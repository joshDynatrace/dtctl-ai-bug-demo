#!/usr/bin/env python3
import asyncio
from datetime import datetime, timezone
import json
import os
import re
import sys
from pathlib import Path

try:
    from claude_agent_sdk import query, ClaudeAgentOptions
except ImportError:
    print(json.dumps({
        "root_cause": "claude_agent_sdk not installed: pip install claude-agent-sdk",
        "confidence": 0.0,
        "evidence": [],
    }))
    sys.exit(1)

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / "investigation_output"
DEFAULT_MODEL = "claude-sonnet-4-6"
# Maximum number of agentic turns before the SDK forcibly stops the session.
MAX_TURNS = 100


def _env_flag(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _short_text(value, max_len=220):
    text = str(value or "")
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


class TraceLogger:
    def __init__(self, enabled=False, trace_file=None):
        self.enabled = enabled
        self.trace_file = trace_file
        self._handle = None
        if self.enabled and self.trace_file:
            path = Path(self.trace_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            self._handle = path.open("a", encoding="utf-8")

    def log(self, event, **data):
        if not self.enabled:
            return
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **data,
        }
        line = json.dumps(payload, ensure_ascii=True)
        print(f"[agent-trace] {line}", file=sys.stderr, flush=True)
        if self._handle:
            self._handle.write(line + "\n")
            self._handle.flush()

    def close(self):
        if self._handle:
            self._handle.close()


def _extract_json(text):
    text = text.strip()
    if not text:
        raise ValueError("Empty output")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
    if match:
        return json.loads(match.group(1))
    match = re.search(r"(\{[\s\S]*\})", text)
    if match:
        return json.loads(match.group(1))
    raise ValueError("No JSON object in agent output")


def _fallback(reason):
    return {
        "root_cause": f"Agent SDK runner error: {reason}",
        "confidence": 0.0,
        "evidence": [],
    }


def _extract_text_from_tool_result(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text", "")))
            else:
                parts.append(str(item))
        return "\n".join([part for part in parts if part])
    return str(content or "")


async def _run(prompt_text, trace):
    # Configure one agent session from env-driven runtime options.
    model = os.getenv("CLAUDE_MODEL", DEFAULT_MODEL)
    tools = [t.strip() for t in os.getenv("AGENT_ALLOWED_TOOLS", "Bash,Read").split(",") if t.strip()]
    cwd = os.getenv("AGENT_CWD", str(SCRIPT_DIR.parent))
    include_partial = _env_flag("AGENT_TRACE_INCLUDE_PARTIAL", False)
    result_text = None

    # Emit a trace marker so operators can correlate later events to a run.
    trace.log(
        "session_start",
        model=model,
        cwd=cwd,
        include_partial_messages=include_partial,
    )

    # Stream all agent SDK messages and convert them into compact trace events.
    async for message in query(
        prompt=prompt_text,
        options=ClaudeAgentOptions(
            allowed_tools=tools,
            model=model,
            permission_mode="bypassPermissions",
            max_turns=MAX_TURNS,
            cwd=cwd,
            include_partial_messages=include_partial,
        ),
    ):
        msg_type = message.__class__.__name__
        session_id = getattr(message, "session_id", None)

        # Assistant blocks are where tool requests, tool results, and text analysis appear.
        if msg_type == "AssistantMessage":
            for block in getattr(message, "content", []):
                block_type = block.__class__.__name__
                if block_type == "ToolUseBlock":
                    trace.log(
                        "tool_use",
                        session_id=session_id,
                        tool=getattr(block, "name", ""),
                        input=_short_text(json.dumps(getattr(block, "input", {}), ensure_ascii=True), max_len=700),
                    )
                elif block_type == "ToolResultBlock":
                    tool_output = _extract_text_from_tool_result(getattr(block, "content", ""))
                    trace.log(
                        "tool_result",
                        session_id=session_id,
                        tool_use_id=getattr(block, "tool_use_id", ""),
                        is_error=getattr(block, "is_error", False),
                        output_excerpt=_short_text(tool_output, max_len=900),
                    )
                elif block_type == "TextBlock":
                    trace.log(
                        "assistant_text",
                        session_id=session_id,
                        text_excerpt=_short_text(getattr(block, "text", ""), max_len=300),
                    )

        # Background tasks (if any) surface progress through dedicated task messages.
        if msg_type in {"TaskStartedMessage", "TaskProgressMessage", "TaskNotificationMessage"}:
            trace.log(
                "task_event",
                session_id=session_id,
                type=msg_type,
                task_id=getattr(message, "task_id", ""),
                status=getattr(message, "status", ""),
                description=_short_text(getattr(message, "description", ""), max_len=300),
                last_tool_name=getattr(message, "last_tool_name", ""),
            )

        # System messages expose SDK/session metadata like init payloads.
        if msg_type == "SystemMessage":
            trace.log(
                "system_message",
                session_id=session_id,
                subtype=getattr(message, "subtype", ""),
                data=_short_text(json.dumps(getattr(message, "data", {}), ensure_ascii=True), max_len=600),
            )

        # Capture the final model result text for JSON parsing by the caller.
        if hasattr(message, "result"):
            result_text = message.result
            trace.log(
                "result_message",
                session_id=session_id,
                subtype=getattr(message, "subtype", ""),
                is_error=getattr(message, "is_error", False),
                num_turns=getattr(message, "num_turns", None),
                duration_ms=getattr(message, "duration_ms", None),
                total_cost_usd=getattr(message, "total_cost_usd", None),
                result_excerpt=_short_text(result_text, max_len=500),
            )

    # Mark completion even when no parseable result is produced.
    trace.log("session_end")
    return result_text


def main():
    # Initialize optional trace sinks (stderr and/or JSONL file).
    trace_enabled = _env_flag("AGENT_TRACE", False)
    trace_file = os.getenv("AGENT_TRACE_FILE", "").strip()
    if trace_enabled and not trace_file:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        trace_file = str(OUTPUT_DIR / "agent_trace.jsonl")
    trace = TraceLogger(enabled=trace_enabled, trace_file=trace_file or None)

    # Validate required CLI argument: a rendered prompt file path.
    if len(sys.argv) < 2:
        print(json.dumps(_fallback("Usage: agent_sdk_runner.py <prompt_file>")))
        trace.close()
        sys.exit(1)

    prompt_path = Path(sys.argv[1])
    if not prompt_path.exists():
        print(json.dumps(_fallback(f"Prompt file not found: {prompt_path}")))
        trace.close()
        sys.exit(1)

    # Read prompt content once, then execute a single SDK investigation session.
    prompt_text = prompt_path.read_text(encoding="utf-8")

    try:
        result_text = asyncio.run(_run(prompt_text, trace))
    except Exception as e:
        trace.log("runner_exception", error=str(e))
        print(json.dumps(_fallback(str(e))))
        trace.close()
        sys.exit(1)

    # Ensure orchestrator always receives a JSON object, even on empty output.
    if not result_text:
        print(json.dumps(_fallback("Agent returned no result")))
        trace.close()
        sys.exit(0)

    # Parse flexible model output into the strict JSON contract expected upstream.
    try:
        parsed = _extract_json(result_text)
    except Exception as e:
        trace.log("parse_error", error=str(e))
        print(json.dumps(_fallback(f"Could not parse output as JSON: {e}")))
        trace.close()
        sys.exit(0)

    # Print final machine-readable result to stdout; trace logs stay on stderr/file.
    print(json.dumps(parsed))
    trace.close()


if __name__ == "__main__":
    main()
