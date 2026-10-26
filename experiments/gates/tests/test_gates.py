import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from meda_core import Diagnostic, Evaluator, Program, digest, format_source
from edit_protocol import Host


class CorpusTests(unittest.TestCase):
    def test_cli_corpus(self):
        manifest = json.loads((ROOT / "corpus/manifest.json").read_text())
        for case in manifest["cases"]:
            with self.subTest(case=case["id"]):
                command = [sys.executable, str(ROOT / "meda.py"), case["command"], str(ROOT / "corpus" / case["source"]),
                           "--operation", case["operation"], "--arguments", json.dumps(case["arguments"])]
                if "fuel" in case:
                    command += ["--fuel", str(case["fuel"])]
                proc = subprocess.run(command, capture_output=True, text=True, timeout=5)
                self.assertEqual(proc.stderr, "")
                result = json.loads(proc.stdout)
                if "error" in case:
                    self.assertNotEqual(proc.returncode, 0)
                    self.assertEqual(result["diagnostic"]["code"], case["error"])
                    self.assertEqual(result["diagnostic"]["phase"], case["phase"])
                elif case["command"] == "test":
                    self.assertEqual(result["tests"], case["expected"])
                    self.assertEqual(proc.returncode, 1 if any(t["status"] == "fail" for t in case["expected"]) else 0)
                else:
                    self.assertEqual(proc.returncode, 0, result)
                    self.assertEqual(result["value"], case["expected"])

    def test_formatter_preserves_comments_and_meaning(self):
        source = '// 😀 comment\r\noperation main() -> Int effects [] {\r\nreturn 7 // keep me\r\n}\r\n'
        formatted = format_source(source)
        self.assertEqual(format_source(formatted), formatted)
        self.assertIn('// 😀 comment', formatted)
        self.assertIn('// keep me', formatted)
        self.assertNotIn('\r', formatted)
        self.assertEqual(Evaluator(Program(formatted)).invoke('main', {}), 7)

    def test_byte_and_editor_diagnostics(self):
        source = '// 😀\noperation main() -> Int effects [] {\n  return missing\n}\n'
        try:
            Program(source)
        except Diagnostic as error:
            d = error.json(source)
            self.assertEqual(d['span']['startByte'], source.encode().index(b'missing'))
            self.assertEqual(d['editor'], {'line':2,'character':9})
        else:
            self.fail('Unknown name should fail')


SOURCE = '''// Protected report acceptance example.
let minimum: Int = 1
operation sameId(actual: Text, expected: Text) -> Bool effects [] {
  return actual == expected
}
operation reportValid(actual: Text, expected: Text, sourceKnown: Bool, length: Int) -> Bool effects [] {
  return sameId(actual: actual, expected: expected) and sourceKnown and length >= minimum
}
operation accept(actual: Text, expected: Text, sourceKnown: Bool, length: Int) -> Bool effects []
  ensure result implies reportValid(actual: actual, expected: expected, sourceKnown: sourceKnown, length: length)
{
  return reportValid(actual: actual, expected: expected, sourceKnown: sourceKnown, length: length)
}
operation unrelated(value: Int) -> Int effects [] {
  return value + 1
}
test "unknown source rejected" {
  assert !accept(actual: "checkout-17", expected: "checkout-17", sourceKnown: false, length: 5)
}
'''


class EditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / 'app.meda'
        self.source.write_text(SOURCE)
        self.checks = [{'id':'known-valid', 'operation':'accept', 'arguments':{'actual':'checkout-17','expected':'checkout-17','sourceKnown':True,'length':5},'expected':True}]
        (self.root/'checks.json').write_text(json.dumps(self.checks))
        self.grant = {'version':1,'grantId':'test-host-grant','baseRevision':digest(SOURCE),
                      'allowedTargets':['sameId','reportValid','unrelated','accept'], 'allowSpecificationRoots':[],
                      'checkFile':'checks.json','checkDigest':digest((self.root/'checks.json').read_text()),
                      'testIds':['unknown source rejected'],'expiresAt':None}
        self.make_host()

    def make_host(self):
        (self.root/'grant.json').write_text(json.dumps(self.grant))
        self.host = Host(self.source, self.root/'grant.json')
        self.tx = self.host.begin_edit(digest(SOURCE))['transaction']

    def tearDown(self):
        self.temp.cleanup()

    def expect_code(self, code, fn):
        with self.assertRaises(Diagnostic) as caught:
            fn()
        self.assertEqual(caught.exception.code, code)

    def replace(self, symbol, body):
        return self.host.replace_body(self.tx, symbol, body)

    def test_selective_helper_weakening_is_spec_change(self):
        self.replace('reportValid', '{\n  return sourceKnown and length >= minimum\n}')
        self.expect_code('SpecificationChange', lambda: self.host.validate_edit(self.tx))
        self.assertEqual(self.source.read_text(), SOURCE)

    def test_transitive_helper_weakening_is_spec_change(self):
        self.replace('sameId', '{\n  return true\n}')
        self.expect_code('SpecificationChange', lambda: self.host.validate_edit(self.tx))

    def test_constant_and_added_dependency_are_in_closure(self):
        original = Program(SOURCE).specification()
        changed = Program(SOURCE.replace('minimum: Int = 1','minimum: Int = 0')).specification()
        root = 'accept:contract:0'
        self.assertNotEqual(original[root]['digest'], changed[root]['digest'])
        self.assertIn('constant:minimum', original[root]['dependencies'])
        self.replace('sameId', '{\n  return unrelated(value: 0) > 0\n}')
        self.expect_code('SpecificationChange', lambda: self.host.validate_edit(self.tx))

    def test_unrelated_helper_can_commit(self):
        self.replace('unrelated', '{\n  return value + 2\n}')
        receipt = self.host.validate_edit(self.tx)
        self.assertEqual(receipt['status'], 'validated')
        self.assertEqual(receipt['specificationRoots'], [])
        out = self.host.commit_edit(self.tx, receipt['receiptId'], digest(SOURCE))
        self.assertEqual(out['status'], 'committed')
        self.assertIn('// Protected report acceptance example.', self.source.read_text())
        self.assertEqual(self.host.transaction_status(self.tx)['status'], 'committed')

    def test_intentional_spec_change_requires_grant(self):
        self.grant['allowSpecificationRoots'] = ['accept:contract:0']
        self.make_host()
        self.replace('sameId', '{\n  return true\n}')
        self.assertEqual(self.host.validate_edit(self.tx)['status'], 'validated')

    def test_scope_escape_payload_rejected(self):
        self.expect_code('EditScope', lambda: self.replace('unrelated', '{ return value }\noperation injected() -> Int effects [] { return 0 }'))

    def test_ungranted_target(self):
        self.grant['allowedTargets']=['accept']
        self.make_host()
        self.expect_code('EditScope', lambda: self.replace('sameId','{ return true }'))

    def test_stale_revision(self):
        self.replace('unrelated','{ return value + 2 }')
        receipt=self.host.validate_edit(self.tx)
        self.source.write_text(SOURCE+'// concurrent change\n')
        self.expect_code('StaleRevision', lambda:self.host.commit_edit(self.tx,receipt['receiptId'],digest(SOURCE)))

    def test_stale_receipt(self):
        self.replace('unrelated','{ return value + 2 }')
        receipt=self.host.validate_edit(self.tx)
        self.replace('unrelated','{ return value + 3 }')
        self.expect_code('InvalidReceipt',lambda:self.host.commit_edit(self.tx,receipt['receiptId'],digest(SOURCE)))

    def test_edited_check_file(self):
        (self.root/'checks.json').write_text('[]')
        self.expect_code('CheckChanged',lambda:self.host.validate_edit(self.tx))

    def test_edited_grant(self):
        (self.root/'grant.json').write_text('{}')
        self.expect_code('GrantChanged',lambda:self.host.validate_edit(self.tx))

    def test_false_acceptance_prevents_receipt(self):
        self.replace('accept','{ return false }')
        result=self.host.validate_edit(self.tx)
        self.assertEqual(result['status'],'failed')
        self.expect_code('InvalidReceipt',lambda:self.host.commit_edit(self.tx,'invented',digest(SOURCE)))

    def test_type_error_can_be_repaired_in_same_transaction(self):
        self.replace('unrelated','{ return true }')
        self.expect_code('TypeMismatch',lambda:self.host.validate_edit(self.tx))
        self.replace('unrelated','{ return value + 3 }')
        self.assertEqual(self.host.validate_edit(self.tx)['status'],'validated')

    def test_qualified_constant_dependency_is_protected(self):
        source=SOURCE.replace('length >= minimum','length >= self.minimum')
        original=Program(source).specification()
        updated=Program(source.replace('minimum: Int = 1','minimum: Int = 0')).specification()
        self.assertIn('constant:minimum',original['accept:contract:0']['dependencies'])
        self.assertNotEqual(original,updated)

    def test_empty_acceptance_rejected(self):
        (self.root/'checks.json').write_text('[]')
        self.grant['checkDigest']=digest('[]')
        self.expect_code('TestDiscovery',self.make_host)

    def test_json_protocol_from_outside(self):
        proc=subprocess.Popen([sys.executable,str(ROOT/'meda.py'),'edit',str(self.source),'--grant',str(self.root/'grant.json')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            def request(method,params):
                proc.stdin.write(json.dumps({'method':method,'params':params})+'\n')
                proc.stdin.flush()
                return json.loads(proc.stdout.readline())
            opened=request('begin_edit',{'expectedRevision':digest(SOURCE)})['result']['transaction']
            self.assertTrue(request('replace_body',{'transaction':opened,'symbol':'unrelated','body':'{ return value + 2 }'})['ok'])
            receipt=request('validate_edit',{'transaction':opened})['result']
            self.assertEqual(request('commit_edit',{'transaction':opened,'receiptId':receipt['receiptId'],'expectedRevision':digest(SOURCE)})['result']['status'],'committed')
        finally:
            proc.stdin.close()
            proc.wait(timeout=5)
            self.assertEqual(proc.returncode,0)
            self.assertEqual(proc.stderr.read(),'')
            proc.stdout.close()
            proc.stderr.close()


if __name__ == '__main__':
    unittest.main()
