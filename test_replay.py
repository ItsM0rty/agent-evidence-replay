import unittest
from dataclasses import replace

from replay import Event, Heartbeat, Principal, replay


class ReplayContract(unittest.TestCase):
    def setUp(self):
        self.bindings = {
            ("runtime", "a"): Principal("calendar-agent", "alice"),
            ("runtime", "b"): Principal("mail-agent", "alice"),
            ("runtime", "c"): Principal("other-agent", "bob"),
        }
        self.first = Event("one", "runtime", "a", 1, "model", "shared-key")

    def run_window(self, events, heartbeat=None):
        return replay(events, self.bindings, {
            "runtime": heartbeat or Heartbeat(100, len(events))
        }, now=100)

    def test_shared_key_does_not_merge_agents(self):
        second = Event("two", "runtime", "b", 2, "model", "shared-key")
        result = self.run_window([self.first, second])
        self.assertEqual([x["agent"] for x in result["observations"]],
                         ["calendar-agent", "mail-agent"])

    def test_delegation_retains_child_and_parent_identity(self):
        child = Event("two", "runtime", "b", 2, "tool", parent="one")
        row = self.run_window([self.first, child])["observations"][1]
        self.assertEqual((row["agent"], row["parent_agent"], row["owner"]),
                         ("mail-agent", "calendar-agent", "alice"))

    def test_tool_action_without_model_call_is_observed(self):
        event = replace(self.first, kind="tool", credential="")
        row = self.run_window([event])["observations"][0]
        self.assertEqual((row["kind"], row["agent"]), ("tool", "calendar-agent"))

    def test_stopped_telemetry_is_unknown(self):
        result = self.run_window([self.first], Heartbeat(69, 1))
        self.assertEqual(result["coverage"]["runtime"]["telemetry"], "unknown")

    def test_missing_heartbeat_is_unknown(self):
        result = replay([], self.bindings, {}, now=100)
        self.assertEqual(result["coverage"]["runtime"]["telemetry"], "unknown")

    def test_sequence_gap_is_unknown_despite_live_heartbeat(self):
        result = self.run_window([self.first], Heartbeat(100, 2))
        self.assertEqual(result["coverage"]["runtime"]["telemetry"], "unknown")

    def test_idle_collector_is_live_without_claiming_actions(self):
        result = self.run_window([])
        self.assertEqual(result["observations"], [])
        self.assertEqual(result["coverage"]["runtime"]["telemetry"], "live")

    def test_agent_supplied_identity_does_not_override_binding(self):
        event = replace(self.first, claimed_agent="administrator-agent")
        self.assertEqual(self.run_window([event])["observations"][0]["agent"],
                         "calendar-agent")

    def test_unknown_session_has_no_inferred_identity_from_key(self):
        event = replace(self.first, session="unregistered")
        self.assertEqual(self.run_window([event])["observations"][0]["attribution"],
                         "unknown")

    def test_unregistered_collector_cannot_claim_known_session(self):
        event = replace(self.first, collector="unregistered")
        self.assertIsNone(self.run_window([event])["observations"][0]["agent"])

    def test_missing_parent_does_not_invent_a_delegation(self):
        event = replace(self.first, parent="missing")
        row = self.run_window([event])["observations"][0]
        self.assertEqual(row["parent_link"], "unknown")
        self.assertEqual(row["agent"], "calendar-agent")

    def test_cross_owner_parent_link_needs_additional_authorization(self):
        child = Event("two", "runtime", "c", 2, "tool", parent="one")
        row = self.run_window([self.first, child])["observations"][1]
        self.assertEqual((row["agent"], row["parent_link"]), ("other-agent", "unknown"))

    def test_exact_retry_does_not_duplicate_an_action(self):
        result = self.run_window([self.first, self.first], Heartbeat(100, 1))
        self.assertEqual(len(result["observations"]), 1)
        self.assertEqual(result["coverage"]["runtime"]["telemetry"], "live")

    def test_conflicting_event_id_is_unknown(self):
        other = replace(self.first, session="b", sequence=2)
        result = self.run_window([self.first, other])
        self.assertIsNone(result["observations"][0]["agent"])
        self.assertEqual(result["coverage"]["runtime"]["telemetry"], "unknown")

    def test_out_of_order_delivery_preserves_parent_link(self):
        child = Event("two", "runtime", "b", 2, "tool", parent="one")
        result = self.run_window([child, self.first])
        self.assertEqual(result["observations"][0]["parent_agent"], "calendar-agent")
        self.assertEqual(result["coverage"]["runtime"]["telemetry"], "live")

    def test_collectors_can_use_the_same_event_id(self):
        bindings = {**self.bindings, ("other", "a"): Principal("other-agent", "bob")}
        other = replace(self.first, collector="other")
        result = replay([self.first, other], bindings, {
            "runtime": Heartbeat(100, 1), "other": Heartbeat(100, 1)
        }, now=100)
        self.assertEqual([row["agent"] for row in result["observations"]],
                         ["calendar-agent", "other-agent"])
        self.assertEqual(result["coverage"]["runtime"]["telemetry"], "live")

    def test_parent_id_is_resolved_only_inside_its_collector(self):
        bindings = {**self.bindings, ("other", "a"): Principal("child", "alice")}
        child = Event("two", "other", "a", 1, "tool", parent="one")
        result = replay([self.first, child], bindings, {
            "runtime": Heartbeat(100, 1), "other": Heartbeat(100, 1)
        }, now=100)
        self.assertEqual(result["observations"][1]["parent_link"], "unknown")

    def test_cyclic_parent_links_are_not_reported_as_delegation(self):
        first = replace(self.first, parent="two")
        second = Event("two", "runtime", "b", 2, "tool", parent="one")
        rows = self.run_window([first, second])["observations"]
        self.assertEqual([row["parent_link"] for row in rows], ["unknown", "unknown"])

    def test_self_parent_link_is_unknown(self):
        row = self.run_window([replace(self.first, parent="one")])["observations"][0]
        self.assertEqual(row["parent_link"], "unknown")

    def test_two_different_events_with_the_same_sequence_are_unknown(self):
        second = Event("two", "runtime", "b", 1, "tool")
        result = self.run_window([self.first, second], Heartbeat(100, 1))
        self.assertEqual(result["coverage"]["runtime"]["telemetry"], "unknown")

    def test_future_heartbeat_is_unknown(self):
        result = self.run_window([self.first], Heartbeat(101, 1))
        self.assertEqual(result["coverage"]["runtime"]["telemetry"], "unknown")

    def test_huge_high_water_mark_does_not_allocate_a_sequence_range(self):
        result = self.run_window([self.first], Heartbeat(100, 10**18))
        self.assertEqual(result["coverage"]["runtime"]["telemetry"], "unknown")

    def test_invalid_sequence_is_rejected(self):
        for sequence in (0, -1, True, 1.5):
            with self.subTest(sequence=sequence), self.assertRaises(ValueError):
                replace(self.first, sequence=sequence)

    def test_invalid_heartbeat_is_rejected(self):
        with self.assertRaises(ValueError):
            Heartbeat(100, -1)

    def test_negative_max_age_is_rejected(self):
        with self.assertRaises(ValueError):
            replay([], self.bindings, {}, now=100, max_age=-1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
