import argparse
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from benchmark import check_cases, trials
from edit_protocol import same_value
from meda_core import Diagnostic
from python_control import replace_body


class BenchmarkTests(unittest.TestCase):
    def test_oracle_does_not_coerce_nested_types(self):
        self.assertFalse(same_value([True],[1]))
        self.assertFalse(same_value({'x':1.0},{'x':1}))
        self.assertTrue(same_value({'x':[1,2]},{'x':[1,2]}))

    def test_python_scope_escape(self):
        source='def solve(*, value: int) -> int:\n    return value\n'
        with self.assertRaises(Diagnostic):
            replace_body(source,'solve','    return value\ndef extra() -> int:\n    return 1')

    def test_python_worker_enforces_deadline(self):
        source='def solve(*, value: int) -> int:\n    while True:\n        pass\n    return value\n'
        outcome=check_cases(source,'python',[{'id':'bounded','operation':'solve','arguments':{'value':1},'expected':1}])
        self.assertEqual(outcome[0]['status'],'fail')

    def test_driver_receives_no_acceptance_or_solution(self):
        tasks=json.loads((ROOT/'benchmark/tasks.json').read_text())['tasks'][:1]
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)
            driver=directory/'driver.py'
            driver.write_text('''import json,sys
r=json.load(sys.stdin)
assert 'acceptance' not in r['prompt'] and 'solution' not in r['prompt']
assert 'languages' not in r['prompt']
body = '{ return 0 }' if r['prompt']['language']=='meda' else '    return 0'
print(json.dumps({'body':body,'usage':{'inputTokens':1,'outputTokens':1}}))
''')
            args=argparse.Namespace(agent_command=json.dumps([sys.executable,str(driver)]),repeats=1,
                                    attempts=2,timeout=10,seed=1,model_id='fixture-driver-not-a-model',
                                    output=str(directory/'report.json'))
            result=trials(tasks,args)
            self.assertEqual(len(result['rows']),2)
            self.assertTrue(all(not row['correct'] for row in result['rows']))
            self.assertTrue(all(row['attempts']==2 for row in result['rows']))


if __name__=='__main__':
    unittest.main()
