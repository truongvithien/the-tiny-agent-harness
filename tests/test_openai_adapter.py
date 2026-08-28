import json
from dataclasses import dataclass, field
from typing import Any

import pytest

from tiny_harness import (
    AcceptFinalAnswer,
    FinalAnswer,
    FunctionTool,
    JsonlEventSink,
    Observation,
    Risk,
    RiskPolicy,
    RunConfig,
    RunContext,
    Runner,
    RunStatus,
    ToolCall,
    ToolRegistry,
    ToolResult,
)
from tiny_harness.openai_adapter import (
    OpenAIModel,
    client_from_environment,
    decode_decision,
    openai_messages,
    openai_tools,
)


@dataclass(frozen=True)
class FakeFunction:
    name: str
    arguments: str


@dataclass(frozen=True)
class FakeToolCall:
    function: FakeFunction


@dataclass(frozen=True)
class FakeMessage:
    content: str | None = None
    tool_calls: tuple[FakeToolCall, ...] = ()


@dataclass(frozen=True)
class FakeChoice:
    message: FakeMessage


@dataclass(frozen=True)
class FakeResponse:
    choices: tuple[FakeChoice, ...]


@dataclass
class FakeCompletions:
    replies: list[FakeResponse]
    requests: list[dict[str, Any]] = field(default_factory=list)

    def create(self, **request: Any) -> FakeResponse:
        self.requests.append(request)
        if not self.replies:
            raise AssertionError("the fake client has no remaining replies")
        return self.replies.pop(0)


@dataclass
class FakeChat:
    completions: FakeCompletions


@dataclass
class FakeClient:
    chat: FakeChat

    @classmethod
    def with_replies(cls, *replies: FakeResponse) -> "FakeClient":
        return cls(chat=FakeChat(completions=FakeCompletions(replies=list(replies))))

    @property
    def requests(self) -> list[dict[str, Any]]:
        return self.chat.completions.requests


def text_reply(text: str) -> FakeResponse:
    return FakeResponse(choices=(FakeChoice(message=FakeMessage(content=text)),))


def tool_reply(name: str, arguments: str) -> FakeResponse:
    call = FakeToolCall(function=FakeFunction(name=name, arguments=arguments))
    return FakeResponse(
        choices=(FakeChoice(message=FakeMessage(tool_calls=(call,))),)
    )


def context(**overrides: Any) -> RunContext:
    values: dict[str, Any] = {
        "task": "Find the value",
        "acceptance_criteria": ("State the value",),
        "observations": (),
        "remaining_iterations": 3,
    }
    values.update(overrides)
    return RunContext(**values)


def test_openai_tools_translates_the_harness_specification() -> None:
    schema = {"type": "object", "properties": {"key": {"type": "string"}}}

    translated = openai_tools(
        [{"name": "lookup", "description": "Read a value.", "input_schema": schema}]
    )

    assert translated == [
        {
            "type": "function",
            "function": {
                "name": "lookup",
                "description": "Read a value.",
                "parameters": schema,
            },
        }
    ]


def test_openai_tools_returns_nothing_without_tools() -> None:
    assert openai_tools([]) == []


def test_openai_messages_carry_task_criteria_and_observations_in_order() -> None:
    messages = openai_messages(
        context(observations=(Observation(source="lookup", content="42"),))
    )

    assert [message["role"] for message in messages] == ["system", "user", "user"]
    assert "State the value" in messages[0]["content"]
    assert "Remaining iterations: 3" in messages[0]["content"]
    assert messages[1]["content"] == "Find the value"
    assert messages[2]["content"] == "Result from lookup:\n42"


def test_openai_messages_accept_a_custom_system_prompt() -> None:
    messages = openai_messages(context(), system_prompt="Be terse.")

    assert messages[0]["content"].startswith("Be terse.")


def test_decode_decision_reads_a_tool_call_with_json_arguments() -> None:
    decision = decode_decision(
        {
            "content": None,
            "tool_calls": [
                {"function": {"name": "lookup", "arguments": '{"key": "answer"}'}}
            ],
        }
    )

    assert decision == ToolCall("lookup", {"key": "answer"})


def test_decode_decision_accepts_arguments_already_decoded() -> None:
    decision = decode_decision(
        {"tool_calls": [{"function": {"name": "lookup", "arguments": {"key": "a"}}}]}
    )

    assert isinstance(decision, ToolCall)
    assert decision.arguments == {"key": "a"}


@pytest.mark.parametrize("raw", ["", None])
def test_decode_decision_treats_absent_arguments_as_empty(raw: object) -> None:
    decision = decode_decision(
        {"tool_calls": [{"function": {"name": "ping", "arguments": raw}}]}
    )

    assert isinstance(decision, ToolCall)
    assert decision.arguments == {}


def test_decode_decision_rejects_malformed_json_arguments() -> None:
    with pytest.raises(ValueError, match="malformed JSON"):
        decode_decision(
            {"tool_calls": [{"function": {"name": "lookup", "arguments": "{oops"}}]}
        )


def test_decode_decision_rejects_arguments_that_are_not_an_object() -> None:
    with pytest.raises(ValueError, match="must decode to an object"):
        decode_decision(
            {"tool_calls": [{"function": {"name": "lookup", "arguments": "[1, 2]"}}]}
        )


def test_decode_decision_rejects_a_nameless_tool_call() -> None:
    with pytest.raises(ValueError, match="missing a name"):
        decode_decision({"tool_calls": [{"function": {"arguments": "{}"}}]})


def test_decode_decision_reads_a_final_answer() -> None:
    assert decode_decision({"content": "The value is 42."}) == FinalAnswer(
        "The value is 42."
    )


def test_decode_decision_prefers_a_tool_call_over_accompanying_text() -> None:
    decision = decode_decision(
        {
            "content": "I will look it up.",
            "tool_calls": [{"function": {"name": "lookup", "arguments": "{}"}}],
        }
    )

    assert decision == ToolCall("lookup", {})


@pytest.mark.parametrize("message", [{}, {"content": "   "}, {"content": None}])
def test_decode_decision_rejects_an_empty_response(message: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="neither a tool call nor text"):
        decode_decision(message)


def test_decode_decision_rejects_a_non_mapping_message() -> None:
    with pytest.raises(TypeError, match="mapping"):
        decode_decision("nope")  # type: ignore[arg-type]


def test_model_sends_the_translated_request_and_returns_a_tool_call() -> None:
    client = FakeClient.with_replies(tool_reply("lookup", '{"key": "answer"}'))
    model = OpenAIModel(client=client, model="test-model")
    specs = [{"name": "lookup", "description": "Read.", "input_schema": {}}]

    decision = model.next_decision(context(), specs)

    assert decision == ToolCall("lookup", {"key": "answer"})
    request = client.requests[0]
    assert request["model"] == "test-model"
    assert request["tools"][0]["function"]["name"] == "lookup"
    assert request["messages"][1]["content"] == "Find the value"


def test_model_omits_the_tools_field_when_no_tools_exist() -> None:
    client = FakeClient.with_replies(text_reply("done"))

    OpenAIModel(client=client, model="test-model").next_decision(context(), [])

    assert "tools" not in client.requests[0]


def test_model_reports_a_response_without_choices() -> None:
    client = FakeClient.with_replies(FakeResponse(choices=()))

    with pytest.raises(ValueError, match="no choices"):
        OpenAIModel(client=client, model="test-model").next_decision(context(), [])


def test_model_drives_a_complete_harness_run(tmp_path) -> None:
    trace = tmp_path / "openai.jsonl"
    client = FakeClient.with_replies(
        tool_reply("lookup", '{"key": "answer"}'),
        text_reply("The value is 42."),
    )
    runner = Runner(
        model=OpenAIModel(client=client, model="test-model"),
        tools=ToolRegistry(
            [
                FunctionTool(
                    name="lookup",
                    description="Read a value.",
                    input_schema={"type": "object"},
                    risk=Risk.READ,
                    handler=lambda _: ToolResult(ok=True, output="42"),
                )
            ]
        ),
        policy=RiskPolicy(),
        approval=lambda _tool, _call: False,
        events=JsonlEventSink(trace, run_id="openai-contract"),
        verifier=AcceptFinalAnswer(),
        config=RunConfig(max_iterations=4),
    )

    result = runner.run("Find the value", ("State the value",))

    assert result.status is RunStatus.SUCCEEDED
    assert result.answer == "The value is 42."
    kinds = [json.loads(line)["kind"] for line in trace.read_text().splitlines()]
    assert kinds == [
        "run_started",
        "model_decision",
        "policy_decision",
        "tool_result",
        "model_decision",
        "verification",
        "run_finished",
    ]


def test_a_run_trace_never_contains_a_credential(tmp_path) -> None:
    trace = tmp_path / "openai.jsonl"
    secret = "sk-test-never-record-me"
    client = FakeClient.with_replies(text_reply("Done without any secret."))
    runner = Runner(
        model=OpenAIModel(client=client, model="test-model"),
        tools=ToolRegistry(),
        policy=RiskPolicy(),
        approval=lambda _tool, _call: False,
        events=JsonlEventSink(trace, run_id="openai-secret", secrets=(secret,)),
        verifier=AcceptFinalAnswer(),
        config=RunConfig(max_iterations=2),
    )

    result = runner.run(f"Ignore {secret}", ("Answer safely",))

    assert result.status is RunStatus.SUCCEEDED
    assert secret not in trace.read_text()


def test_client_from_environment_requires_a_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY is not set"):
        client_from_environment()
