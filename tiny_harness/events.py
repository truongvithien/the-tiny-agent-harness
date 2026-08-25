from __future__ import annotations

from collections.abc import Mapping
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Protocol


@dataclass(frozen=True)
class Event:
    sequence: int
    timestamp: str
    run_id: str
    kind: str
    payload: Mapping[str, object]


class EventSink(Protocol):
    @property
    def count(self) -> int: ...

    def record(self, kind: str, payload: dict[str, object]) -> Event: ...


def _normalize(value: object, secrets: tuple[str, ...], limit: int) -> object:
    if isinstance(value, str):
        cleaned = value
        for secret in sorted(secrets, key=len, reverse=True):
            cleaned = cleaned.replace(secret, "[REDACTED]")
        if cleaned == "[REDACTED]":
            return cleaned
        return cleaned if len(cleaned) <= limit else cleaned[:limit] + "…[TRUNCATED]"
    if isinstance(value, Mapping):
        return MappingProxyType(
            {str(key): _normalize(item, secrets, limit) for key, item in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_normalize(item, secrets, limit) for item in value)
    return value


def _thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


class MemoryEventSink:
    def __init__(
        self,
        run_id: str,
        *,
        secrets: tuple[str, ...] = (),
        max_string_length: int = 10_000,
    ) -> None:
        self._run_id = run_id
        self._secrets = secrets
        self._max_string_length = max_string_length
        self._events: list[Event] = []

    @property
    def count(self) -> int:
        return len(self._events)

    @property
    def events(self) -> tuple[Event, ...]:
        return tuple(self._events)

    def record(self, kind: str, payload: dict[str, object]) -> Event:
        event = Event(
            sequence=self.count + 1,
            timestamp=datetime.now(UTC).isoformat(),
            run_id=self._run_id,
            kind=kind,
            payload=MappingProxyType(
                {
                    str(key): _normalize(value, self._secrets, self._max_string_length)
                    for key, value in payload.items()
                }
            ),
        )
        self._events.append(event)
        return event


class JsonlEventSink:
    def __init__(
        self,
        path: Path,
        run_id: str,
        *,
        secrets: tuple[str, ...] = (),
        max_string_length: int = 10_000,
    ) -> None:
        self._path = path
        self._memory = MemoryEventSink(
            run_id,
            secrets=secrets,
            max_string_length=max_string_length,
        )

    @property
    def count(self) -> int:
        return self._memory.count

    def record(self, kind: str, payload: dict[str, object]) -> Event:
        event = self._memory.record(kind, payload)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        serialized = {
            "sequence": event.sequence,
            "timestamp": event.timestamp,
            "run_id": event.run_id,
            "kind": event.kind,
            "payload": _thaw(event.payload),
        }
        with self._path.open("a", encoding="utf-8") as trace:
            trace.write(json.dumps(serialized, sort_keys=True) + "\n")
        return event
