# Agent evidence replay

Replay a recorded window of agent events to check attribution, parent links,
and missing telemetry. Runs locally with Python 3.10 or newer, using the standard
library.

Session bindings come from a trusted collector or control plane. Model API keys
and names supplied by agents are not used as identity. A recent heartbeat and a
complete sequence describe the evidence received from a collector; they do not
prove that every real action was recorded.

This is a reference implementation for synthetic tests. It does not collect
events, discover agents, authenticate a collector, or enforce policy.
