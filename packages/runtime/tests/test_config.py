"""Validate the public configuration boundary before creating a transport."""
from dataclasses import replace
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from meda_runtime.host import Host, HostConfig, Limits


def config(**changes):
    values = dict(mcp_url="https://mcp.test/mcp", a2a_url="https://agent.test/a2a",
                  mcp_token="MCP-TOKEN-SENTINEL", a2a_token="A2A-TOKEN-SENTINEL",
                  ca_file="/unused/test-ca.pem", tool_descriptor={"name": "evidence.read"},
                  agent_card={"name": "report"})
    values.update(changes)
    return HostConfig(**values)


class ConfigurationTests(unittest.TestCase):
    def test_credentials_are_not_in_config_repr_or_validation_errors(self):
        value = config()
        for secret in (value.mcp_token, value.a2a_token):
            self.assertNotIn(secret, repr(value))
        for bad in ("PRIVATE\r\nHEADER", "PRIVATE TOKEN", "PRIVATE\x00TOKEN", "", None):
            with self.subTest(kind=type(bad).__name__), self.assertRaises(ValueError) as caught:
                config(mcp_token=bad)
            self.assertNotIn("PRIVATE", str(caught.exception))

    def test_count_limits_require_nonnegative_integers(self):
        names = set(Limits.__dataclass_fields__) - {
            "root_seconds", "request_seconds", "cleanup_seconds", "poll_interval"}
        for name in names:
            for invalid in (1.5, 1.0, True, -1, "4", None):
                with self.subTest(name=name, value=invalid), self.assertRaises(ValueError):
                    Limits(**{name: invalid})
        self.assertEqual(Limits(max_polls=0).max_polls, 0)

    def test_deadline_bounds_are_finite_positive_and_reserve_is_valid(self):
        for name in ("root_seconds", "request_seconds", "cleanup_seconds"):
            for invalid in (0, -1, float("nan"), float("inf"), True, 10 ** 1000):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    Limits(**{name: invalid})
        for invalid in (-1, float("nan"), float("inf"), True):
            with self.subTest(interval=invalid), self.assertRaises(ValueError):
                Limits(poll_interval=invalid)
        with self.assertRaises(ValueError):
            Limits(max_requests=1, cleanup_requests=2)
        self.assertEqual(Limits(poll_interval=0).poll_interval, 0)

    def test_bad_endpoints_are_rejected_before_transport_construction(self):
        bad_urls = ["http://example.test", "https://user:PRIVATE@example.test",
                    "https://example.test/#fragment", "https://example.test:bad",
                    "https://example.test:99999", "https://example.test:0",
                    "https://exa\nmple.test", "https://", [], None]
        with patch("meda_runtime.host.HTTPSTransport") as transport:
            for value in bad_urls:
                with self.subTest(value=value), self.assertRaises(ValueError) as caught:
                    Host(config(mcp_url=value))
                self.assertNotIn("PRIVATE", str(caught.exception))
            transport.assert_not_called()

    def test_grants_and_documents_accept_collections_but_not_scalar_strings(self):
        value = config(grants=["readEvidence"], allowed_documents=["doc-1"])
        self.assertEqual(value.grants, frozenset({"readEvidence"}))
        self.assertEqual(value.allowed_documents, frozenset({"doc-1"}))
        for changes in ({"grants": "readEvidence"}, {"grants": ["unknown"]},
                        {"grants": [None]}, {"allowed_documents": "doc-1"},
                        {"allowed_documents": [""]}, {"allowed_documents": {"id": "doc"}}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                config(**changes)
        self.assertEqual(config(grants=[], allowed_documents=[]).grants, frozenset())

    def test_identity_revision_limits_and_metadata_fail_closed(self):
        for changes in ({"principal": ""}, {"tenant": None}, {"expected_revision": True},
                        {"expected_revision": 1.0}, {"expected_revision": -1},
                        {"expected_revision": 1_000_001}, {"limits": {}},
                        {"tool_descriptor": []}, {"agent_card": {"nan": float("nan")}},
                        {"tool_descriptor": {"value": object()}}, {"ca_file": ""}):
            with self.subTest(fields=list(changes)), self.assertRaises(ValueError):
                config(**changes)
        with self.assertRaises(ValueError):
            Host(None)

    def test_host_snapshots_caller_owned_metadata_and_dictionary_config(self):
        source = config()
        transport = object()
        host = Host(source, transport=transport)
        source.tool_descriptor["name"] = "changed"
        source.agent_card["name"] = "changed"
        self.assertEqual(host.config.tool_descriptor["name"], "evidence.read")
        self.assertEqual(host.config.agent_card["name"], "report")
        values = dict(source.__dict__, limits={"max_polls": 0})
        second = Host(values, transport=transport)
        self.assertEqual(second.limits.max_polls, 0)
        self.assertIs(second.transport, transport)


if __name__ == "__main__":
    unittest.main()
