import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from host import FixturePeer, GuardedHost


def action(kind="read", task="", value="", tenant="team-a"):
    return {"kind": kind, "tenant": tenant, "taskId": task, "input": value}


class HostTests(unittest.TestCase):
    def test_authorized_flow_and_exact_trace_metadata(self):
        with FixturePeer() as peer:
            host = GuardedHost(peer)
            evidence = host.execute(action())
            self.assertEqual(evidence["value"], "evidence:42")
            task = host.execute(action("submit", value=evidence["value"]))
            self.assertEqual(task["kind"], "pending")
            done = host.execute(action("poll", task=task["taskId"]))
            self.assertEqual(done, {"kind": "completed", "taskId": "t1",
                                    "value": "report:evidence:42", "code": ""})
            self.assertEqual(host.dispatches, 3)
            self.assertEqual(peer.stats()["created"], 1)
            self.assertNotIn("evidence:42", json.dumps(host.trace))

    def test_host_denials_cannot_dispatch(self):
        with FixturePeer() as peer:
            host = GuardedHost(peer, allowed_ops=("read",))
            self.assertEqual(host.execute(action(tenant="team-b"))["kind"], "denied")
            self.assertEqual(host.execute(action("submit"))["kind"], "denied")
            bad = action()
            bad["endpoint"] = "http://example.invalid/"
            self.assertEqual(host.execute(bad)["kind"], "invalid")
            self.assertEqual(peer.stats()["calls"], {})
            self.assertEqual(host.dispatches, 0)
            self.assertEqual(host.execute(action())["kind"], "evidence")

    def test_lost_submission_is_unknown_without_retry(self):
        with FixturePeer("lost_submit") as peer:
            host = GuardedHost(peer)
            result = host.execute(action("submit", value="evidence:42"))
            self.assertEqual(result["kind"], "unknown")
            self.assertEqual(result["taskId"], "")
            self.assertEqual(host.dispatches, 1)
            stats = peer.stats()
            self.assertEqual(stats["created"], 1)
            self.assertEqual(stats["calls"]["message/send"], 1)

    def test_remote_task_can_be_reattached_but_authority_is_current(self):
        with FixturePeer("needs_input") as peer:
            first = GuardedHost(peer, root_id="first")
            task_id = first.execute(action("submit", value="evidence:42"))["taskId"]
            first.close()
            self.assertEqual(first.execute(action("poll", task=task_id))["code"], "RootClosed")
            other = GuardedHost(peer, principal="bob", root_id="other")
            self.assertEqual(other.execute(action("poll", task=task_id))["kind"], "denied")
            later = GuardedHost(peer, root_id="later")
            self.assertEqual(later.execute(action("poll", task=task_id))["kind"], "input_required")
            self.assertEqual(later.execute(action("continue", task=task_id, value="approved"))["value"],
                             "report:evidence:42")
            stats = peer.stats()
            self.assertEqual(stats["created"], 1)
            self.assertEqual(stats["tasks"][task_id]["continuationInput"], "approved")

    def test_invalid_peer_data_stays_a_typed_error(self):
        expected = {"malformed": "MalformedPeerData", "oversized": "ResponseLimit",
                    "wrong_type": "InvalidPeerData", "wrong_id": "InvalidEnvelope"}
        for mode, code in expected.items():
            with self.subTest(mode=mode), FixturePeer(mode) as peer:
                host = GuardedHost(peer, max_bytes=512)
                result = host.execute(action())
                self.assertEqual(result["kind"], "invalid")
                self.assertEqual(result["code"], code)
                self.assertEqual(host.dispatches, 1)

    def test_call_budget_and_pending_remote_work(self):
        with FixturePeer("pending") as peer:
            host = GuardedHost(peer, max_calls=2)
            task_id = host.execute(action("submit", value="evidence:42"))["taskId"]
            self.assertEqual(host.execute(action("poll", task=task_id))["kind"], "pending")
            self.assertEqual(host.execute(action("poll", task=task_id))["kind"], "budget")
            host.close()
            stats = peer.stats()
            self.assertEqual(stats["tasks"][task_id]["state"], "working")
            self.assertEqual(stats["calls"]["tasks/get"], 1)

    def test_cancel_is_not_completion(self):
        with FixturePeer("pending") as peer:
            host = GuardedHost(peer)
            task = host.execute(action("submit", value="evidence:42"))
            result = host.execute(action("cancel", task=task["taskId"]))
            self.assertEqual(result["kind"], "cancelled")
            self.assertEqual(result["value"], "")

    def test_nonterminal_and_terminal_states_are_not_conflated(self):
        with FixturePeer("pending") as peer:
            host = GuardedHost(peer)
            task_id = host.execute(action("submit", value="evidence:42"))["taskId"]
            self.assertEqual(host.execute(action("continue", task=task_id, value="approved"))["kind"], "pending")
            self.assertNotIn("continuationInput", peer.stats()["tasks"][task_id])
            host.execute(action("cancel", task=task_id))
            self.assertEqual(host.execute(action("poll", task=task_id))["kind"], "cancelled")
        with FixturePeer("needs_input") as peer:
            host = GuardedHost(peer)
            task_id = host.execute(action("submit", value="evidence:42"))["taskId"]
            self.assertEqual(host.execute(action("poll", task=task_id))["kind"], "input_required")
            host.execute(action("continue", task=task_id, value="approved"))
            self.assertEqual(host.execute(action("cancel", task=task_id))["kind"], "completed")

    def test_empty_grant_and_zero_budget_deny_without_dispatch(self):
        with FixturePeer() as peer:
            host = GuardedHost(peer, allowed_ops=())
            self.assertEqual(host.execute(action())["code"], "AuthorityDenied")
            host = GuardedHost(peer, max_calls=0)
            self.assertEqual(host.execute(action())["code"], "CallLimit")
            self.assertEqual(peer.stats()["calls"], {})

    def test_input_validation_and_constructor_limits(self):
        with FixturePeer() as peer:
            host = GuardedHost(peer)
            for invalid in ({}, {**action(), "input": False}, action(value="\ud800"), action(value="x" * 1025),
                            action("poll"), action("read", task="t1"), action("continue", task="t1")):
                self.assertEqual(host.execute(invalid)["kind"], "invalid")
            self.assertEqual(peer.stats()["calls"], {})
            with self.assertRaises(ValueError):
                GuardedHost(peer, max_calls=True)


if __name__ == "__main__":
    unittest.main()
