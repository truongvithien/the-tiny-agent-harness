"""Small, explicit building blocks for an educational agent harness."""

from .types import (
    FinalAnswer,
    ModelDecision,
    Observation,
    PolicyDecision,
    Risk,
    RunContext,
    RunResult,
    RunStatus,
    ToolCall,
    ToolResult,
    VerificationResult,
)
from .tools import FunctionTool, Tool, ToolRegistry
from .policy import ApprovalCallback, Policy, RiskPolicy, authorize
from .events import Event, EventSink, JsonlEventSink, MemoryEventSink

__version__ = "0.1.0"

__all__ = [
    "FinalAnswer",
    "ModelDecision",
    "Observation",
    "PolicyDecision",
    "Risk",
    "RunContext",
    "RunResult",
    "RunStatus",
    "ToolCall",
    "ToolResult",
    "VerificationResult",
    "Tool",
    "FunctionTool",
    "ToolRegistry",
    "Policy",
    "RiskPolicy",
    "ApprovalCallback",
    "authorize",
    "Event",
    "EventSink",
    "JsonlEventSink",
    "MemoryEventSink",
    "__version__",
]
