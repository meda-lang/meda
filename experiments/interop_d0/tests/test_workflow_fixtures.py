"""Execute the two previously missing workflow fixtures through real SDK peers.

These focused lifecycle checks do not promote incomplete frozen D0 obligations
to passes. The immutable inventory and independent oracle stay unchanged.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import threading
import unittest
from unittest import mock

from experiments.interop_d0 import oracle, runner


HERE = Path(__file__).resolve().parents[1]
CASES = {case["id"]: case for case in json.loads((HERE / "acceptance.json").read_text())["cases"]}


class WorkflowFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        runner.compile_client()

    def assert_terminal(self, receipt, outcome, *, application_finish=False):
        self.assertEqual(receipt["result"]["outcome"], outcome)
        worker = receipt["worker"]
        self.assertTrue(worker["retired"])
        self.assertTrue(worker["supervisorJoined"])
        self.assertEqual(worker["responsesAfterFatal"], 0)
        self.assertEqual(worker["finishFrames"], int(application_finish))
        publications = [row for row in receipt["trace"] if row["event"] == "publication"]
        self.assertEqual(len(publications), 1)
        self.assertEqual(publications[0]["success"], outcome == "Success")
        close = next(index for index, row in enumerate(receipt["trace"])
                     if row["event"] in {"root_close", "root_abort"})
        self.assertFalse(any(row["event"] == "dispatch" and not row["cleanup"]
                             for row in receipt["trace"][close + 1:]))

    def test_input_required_wait_reaches_real_root_deadline(self):
        case = CASES["W02-wait-deadline"]
        scenario = copy.deepcopy(case["scenario"])
        scenario["limits"] = {"rootWorkMs": 2000}
        receipt = runner.execute_workflow(scenario)

        self.assert_terminal(receipt, "Timeout")
        self.assertTrue(receipt["result"]["fatal"])
        worker = receipt["worker"]
        self.assertEqual(worker["termination"], "deadline")
        self.assertEqual([call["operation"] for call in worker["calls"]], ["readEvidence", "submit"])
        self.assertEqual(worker["calls"][-1]["state"], "InputRequired")
        self.assertIsNone(worker["applicationFinish"])
        self.assertGreater(worker["retirementRequestedAfterStartSeconds"], 1.5)
        self.assertLess(worker["retirementAfterRequestSeconds"], 3)
        self.assertTrue(receipt["peerProcessesRetired"])
        self.assertNotIn("localActivityFixture", receipt)

        assessment = oracle.evaluate_case(case, receipt)
        self.assertEqual([check["name"] for check in assessment["checks"]
                          if check["status"] == "failed"], [])
        self.assertEqual(assessment["normalized"]["categories"], ["root_deadline"])
        self.assertEqual(assessment["normalized"]["phases"], ["root_terminal"])
        self.assertEqual(assessment["status"], "unverified")
        self.assertIn("clock_barrier_log", assessment["witnesses"]["available"])

    def test_missing_input_control_and_supplied_input_precedence(self):
        controls = [
            ({"initialIncludeIds": None}, "NeedsInput", ["readEvidence", "submit"]),
            ({"initialIncludeIds": None, "onMissingInput": "wait",
              "suppliedIncludeIds": ["f1", "f2"]}, "Success",
             ["readEvidence", "submit", "provideInput"]),
        ]
        for scenario, outcome, operations in controls:
            with self.subTest(outcome=outcome):
                receipt = runner.execute_workflow(scenario)
                self.assert_terminal(receipt, outcome, application_finish=True)
                self.assertEqual(receipt["worker"]["termination"], "normal")
                self.assertEqual([call["operation"] for call in receipt["worker"]["calls"]], operations)
                self.assertTrue(receipt["peerProcessesRetired"])
                self.assertNotIn("localActivityFixture", receipt)

    def test_nonjoining_activity_uses_real_cleanup_deadline_and_is_released(self):
        scenario = copy.deepcopy(CASES["W04-cleanup-cannot-join"]["scenario"])
        scenario["limits"] = {"cleanup_seconds": .2}
        prior_threads = set(threading.enumerate())
        with runner.environment(scenario) as env:
            host = env["host"]
            receipt = runner.run_client(host, runner.workflow_input(scenario),
                                        proxies=env["proxies"], scenario=scenario)
            self.assert_terminal(receipt, "CleanupFailure")
            self.assertTrue(receipt["result"]["fatal"])
            self.assertEqual(receipt["worker"]["termination"], "root_abort")
            self.assertEqual([call["operation"] for call in receipt["worker"]["calls"]],
                             ["readEvidence", "submit"])
            self.assertEqual(receipt["cleanup"][0]["outcome"], "CleanupFailure")
            self.assertEqual(receipt["localActivityFixture"], {
                "started": True, "activeAtPublication": True, "joinedAfterRelease": True})
            self.assertGreaterEqual(receipt["worker"]["hostFinishElapsedSeconds"], .19)
            self.assertLess(receipt["worker"]["hostFinishElapsedSeconds"], 1.2)
            self.assertFalse(host._active)
            self.assertEqual(host.trace, receipt["trace"])
            self.assertEqual(host.finish({"outcome": "Success"})["result"], receipt["result"])
            self.assertEqual(host.trace, receipt["trace"])
        self.assertEqual([thread.name for thread in threading.enumerate()
                          if thread not in prior_threads and thread.name.startswith("meda-")], [])

        control = {key: value for key, value in scenario.items() if key != "localCleanup"}
        receipt = runner.execute_workflow(control)
        self.assert_terminal(receipt, "RootTerminated")
        self.assertNotIn("localActivityFixture", receipt)
        self.assertFalse(any(row["outcome"] == "CleanupFailure" for row in receipt["cleanup"]))

    def test_nonjoining_activity_is_released_when_publication_raises(self):
        scenario = copy.deepcopy(CASES["W04-cleanup-cannot-join"]["scenario"])
        prior_threads = set(threading.enumerate())
        with runner.environment(scenario) as env:
            host = env["host"]

            def fail_publication(_proposal):
                self.assertTrue(host._active, "Fault must already be active before publication")
                raise RuntimeError("injected publication failure")

            with mock.patch.object(host, "finish", side_effect=fail_publication):
                with self.assertRaisesRegex(RuntimeError, "injected publication failure"):
                    runner.run_client(host, runner.workflow_input(scenario),
                                      proxies=env["proxies"], scenario=scenario)
            self.assertFalse(host._active)
            self.assertEqual([thread.name for thread in threading.enumerate()
                              if thread not in prior_threads and thread.name.startswith("meda-")], [])


if __name__ == "__main__":
    unittest.main()
