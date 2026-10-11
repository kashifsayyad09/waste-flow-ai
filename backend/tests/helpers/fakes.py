import json
from contextlib import asynccontextmanager

from app.ai.groq_service import Completion, GroqService, ToolCall
from app.ai.mcp_client import MCPUnavailable, ToolResult, ToolSpec
from app.ai.errors import AIError

TOOL_SPECS = [
    ToolSpec("get_bin_details", "Get one bin", {"type": "object", "properties": {"bin_id": {"type": "string"}}, "required": ["bin_id"]}),
    ToolSpec("get_critical_bins", "Critical bins", {"type": "object", "properties": {}}),
    ToolSpec("list_bins_by_priority", "List", {"type": "object", "properties": {"limit": {"type": "integer"}}}),
]


def tool_call(name: str, args: dict | str | None = None, call_id: str = "call_1") -> ToolCall:
    return ToolCall(id=call_id, name=name, arguments=args if isinstance(args, str) else json.dumps(args or {}))


class ScriptedGroq(GroqService):
    """Returns pre-scripted Completions (or raises scripted errors). Records every call."""

    def __init__(self, *script):
        self.script = list(script)
        self.calls: list[dict] = []

    async def complete(self, kind, messages, *, tools=None, max_tokens=700, temperature=0.1):
        self.calls.append({"kind": kind, "messages": [dict(m) for m in messages], "tools": tools})
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item(messages) if callable(item) else item


def say(text: str) -> Completion:
    return Completion(content=text, model="test-text-model")


def call(*calls: ToolCall) -> Completion:
    return Completion(content=None, tool_calls=list(calls), model="test-text-model")


class FakeMCP:
    """Stands in for MCPToolClient. handlers: tool name -> callable(args) -> dict | ToolResult | Exception."""

    configured = True

    def __init__(self, handlers=None, unavailable=False):
        self.handlers = handlers or {}
        self.unavailable = unavailable
        self.calls: list[tuple[str, dict]] = []

    @asynccontextmanager
    async def connect(self):
        if self.unavailable:
            raise MCPUnavailable("down")
        outer = self

        class Conn:
            async def list_tools(self):
                return TOOL_SPECS

            async def call_tool(self, name, arguments):
                outer.calls.append((name, arguments))
                result = outer.handlers[name](arguments)
                if isinstance(result, Exception):
                    raise result
                return result if isinstance(result, ToolResult) else ToolResult(False, json.dumps(result))

        yield Conn()


BIN_004 = {"bin_id": "BIN-004", "priority_score": 97, "priority_level": "CRITICAL", "fill_level_percent": 97, "reasons": ["97% full"]}
BIN_001 = {"bin_id": "BIN-001", "priority_score": 86, "priority_level": "CRITICAL", "fill_level_percent": 92, "reasons": ["92% full"]}
CRITICAL = {"matching_bins": 2, "bins": [BIN_004, BIN_001]}
