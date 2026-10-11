"""A local stand-in for the Groq HTTP API (OpenAI-compatible /openai/v1/chat/completions).

Lets the REAL groq SDK run end to end in tests with no network and no paid calls.
Modes: chat (scripted tool-calling assistant), classify, rate_limit, unauthorized, bad_request, server_error, slow.
"""
import json
import socket
import threading
import time

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route


def _completion(message: dict, model: str) -> dict:
    return {"id": "chatcmpl-fake", "object": "chat.completion", "created": 0, "model": model,
            "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}


class FakeGroqServer:
    def __init__(self):
        self.mode = "chat"
        self.requests: list[dict] = []
        self.headers: list[dict] = []
        self.chat_tool = "get_critical_bins"
        self.chat_tool_args: dict = {}
        self.classify_reply = '{"category": "organic", "explanation": "Food scraps are visible."}'
        self.model_ids = ["fake-text", "fake-vision"]
        self.invented_id = None  # when set, the final chat answer mentions this (fake) bin ID
        self._server: uvicorn.Server | None = None
        self.port = 0

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    async def _handle(self, request: Request):
        body = await request.json()
        self.requests.append(body)
        self.headers.append(dict(request.headers))
        model = body.get("model", "")
        if self.mode == "unauthorized":
            return JSONResponse({"error": {"message": "Invalid API Key", "type": "invalid_request_error"}}, 401)
        if self.mode == "rate_limit":
            return JSONResponse({"error": {"message": "Rate limit reached", "type": "tokens"}}, 429, headers={"retry-after": "7"})
        if self.mode == "bad_request":
            return JSONResponse({"error": {"message": "model does not support image input", "type": "invalid_request_error"}}, 400)
        if self.mode == "server_error":
            return JSONResponse({"error": {"message": "boom", "type": "server_error"}}, 500)
        if self.mode == "slow":
            time.sleep(3)
        has_image = any(isinstance(m.get("content"), list) and any(p.get("type") == "image_url" for p in m["content"]) for m in body["messages"])
        if self.mode == "classify" or (self.mode == "chat" and has_image):
            return JSONResponse(_completion({"role": "assistant", "content": self.classify_reply}, model))
        # chat: first turn calls a tool, second turn answers from the tool output
        tool_msgs = [m for m in body["messages"] if m.get("role") == "tool"]
        if not tool_msgs:
            return JSONResponse(_completion({"role": "assistant", "content": None, "tool_calls": [
                {"id": "call_1", "type": "function",
                 "function": {"name": self.chat_tool, "arguments": json.dumps(self.chat_tool_args)}}]}, model))
        try:
            data = json.loads(tool_msgs[-1]["content"])
        except ValueError:
            data = {"error": "unreadable"}
        if "error" in data:
            text = "I could not verify that information because the data tool returned an error."
        else:
            bins = data.get("bins") or data.get("collection_order") or [data]
            text = "Verified from live data: " + "; ".join(
                f"{b['bin_id']} has priority {b['priority_score']} ({b['priority_level']})" for b in bins if "bin_id" in b)
        if self.invented_id:
            text += f" Also check {self.invented_id}."
        return JSONResponse(_completion({"role": "assistant", "content": text}, model))

    def start(self) -> "FakeGroqServer":
        if not self.port:
            with socket.socket() as s:
                s.bind(("127.0.0.1", 0))
                self.port = s.getsockname()[1]
        async def models(request: Request):
            return JSONResponse({"object": "list", "data": [{"id": m, "object": "model", "created": 0, "owned_by": "fake"} for m in self.model_ids]})

        app = Starlette(routes=[Route("/openai/v1/chat/completions", self._handle, methods=["POST"]),
                                Route("/openai/v1/models", models, methods=["GET"])])
        self._server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=self.port, log_level="error"))
        threading.Thread(target=self._server.run, daemon=True).start()
        for _ in range(100):
            if self._server.started:
                return self
            time.sleep(0.05)
        raise RuntimeError("fake Groq server did not start")

    def stop(self) -> None:
        if self._server:
            self._server.should_exit = True
