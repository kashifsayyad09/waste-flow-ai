"""Verify YOUR Groq account/config for WasteFlow AI. Run from backend/ with the venv active:

    python scripts/check_groq.py          # checks key + that the configured model IDs exist on your account
    python scripts/check_groq.py --live   # also makes two tiny real requests (tool calling + image input)

Reads GROQ_* from backend/.env or the environment. Never prints the API key. --live uses a few tokens.
Exit code 0 only if every check passed.
"""
import base64
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import groq  # noqa: E402
from PIL import Image  # noqa: E402

from app.config import get_settings  # noqa: E402


def main() -> int:
    s = get_settings()
    live = "--live" in sys.argv
    ok = True

    def report(passed: bool, label: str, detail: str = "") -> None:
        nonlocal ok
        ok = ok and passed
        print(f"[{'PASS' if passed else 'FAIL'}] {label}" + (f": {detail}" if detail else ""))

    report(s._set(s.groq_api_key.get_secret_value()), "GROQ_API_KEY is set")
    report(s._set(s.groq_text_model), "GROQ_TEXT_MODEL is set", s.groq_text_model if s._set(s.groq_text_model) else "")
    report(s._set(s.groq_vision_model), "GROQ_VISION_MODEL is set", s.groq_vision_model if s._set(s.groq_vision_model) else "")
    if not s._set(s.groq_api_key.get_secret_value()):
        return 1

    kwargs = {"base_url": s.groq_base_url} if s.groq_base_url.strip() else {}
    client = groq.Groq(api_key=s.groq_api_key.get_secret_value(), timeout=30, max_retries=0, **kwargs)
    try:
        available = {m.id for m in client.models.list().data}
        report(True, "API key accepted; models listed", f"{len(available)} models visible to this account")
    except groq.AuthenticationError:
        report(False, "API key accepted", "the key was rejected (401)")
        return 1
    except groq.APIError as exc:
        report(False, "Groq reachable", type(exc).__name__)
        return 1
    for label, model in (("text", s.groq_text_model.strip()), ("vision", s.groq_vision_model.strip())):
        if s._set(model):
            report(model in available, f"{label} model exists on your account", model)

    if live:
        if s._set(s.groq_text_model):
            tool = {"type": "function", "function": {"name": "ping", "description": "Check connectivity", "parameters": {"type": "object", "properties": {}}}}
            try:
                r = client.chat.completions.create(
                    model=s.groq_text_model.strip(), messages=[{"role": "user", "content": "Call the ping tool."}], tools=[tool],
                    tool_choice={"type": "function", "function": {"name": "ping"}}, max_tokens=50)
                called = bool(r.choices[0].message.tool_calls)
                report(called, "text model supports tool calling", "returned a tool call" if called else "answered without a tool call")
            except groq.APIStatusError as exc:
                report(False, "text model supports tool calling", f"HTTP {exc.status_code}: the model rejected tools or is unavailable")
        if s._set(s.groq_vision_model):
            buf = io.BytesIO()
            Image.new("RGB", (64, 64), (200, 30, 30)).save(buf, "JPEG")
            url = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
            try:
                r = client.chat.completions.create(
                    model=s.groq_vision_model.strip(), max_tokens=30,
                    messages=[{"role": "user", "content": [{"type": "text", "text": "What colour is this image? One word."},
                                                            {"type": "image_url", "image_url": {"url": url}}]}])
                report(bool(r.choices[0].message.content), "vision model accepts image input", (r.choices[0].message.content or "").strip()[:40])
            except groq.APIStatusError as exc:
                report(False, "vision model accepts image input", f"HTTP {exc.status_code}: the model rejected image input or is unavailable")
    else:
        print("(skipped tool-calling and image checks; add --live to run them)")
    print("\nAll checks passed." if ok else "\nSome checks FAILED.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
