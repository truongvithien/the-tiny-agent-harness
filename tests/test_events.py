import json

from tiny_harness.events import EventSink, JsonlEventSink, MemoryEventSink


def test_memory_sink_assigns_monotonic_sequence_numbers() -> None:
    sink = MemoryEventSink(run_id="run-1")
    sink.record("run_started", {"task": "demo"})
    sink.record("run_finished", {"status": "succeeded"})
    assert [event.sequence for event in sink.events] == [1, 2]


def test_sink_redacts_secrets_and_truncates_long_strings() -> None:
    sink = MemoryEventSink(run_id="run-1", secrets=("secret-value",), max_string_length=8)
    sink.record("tool_result", {"token": "secret-value", "output": "abcdefghijk"})
    assert sink.events[0].payload == {
        "token": "[REDACTED]",
        "output": "abcdefgh…[TRUNCATED]",
    }


def test_sink_truncates_a_long_string_after_redacting_a_secret() -> None:
    sink = MemoryEventSink(run_id="run-1", secrets=("secret-value",), max_string_length=8)
    sink.record("tool_result", {"output": "secret-value abcdefghijk"})
    assert sink.events[0].payload == {"output": "[REDACTE…[TRUNCATED]"}


def test_jsonl_sink_writes_one_json_object_per_event(tmp_path) -> None:
    path = tmp_path / "trace.jsonl"
    sink = JsonlEventSink(path=path, run_id="run-1")
    sink.record("run_started", {"task": "demo"})
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert rows[0]["kind"] == "run_started"
    assert rows[0]["run_id"] == "run-1"


def test_sink_exposes_event_sink_count() -> None:
    sink: EventSink = MemoryEventSink(run_id="run-1")
    sink.record("run_started", {"task": "demo"})
    assert sink.count == 1


def test_memory_sink_copies_payload_at_record_boundary() -> None:
    payload = {"details": {"status": "original"}}
    sink = MemoryEventSink(run_id="run-1")
    sink.record("tool_result", payload)
    payload["details"]["status"] = "changed"
    assert sink.events[0].payload == {"details": {"status": "original"}}
