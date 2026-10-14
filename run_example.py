"""Run a JSON replay fixture without making network requests."""

import argparse
import json
import sys
from pathlib import Path

from replay import Event, Heartbeat, Principal, replay


def unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def load_fixture(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    if not isinstance(payload, dict):
        raise ValueError("fixture must be a JSON object")
    allowed = {"bindings", "events", "heartbeats", "now", "max_age"}
    unexpected = set(payload) - allowed
    if unexpected:
        raise ValueError(f"unknown fixture fields: {', '.join(sorted(unexpected))}")
    for field in ("bindings", "events"):
        if not isinstance(payload[field], list):
            raise ValueError(f"{field} must be an array")
    if not isinstance(payload["heartbeats"], dict):
        raise ValueError("heartbeats must be an object")
    bindings = {}
    for entry in payload["bindings"]:
        if set(entry) != {"collector", "session", "agent", "owner"}:
            raise ValueError("a binding needs collector, session, agent and owner")
        key = (entry["collector"], entry["session"])
        if any(not isinstance(item, str) or not item.strip() for item in key):
            raise ValueError("binding collector and session must be nonempty strings")
        if key in bindings:
            raise ValueError(f"duplicate binding for {key[0]}/{key[1]}")
        bindings[key] = Principal(entry["agent"], entry["owner"])
    events = [Event(**entry) for entry in payload["events"]]
    heartbeats = {
        collector: Heartbeat(**entry)
        for collector, entry in payload["heartbeats"].items()
    }
    return replay(events, bindings, heartbeats, now=payload["now"],
                  max_age=payload.get("max_age", 30))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path, help="path to a JSON input fixture")
    args = parser.parse_args()
    try:
        result = load_fixture(args.fixture)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Invalid fixture: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
