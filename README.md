# Agent evidence replay

Replay a recorded window of agent events to check attribution, parent links,
and missing telemetry. Runs locally with Python 3.10 or newer, using the standard
library.

Two agents can share a model API key. An agent can call a tool without calling a
model. A collector can stop sending events while its last recorded actions still
look normal. The fixtures make these cases easy to reproduce and inspect.

## Run it

No dependencies to install:

```sh
git clone https://github.com/ItsM0rty/agent-evidence-replay.git
cd agent-evidence-replay
python run_example.py examples/shared-key.json
python -m unittest -v
```

On Windows, `py -3` can be used in place of `python`.

The shared-key example attributes the two events to `calendar-agent` and
`mail-agent`, even though both carry the same credential label.

## Examples

| Fixture | Case |
| --- | --- |
| [Shared key](examples/shared-key.json) | Two agents using the same model credential. |
| [Delegation](examples/delegation.json) | A child tool action with its own actor and a linked parent. |
| [Tool only](examples/tool-only.json) | An action recorded without a model call. |
| [Telemetry gap](examples/telemetry-gap.json) | A recent heartbeat with a missing event in the sequence. |
| [Stale heartbeat](examples/stale-heartbeat.json) | Known past actions with no recent collector heartbeat. |
| [Claimed identity](examples/claimed-identity.json) | Agent-supplied names that disagree with session bindings. |

Each fixture has a matching expected output. [Example notes](examples/README.md)
explain the results. The tests also cover retries, out-of-order delivery,
conflicting event IDs, cyclic parent links, and invalid input.

## Input and output

A fixture contains `bindings`, `events`, `heartbeats`, and `now`. `max_age` is
optional and defaults to 30 seconds.

- **Bindings** map a collector and session to an agent and owner.
- **Events** carry a collector, session, event ID, sequence number, and kind.
  A `parent` refers to an event in the same collector. Optional `credential` and
  `claimed_agent` fields are fixture metadata and do not determine identity.
- **Heartbeats** carry a time and the last sequence emitted by that collector.
- **Time** is measured in integer seconds on one shared clock.

The result contains `observations` and collector `coverage`. An observation can
be `attributed` or `unknown`. Its parent link can be `linked`, `unknown`, or `none`.
Collector telemetry is `live` only when the heartbeat is recent and the supplied
window contains every sequence from 1 through its advertised last sequence.

Attribution and telemetry are separate. A received event can have a known actor
while the collector's remaining evidence is incomplete. A recent heartbeat with
sequence 0 represents an idle collector.

## Assumptions and limits

This is a reference implementation with synthetic fixtures. The caller supplies
events from an authenticated collector and session bindings from a trusted
control plane. Those bindings must be established outside the agent's control.
The code does not authenticate collectors, discover agents, instrument tools,
or enforce policy. A compromised collector can fabricate evidence.

`live` describes the received replay window. It does not establish that every
real action was recorded or that an agent is operating within policy. Tool-only
events need tool instrumentation at the source.

Event IDs and parent links are local to a collector. Exact retries are deduplicated;
conflicting IDs and missing sequences make telemetry unknown. Parent links across
owners are left unknown because this model has no delegation authorization record.
Links containing cycles are also left unknown.

Each input is one complete window starting at sequence 1. Collector restarts,
cross-collector traces, clock skew, persistent storage, and large-scale processing
are outside this model. The fixtures have not been compared with a commercial
product or run against production telemetry.

## Adapting the cases

Translate a connector's recorded events into the fixture format, then inspect the
attributed actors, parent links, and telemetry state. Keep the original source
evidence alongside the translated input so the mapping can be reviewed.

For a change, add a failing case and run `python -m unittest -v`. Tests make no
network requests. CI runs the same suite on Linux and Windows.

MIT licensed. See [LICENSE](LICENSE).
