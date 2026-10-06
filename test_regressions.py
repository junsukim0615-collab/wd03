"""Offline regression tests; the official test_tasks.py remains unchanged."""
import unittest
from unittest.mock import patch
import task1_resolve as dns
import task2_steering as steering


def response(answer=(), authority=(), additional=(), aa=False):
    return dict(rcode=0, authoritative=aa, answer=answer,
                authority=authority, additional=additional)


class ResolverStatsTests(unittest.TestCase):
    def test_missing_glue_timeout_and_cname_are_counted(self):
        resolver = dns.Resolver()

        def query(server, name):
            if server == dns.ROOT_SERVERS[0]:
                raise TimeoutError("simulated unresponsive server")
            if name == "ns.other.test":
                return response([(name, dns.TYPE_A, "192.0.2.53")], aa=True)
            if name == "target.test":
                return response([(name, dns.TYPE_A, "192.0.2.8")], aa=True)
            if server == "192.0.2.53":
                return response([(name, dns.TYPE_CNAME, "target.test")], aa=True)
            return response(authority=[("test", dns.TYPE_NS, "ns.other.test")])

        with patch.object(resolver, "_query", side_effect=query):
            address, path = resolver.resolve("site.test")
            self.assertEqual(address, "192.0.2.8")
            self.assertEqual(path[0], dns.ROOT_SERVERS[0])
            self.assertEqual(len(path), 7)
            self.assertEqual(sum(q["purpose"] == "no_glue_ns"
                                 for q in resolver.query_log), 2)
            self.assertEqual(resolver.ns_walks, 1)
            self.assertEqual(resolver.cname_restarts, 1)
            resolver.resolve("target.test")
            self.assertEqual(len(resolver.query_log), 2)  # reset per resolve
            self.assertEqual(resolver.ns_walks, 0)

    def test_cname_loop_still_stops(self):
        resolver = dns.Resolver()
        with patch.object(resolver, "_query", side_effect=lambda server, name:
                          response([(name, dns.TYPE_CNAME, name)], aa=True)):
            with self.assertRaises(RuntimeError):
                resolver.resolve("loop.test")


class NetworkSelectionTests(unittest.TestCase):
    def setUp(self):
        self.data = {"runs": [
            {"network": "office", "completed": True, "started_at": "2026-10-01"},
            {"network": "phone", "completed": True, "started_at": "2026-10-02"},
            {"network": "office", "completed": True, "started_at": "2026-10-03"},
            {"network": "current-network", "completed": True, "started_at": "2026-10-04"},
            {"network": "office", "completed": False, "started_at": "2026-10-05"},
        ]}

    def test_arbitrary_names_latest_complete_and_placeholder(self):
        runs = steering.select_runs(self.data)
        self.assertEqual([r["network"] for r in runs], ["office", "phone"])
        self.assertEqual(runs[0]["started_at"], "2026-10-03")

    def test_explicit_selection_order(self):
        runs = steering.select_runs(self.data, ["phone", "office"])
        self.assertEqual([r["network"] for r in runs], ["phone", "office"])

    def test_ambiguous_networks_require_selection(self):
        self.data["runs"].append(dict(network="cafe", completed=True, started_at="2026-10-06"))
        with self.assertRaises(ValueError):
            steering.select_runs(self.data)
        self.assertEqual(len(steering.select_runs(self.data, ["office", "phone"])), 2)

    def test_duplicate_missing_and_placeholder_rejected(self):
        for names in [["office", "office"], ["office", "missing"],
                      ["office", "current-network"]]:
            with self.subTest(names=names), self.assertRaises(ValueError):
                steering.select_runs(self.data, names)

    def test_one_network_is_not_enough(self):
        with self.assertRaises(ValueError):
            steering.select_runs({"runs": self.data["runs"][:1]})


if __name__ == "__main__":
    unittest.main()
