"""Prospective cancellation-refusal policy; original pilot receipts stay intact."""
import copy
import json
import unittest

try:
    from .test_host import PeerDouble, make_host, submit
except ImportError:
    from test_host import PeerDouble, make_host, submit

from transport import Response


class RefusalPeer(PeerDouble):
    """Exercise protocol-invalid and wrong-operation refusals at the wire boundary."""
    def __init__(self):
        super().__init__()
        self.corrupt_refusal_id = False
        self.refuse_observation = False

    def request(self, verb, url, headers, body, **options):
        response = super().request(verb, url, headers, body, **options)
        request = json.loads(body) if body else None
        if request and request["method"] == "GetTask" and self.refuse_observation:
            return Response(200, {"jsonrpc": "2.0", "id": request["id"],
                                 "error": {"code": -32002, "message": "refused"}}, 100)
        if request and request["method"] == "CancelTask" and self.corrupt_refusal_id:
            value = copy.deepcopy(response.value)
            value["id"] = "unrelated-request"
            return Response(200, value, response.received)
        return response


class CancellationRefusalTests(unittest.TestCase):
    def test_validated_explicit_refusal_skips_cleanup_with_provenance(self):
        host, peer, _ = make_host()
        ref = submit(host)["ref"]
        peer.cancel_refusal = True
        refusal = host.call("cancel", {"ref": ref})
        self.assertEqual(refusal["code"], "TaskNotCancelable")
        self.assertEqual(host.refs[ref]["state"], "Working")
        refused_event = next(event for event in host.trace if event["event"] == "explicit_cancel_refused")
        request_count = len(peer.requests)

        receipt = host.finish({"outcome": refusal["code"]})

        self.assertEqual(len(peer.requests), request_count)
        self.assertEqual(host.cleanup_count, 0)
        self.assertEqual(receipt["cleanup"], [{"outcome": "Skipped", "reason": "PriorExplicitRefusal",
            "refusalSequence": refused_event["sequence"], "lastObservedState": "Working",
            "remoteOutcome": "Unknown"}])
        self.assertEqual(sum(event["event"] == "cleanup_skipped" for event in receipt["trace"]), 1)
        self.assertFalse(any(event["event"] == "dispatch" and event["cleanup"] for event in receipt["trace"]))
        self.assertEqual(receipt, host.finish({"outcome": "Success"}))
        self.assertNotIn(ref, json.dumps(receipt))

    def test_validated_nonterminal_observation_restores_cleanup(self):
        host, peer, _ = make_host()
        ref = submit(host)["ref"]
        peer.cancel_refusal = True
        host.call("cancel", {"ref": ref})
        refusal_sequence = host.refs[ref]["cancel_refusal_sequence"]
        peer.cancel_refusal = False

        observed = host.call("observe", {"ref": ref})
        self.assertEqual(observed["state"], "Working")
        self.assertNotIn("cancel_refusal_sequence", host.refs[ref])
        restored = next(event for event in host.trace if event["event"] == "cleanup_eligibility_restored")
        self.assertEqual(restored["refusalSequence"], refusal_sequence)
        receipt = host.finish({"outcome": "PollLimit"})
        self.assertEqual(receipt["cleanup"], [{"outcome": "Canceled", "remoteOutcome": "Completed"}])
        self.assertEqual(sum(row[0] == "CancelTask" for row in peer.requests), 2)

    def test_invalid_observation_does_not_clear_refusal(self):
        host, peer, _ = make_host()
        ref = submit(host)["ref"]
        peer.cancel_refusal = True
        host.call("cancel", {"ref": ref})
        peer.wrong_id = True
        self.assertEqual(host.call("observe", {"ref": ref})["code"], "ProtocolRejected")
        receipt = host.finish({"outcome": "ProtocolRejected"})
        self.assertEqual(receipt["cleanup"][0]["reason"], "PriorExplicitRefusal")
        self.assertEqual(sum(row[0] == "CancelTask" for row in peer.requests), 1)

    def test_lost_explicit_cancellation_response_allows_bounded_cleanup(self):
        host, peer, _ = make_host()
        ref = submit(host)["ref"]
        peer.drop = "CancelTask"
        result = host.call("cancel", {"ref": ref})
        self.assertEqual((result["code"], result["remoteOutcome"]), ("TransportFailure", "Unknown"))
        self.assertNotIn("cancel_refusal_sequence", host.refs[ref])
        peer.drop = None
        receipt = host.finish({"outcome": "TransportFailure"})
        self.assertEqual(receipt["cleanup"][0]["outcome"], "Canceled")
        self.assertEqual(host.cleanup_count, 2)  # Card recheck plus one cancellation.
        self.assertEqual(sum(row[0] == "CancelTask" for row in peer.requests), 2)

    def test_unmatched_refusal_response_does_not_suppress_cleanup(self):
        peer = RefusalPeer()
        host, _, _ = make_host(peer)
        ref = submit(host)["ref"]
        peer.cancel_refusal = peer.corrupt_refusal_id = True
        self.assertEqual(host.call("cancel", {"ref": ref})["code"], "ProtocolRejected")
        self.assertNotIn("cancel_refusal_sequence", host.refs[ref])
        peer.cancel_refusal = peer.corrupt_refusal_id = False
        receipt = host.finish({"outcome": "ProtocolRejected"})
        self.assertEqual(receipt["cleanup"][0]["outcome"], "Canceled")

    def test_refusal_from_observe_does_not_count_as_explicit_cancel_refusal(self):
        peer = RefusalPeer()
        host, _, _ = make_host(peer)
        ref = submit(host)["ref"]
        peer.refuse_observation = True
        self.assertEqual(host.call("observe", {"ref": ref})["code"], "TaskNotCancelable")
        self.assertNotIn("cancel_refusal_sequence", host.refs[ref])
        receipt = host.finish({"outcome": "TaskNotCancelable"})
        self.assertEqual(receipt["cleanup"][0]["outcome"], "Canceled")


if __name__ == "__main__":
    unittest.main()
