import json
import unittest

from experiments.gates import meda_core as core
from experiments.decision_screen.language import Bindings, Evaluator, Program, export_value, variant

EVIDENCE = {"documentId": "evidence-42", "revision": 1, "facts": [{"id": "f1", "value": "blue"}]}
READ = '''operation read(documentId: Text) -> EvidenceResult effects [ReadEvidence] {
  return host.readEvidence(documentId: documentId)
}
'''


class LanguageTests(unittest.TestCase):
    def reject(self, source, code):
        with self.assertRaises(core.Diagnostic) as caught:
            Program(source)
        self.assertEqual(caught.exception.code, code)

    def test_default_profile_remains_pure(self):
        with self.assertRaises(core.Diagnostic) as caught:
            core.Program(READ)
        self.assertEqual(caught.exception.code, "UnsupportedEffect")
        self.assertEqual(core.Evaluator(core.Program('operation main() -> Int effects [] { return 4 }')).invoke('main', {}), 4)

    def test_declared_and_transitive_effect_bounds(self):
        self.reject(READ.replace('[ReadEvidence]', '[]'), 'EffectViolation')
        self.reject(READ + '\noperation main() -> EvidenceResult effects [] { return read(documentId: "evidence-42") }', 'EffectViolation')
        self.reject(READ.replace('[ReadEvidence]', '[Network]'), 'UnsupportedEffect')
        self.reject(READ.replace('[ReadEvidence]', '[ReadEvidence, ReadEvidence]'), 'DuplicateEffect')
        Program(READ + '\noperation main() -> EvidenceResult effects [ReadEvidence] { return read(documentId: "evidence-42") }')

    def test_native_calls_have_checked_labels_and_types(self):
        self.reject(READ.replace('documentId: documentId', 'documentId: 9'), 'TypeMismatch')
        self.reject(READ.replace('documentId: documentId', 'document: documentId'), 'ArgumentLabels')
        self.reject(READ.replace('host.readEvidence', 'host.fake'), 'UnknownOperation')
        self.reject(READ.replace('documentId: Text', 'host: Text'), 'ReservedBinding')

    def test_contracts_assertions_and_tests_cannot_call_effects(self):
        helper = 'operation touch() -> Bool effects [ReadEvidence] { discard host.readEvidence(documentId: "evidence-42")\n return true }\n'
        self.reject(helper + 'operation main() -> Bool effects [ReadEvidence]\n require touch()\n{ return true }', 'EffectViolation')
        self.reject(helper + 'operation main() -> Bool effects [ReadEvidence] { assert touch()\n return true }', 'EffectViolation')
        self.reject(helper + 'test "no effects" { discard touch() }', 'EffectViolation')

    def test_fixed_names_cannot_be_redeclared(self):
        self.reject('record TaskRef { token: Text }', 'ReservedBinding')
        self.reject('record Evidence { fake: Text }', 'ReservedBinding')
        self.reject('operation host() -> Unit effects [] { return unit }', 'ReservedBinding')

    def test_opaque_references_have_no_constructor_or_observers(self):
        self.reject('operation mint() -> TaskRef effects [] { return TaskRef {} }', 'UnknownType')
        self.reject('operation peek(ref: TaskRef) -> Text effects [] { return ref.token }', 'UnknownField')
        self.reject('operation change(ref: TaskRef) -> TaskRef effects [] { return ref with { token: "x" } }', 'TypeMismatch')
        self.reject('operation compare(a: List<Task>, b: List<Task>) -> Bool effects [] { return a == b }', 'OpaqueReference')

    def test_real_meda_ast_executes_five_direct_host_operations(self):
        source = '''
operation read() -> EvidenceResult effects [ReadEvidence] { return host.readEvidence(documentId: "evidence-42") }
operation submit(evidence: Evidence) -> TaskResult effects [SubmitTask] {
  return host.submit(evidence: evidence, selection: Selection.Included(ids: ["f1"]))
}
operation observe(ref: TaskRef) -> TaskResult effects [ObserveTask] { return host.observe(ref: ref) }
operation provide(ref: TaskRef) -> TaskResult effects [ProvideInput] { return host.provideInput(ref: ref, includeIds: ["f1"]) }
operation cancel(ref: TaskRef) -> TaskResult effects [CancelTask] { return host.cancel(ref: ref) }
'''
        calls = []
        def exchange(operation, args):
            calls.append((operation, args))
            return ({'kind': 'Evidence', 'value': EVIDENCE} if operation == 'readEvidence' else
                    {'kind': 'Task', 'ref': 'private-wire-token', 'state': 'Working'})
        evaluator = Evaluator(Program(source), exchange)
        evidence = evaluator.invoke('read', {})['fields']['value']
        task = evaluator.invoke('submit', {'evidence': evidence})['fields']['task']
        for operation in ('observe', 'provide', 'cancel'):
            result = evaluator.invoke(operation, {'ref': task['ref']})
            self.assertIs(result['fields']['task']['ref'], task['ref'])
        self.assertEqual([name for name, _ in calls], ['readEvidence', 'submit', 'observe', 'provideInput', 'cancel'])
        self.assertEqual(calls[1][1], {'evidence': EVIDENCE, 'includeIds': ['f1']})
        self.assertEqual(calls[-1][1], {'ref': 'private-wire-token'})
        self.assertFalse(hasattr(task['ref'], '__dict__'))
        with self.assertRaises(core.Diagnostic):
            export_value({'nested': [task]})
        evaluator.close()
        self.assertFalse(evaluator.bindings.owns(task['ref']))

    def test_foreign_forged_and_retired_refs_cannot_dispatch(self):
        calls = []
        exchange = lambda name, args: calls.append((name,args)) or {'kind':'Task','ref':'one','state':'Working'}
        first, second = Bindings(exchange), Bindings(exchange)
        ref = first.call('submit', {'evidence':EVIDENCE,'selection':variant('Omitted')})['fields']['task']['ref']
        self.assertEqual(calls[0][1], {'evidence': EVIDENCE})
        for wrong in ({'token':'one'}, 'one', ref):
            outcome = second.call('observe', {'ref':wrong})
            self.assertEqual(outcome['fields']['error']['code'], 'InvalidReference')
        first.close()
        self.assertEqual(first.call('observe', {'ref':ref})['fields']['error']['code'], 'InvalidReference')
        self.assertEqual(len(calls), 1)

    def test_bad_host_results_are_rejected_without_fabricating_success(self):
        values = [None, {'kind':'Error','code':[],'remoteOutcome':'Unknown'},
                  {'kind':'Error','code':'Timeout','remoteOutcome':{}},
                  {'kind':'Task','ref':'token','state':'FutureState'},
                  {'kind':'Task','ref':{},'state':'Working'}]
        for value in values:
            with self.subTest(value=value):
                bindings = Bindings(lambda name,args:value)
                result = bindings.call('submit', {'evidence':EVIDENCE,'selection':variant('Omitted')})
                self.assertEqual(result['fields']['error']['code'],'ProtocolRejected')
        error = {'kind':'Error','code':'Timeout','remoteOutcome':'Unknown','fatal':True}
        evaluator = Evaluator(Program(READ), lambda name,args:error)
        self.assertEqual(evaluator.invoke('read',{'documentId':'evidence-42'}),variant('Error',error={k:v for k,v in error.items() if k!='kind'}))

    def test_domain_relationships_remain_for_source_to_validate(self):
        report = {'documentId':'wrong-document','revision':2,'selected':[{'id':'f1','value':'fabricated'}]}
        bindings = Bindings(lambda name,args:{'kind':'Task','ref':'one','state':'Completed','artifact':report})
        result = bindings.call('submit',{'evidence':EVIDENCE,'selection':variant('Omitted')})
        self.assertEqual(result['fields']['task']['artifact'],variant('Value',report=report))
        bindings.exchange = lambda name,args:{'kind':'Task','ref':'one','state':'Completed','artifact':{'malformed':True}}
        self.assertEqual(bindings.call('submit',{'evidence':EVIDENCE,'selection':variant('Omitted')})['fields']['task']['artifact'],variant('Invalid'))

    def test_protobuf_integral_json_numbers_decode_to_meda_int(self):
        for revision in (1, 1.0, 2.0):
            with self.subTest(revision=revision):
                report = {'documentId':'evidence-42','revision':revision,'selected':[{'id':'f1','value':'blue'}]}
                evaluator = Evaluator(Program('operation submit(evidence: Evidence) -> TaskResult effects [SubmitTask] { return host.submit(evidence: evidence, selection: Selection.Omitted) }'),
                    lambda name,args:{'kind':'Task','ref':'one','state':'Completed','artifact':report})
                artifact = evaluator.invoke('submit',{'evidence':EVIDENCE})['fields']['task']['artifact']
                self.assertEqual(artifact['case'], 'Value')
                self.assertEqual(artifact['fields']['report']['revision'], revision)
                self.assertIs(type(artifact['fields']['report']['revision']), int)
        for revision in (True, False, 1.5, float('nan'), float('inf'), -float('inf'), 1_000_001.0):
            with self.subTest(revision=revision):
                report = {'documentId':'evidence-42','revision':revision,'selected':[]}
                bindings = Bindings(lambda name,args:{'kind':'Task','ref':'one','state':'Completed','artifact':report})
                self.assertEqual(bindings.call('submit',{'evidence':EVIDENCE,'selection':variant('Omitted')})['fields']['task']['artifact'],variant('Invalid'))

    def test_export_limits_and_json_copy(self):
        original = {'items':[{'ok':True}]}
        result = export_value(original)
        self.assertEqual(result, original)
        self.assertIsNot(result['items'], original['items'])
        for value in ('x'*65537, [float('nan')], {1:'value'}):
            with self.subTest(value=type(value).__name__), self.assertRaises(core.Diagnostic):
                export_value(value)
        value = None
        for _ in range(18): value = [value]
        with self.assertRaises(core.Diagnostic): export_value(value)


if __name__ == '__main__':
    unittest.main()
