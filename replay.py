"""Local evidence replay. Inputs must come from an authenticated collector."""

from dataclasses import dataclass
from typing import Mapping, Sequence


def _text(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a nonempty string")


def _integer(value: int, field: str, minimum: int = 0) -> None:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{field} must be an integer >= {minimum}")


@dataclass(frozen=True)
class Principal:
    agent: str
    owner: str

    def __post_init__(self) -> None:
        _text(self.agent, "agent")
        _text(self.owner, "owner")


@dataclass(frozen=True)
class Event:
    id: str
    collector: str
    session: str
    sequence: int
    kind: str
    credential: str = ""
    parent: str | None = None
    claimed_agent: str | None = None

    def __post_init__(self) -> None:
        for field in ("id", "collector", "session", "kind"):
            _text(getattr(self, field), field)
        _integer(self.sequence, "sequence", 1)
        if not isinstance(self.credential, str):
            raise ValueError("credential must be a string")
        for field in ("parent", "claimed_agent"):
            value = getattr(self, field)
            if value is not None:
                _text(value, field)


@dataclass(frozen=True)
class Heartbeat:
    at: int
    last_sequence: int

    def __post_init__(self) -> None:
        _integer(self.at, "heartbeat time")
        _integer(self.last_sequence, "last_sequence")


def replay(
    events: Sequence[Event],
    bindings: Mapping[tuple[str, str], Principal],
    heartbeats: Mapping[str, Heartbeat],
    *,
    now: int,
    max_age: int = 30,
) -> dict:
    """Attribute observed events; assess transport evidence, not agent safety.

    Bindings are collector-established session identities, not agent-supplied
    names. Each collector's input is a complete replay window starting at
    sequence 1. The heartbeat supplies the last emitted sequence in that window.
    A live heartbeat alone cannot prove that every real action was instrumented.
    """
    _integer(now, "now")
    _integer(max_age, "max_age")
    trusted = {collector for collector, _ in bindings}
    by_id: dict[tuple[str, str], Event] = {}
    conflicts: set[tuple[str, str]] = set()
    for event in events:
        key = (event.collector, event.id)
        if key in by_id and event != by_id[key]:
            conflicts.add(key)
        else:
            by_id[key] = event

    def principal(event: Event) -> Principal | None:
        if (event.collector, event.id) in conflicts:
            return None
        return bindings.get((event.collector, event.session))

    def cyclic_parent_chain(event: Event) -> bool:
        seen: set[tuple[str, str]] = set()
        current: Event | None = event
        while current:
            key = (current.collector, current.id)
            if key in seen:
                return True
            seen.add(key)
            current = (
                by_id.get((current.collector, current.parent))
                if current.parent else None
            )
        return False

    observations = []
    for event in by_id.values():
        actor = principal(event)
        parent_event = (
            by_id.get((event.collector, event.parent)) if event.parent else None
        )
        parent_actor = principal(parent_event) if parent_event else None
        # Parent linkage is evidence supplied by the trusted collector. Do not
        # infer delegation from two events sharing a credential or timestamp.
        parent_valid = bool(
            actor and parent_actor and parent_actor.owner == actor.owner
            and not cyclic_parent_chain(event)
        )
        observations.append({
            "event": event.id,
            "collector": event.collector,
            "kind": event.kind,
            "attribution": "attributed" if actor else "unknown",
            "agent": actor.agent if actor else None,
            "owner": actor.owner if actor else None,
            "parent_event": event.parent if parent_valid else None,
            "parent_agent": parent_actor.agent if parent_valid else None,
            "parent_link": (
                "linked" if parent_valid else "unknown" if event.parent else "none"
            ),
        })

    coverage = {}
    for collector in sorted(trusted):
        heartbeat = heartbeats.get(collector)
        relevant = [event for event in events if event.collector == collector]
        sequences: dict[int, Event] = {}
        sequence_conflict = False
        for event in relevant:
            previous = sequences.get(event.sequence)
            if previous is not None and previous != event:
                sequence_conflict = True
            sequences[event.sequence] = event
        fresh = bool(heartbeat and 0 <= now - heartbeat.at <= max_age)
        complete = False
        if heartbeat and heartbeat.last_sequence >= 0:
            # Compare sorted positions without allocating a huge range from an
            # untrusted high-water mark. Exact retries count only once.
            observed = sorted(sequences)
            complete = (
                len(observed) == heartbeat.last_sequence
                and all(seq == index + 1 for index, seq in enumerate(observed))
                and not sequence_conflict
                and not any(
                    (event.collector, event.id) in conflicts for event in relevant
                )
            )
        coverage[collector] = {
            "telemetry": "live" if fresh and complete else "unknown",
            "reason": (
                "complete_observed_window" if fresh and complete
                else "missing_or_stale_heartbeat" if not fresh
                else "sequence_or_event_conflict"
            ),
        }
    return {"observations": observations, "coverage": coverage}
