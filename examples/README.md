# Replay examples

Each input has a matching `.expected.json` file containing the full output. The
test suite checks those files against the runner. All names and events are made up.

Run one example from the repository root:

```sh
python run_example.py examples/shared-key.json
```

| Input | What to look for in the output |
| --- | --- |
| `shared-key.json` | Two agents keep separate identities despite the same credential label. |
| `delegation.json` | The child action belongs to `mail-agent`, with `calendar-agent` as its parent. |
| `tool-only.json` | A tool event is attributed without any model event. |
| `telemetry-gap.json` | The heartbeat is recent, but sequence 2 is missing. Telemetry is `unknown`. |
| `stale-heartbeat.json` | Event attribution is retained, but the old heartbeat makes telemetry `unknown`. |
| `claimed-identity.json` | The registered session keeps its real identity. The unregistered session stays `unknown`. |

## Reading a result

The shared-key example returns two observations with different `agent` values:

```json
{
  "event": "two",
  "collector": "runtime",
  "kind": "model",
  "attribution": "attributed",
  "agent": "mail-agent",
  "owner": "alice",
  "parent_event": null,
  "parent_agent": null,
  "parent_link": "none"
}
```

The telemetry-gap example retains its two known observations and reports:

```json
{
  "runtime": {
    "telemetry": "unknown",
    "reason": "sequence_or_event_conflict"
  }
}
```

These answer different questions. An observed event can have a known actor while
the rest of the collector's window is incomplete. `unknown` does not erase the
events that were received.

`credential` contains a label for comparing fixtures, never an actual API key.
Times are integer seconds on one shared clock. The examples use `now: 100` and a
30-second heartbeat age limit so they produce the same result whenever they run.
