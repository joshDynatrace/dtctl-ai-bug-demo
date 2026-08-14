#!/usr/bin/env python3
import json
import os
import signal
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

SCRIPT_DIR = Path(__file__).resolve().parent
SUBPROCESS_TIMEOUT = int(os.getenv("AGENT_SUBPROCESS_TIMEOUT", "1500"))  # 25 min

REQUIRED_PLACEHOLDERS = [
    "{{ISSUE_JSON}}",
    "{{EVIDENCE_JSON}}",
    "{{DTCTL_SKILL_CONTEXT}}",
    "{{DTCTL_LIVE_DEBUGGER_CONTEXT}}",
    "{{PR_CREATION_INSTRUCTIONS}}",
]


@dataclass
class IssueContext:
    issue_number: Optional[int] = None
    issue_url: str = ""
    issue_title: str = ""
    issue_body: str = ""
    problem_id: Optional[str] = None
    event_id: Optional[str] = None
    service_name: str = ""
    repo: str = ""
    run_id: str = ""
    sha: str = ""

    def to_dict(self) -> dict:
        return {
            "issue_number": self.issue_number,
            "issue_url": self.issue_url,
            "issue_title": self.issue_title,
            "issue_body": self.issue_body,
            "problem_id": self.problem_id,
            "event_id": self.event_id,
            "service_name": self.service_name,
            "repo": self.repo,
            "run_id": self.run_id,
            "sha": self.sha,
        }


@dataclass
class FixPlan:
    root_cause: str = ""
    confidence: float = 0.0
    evidence: list = field(default_factory=list)
    fix_strategy: str = ""
    code_changes: list = field(default_factory=list)
    pr_url: Optional[str] = None
    pr_number: Optional[int] = None
    pr_title: Optional[str] = None
    pr_body_markdown: Optional[str] = None
    branch: Optional[str] = None
    ok: bool = True
    error: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "FixPlan":
        return cls(
            root_cause=data.get("root_cause", ""),
            confidence=data.get("confidence", 0.0),
            evidence=data.get("evidence", []),
            fix_strategy=data.get("fix_strategy", ""),
            code_changes=data.get("code_changes", []),
            pr_url=data.get("pr_url"),
            pr_number=data.get("pr_number"),
            pr_title=data.get("pr_title"),
            pr_body_markdown=data.get("pr_body_markdown"),
            branch=data.get("branch"),
        )

    @classmethod
    def failed(cls, reason: str) -> "FixPlan":
        return cls(
            root_cause=f"Investigation did not complete: {reason}",
            ok=False,
            error=reason,
        )

    def to_dict(self) -> dict:
        return {
            "root_cause": self.root_cause,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "fix_strategy": self.fix_strategy,
            "code_changes": self.code_changes,
            "pr_url": self.pr_url,
            "pr_number": self.pr_number,
            "branch": self.branch,
        }


def _env_flag(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _render_prompt(template: str, context: dict) -> str:
    for key in REQUIRED_PLACEHOLDERS:
        if key not in template:
            raise ValueError(f"Prompt template missing placeholder: {key}")
    result = template
    for placeholder, value in context.items():
        result = result.replace(placeholder, value)
    return result


def build_agent_prompt(issue_ctx: IssueContext, investigation_state: dict, auto_pr: bool = False) -> str:
    template_path = SCRIPT_DIR / "templates" / "agent_prompt.md"
    prompt_template = template_path.read_text(encoding="utf-8")

    if auto_pr:
        pr_instructions = (
            f"After finalizing the root cause and fix, you MUST push your changes to GitHub:\n"
            f"1. Create a new branch named: agent/fix-{issue_ctx.issue_number}\n"
            f"2. Make the necessary code changes based on your analysis\n"
            f"3. Commit the changes with a descriptive message including the root cause\n"
            f"4. Push the branch to GitHub\n"
            f"Do NOT attempt to create a pull request — the orchestrator will handle PR creation automatically.\n"
            f"Include the branch name, pr_title, and pr_body_markdown in your final JSON response."
        )
    else:
        pr_instructions = "PR creation is disabled (AUTO_PR not set)."

    return _render_prompt(
        prompt_template,
        {
            "{{ISSUE_JSON}}": json.dumps(issue_ctx.to_dict(), indent=2),
            "{{EVIDENCE_JSON}}": json.dumps(investigation_state, indent=2),
            "{{DTCTL_SKILL_CONTEXT}}": (
                "Use dtctl directly during investigation. You are expected to choose commands dynamically, "
                "execute them, and iterate until root cause confidence is high."
            ),
            "{{DTCTL_LIVE_DEBUGGER_CONTEXT}}": (
                "Use Dynatrace Live Debugger commands through dtctl when needed. "
                "Collect concrete variable-value evidence before finalizing."
            ),
            "{{PR_CREATION_INSTRUCTIONS}}": pr_instructions,
        },
    )


def _run_subprocess(prompt_file_path: str) -> dict:
    runner = SCRIPT_DIR / "agent_sdk_runner.py"
    trace_enabled = _env_flag("AGENT_TRACE", False)

    if trace_enabled:
        proc = subprocess.Popen(
            [sys.executable, str(runner), prompt_file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=str(SCRIPT_DIR),
            start_new_session=True,
        )

        stderr_lines = []

        def _drain_stderr():
            for line in proc.stderr:
                stderr_lines.append(line)
                print(line, end="", file=sys.stderr, flush=True)

        t = threading.Thread(target=_drain_stderr, daemon=True)
        t.start()

        try:
            returncode = proc.wait(timeout=SUBPROCESS_TIMEOUT)
        except subprocess.TimeoutExpired:
            print(
                f"Agent subprocess timed out after {SUBPROCESS_TIMEOUT}s — killing process group",
                file=sys.stderr,
                flush=True,
            )
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except Exception:
                proc.kill()
            returncode = proc.wait()

        t.join(timeout=5)
        stdout_text = proc.stdout.read() if proc.stdout is not None else ""
        # Strip [agent-trace] lines so they don't pollute the error message on failure.
        stderr_text = "\n".join(
            l.rstrip() for l in stderr_lines if not l.startswith("[agent-trace]")
        ).strip()
    else:
        try:
            proc = subprocess.run(
                [sys.executable, str(runner), prompt_file_path],
                capture_output=True,
                text=True,
                cwd=str(SCRIPT_DIR),
                timeout=SUBPROCESS_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "error": f"Agent subprocess timed out after {SUBPROCESS_TIMEOUT}s",
                "result": FixPlan.failed(f"Timed out after {SUBPROCESS_TIMEOUT}s").to_dict(),
            }
        stdout_text = proc.stdout
        stderr_text = proc.stderr.strip()
        returncode = proc.returncode

    if returncode != 0:
        error_text = stderr_text or f"Runner failed with exit code {returncode}."
        return {"ok": False, "error": error_text, "result": FixPlan.failed(error_text).to_dict()}

    try:
        parsed = json.loads((stdout_text or "").strip())
        if isinstance(parsed, dict):
            return {"ok": True, "error": "", "result": parsed}
        return {
            "ok": False,
            "error": "Runner output was not a JSON object",
            "result": FixPlan.failed("Runner output was not a JSON object").to_dict(),
        }
    except json.JSONDecodeError:
        return {
            "ok": False,
            "error": "Runner output was not valid JSON",
            "result": FixPlan.failed("Runner output was not valid JSON").to_dict(),
        }


def run_investigation(issue_ctx: IssueContext, output_dir: Path, auto_pr: bool = False) -> tuple:
    """Pure investigation pipeline. No GitHub or Dynatrace output. Returns (FixPlan, investigation_result dict)."""
    investigation_state = {
        "notes": [
            "Choose and run dtctl commands dynamically based on issue details.",
            "Only finalize when root cause evidence is concrete.",
        ],
    }

    started_at = datetime.now(timezone.utc).isoformat()
    prompt = build_agent_prompt(issue_ctx, investigation_state, auto_pr)
    prompt_path = output_dir / "agent_prompt.md"
    prompt_path.write_text(prompt, encoding="utf-8")
    (output_dir / "agent_prompt_rendered.md").write_text(prompt, encoding="utf-8")

    cmd_result = _run_subprocess(str(prompt_path))
    fix_plan_dict = cmd_result.get("result") or FixPlan.failed("Empty result from runner").to_dict()
    fix_plan = FixPlan.from_dict(fix_plan_dict)
    fix_plan.ok = cmd_result.get("ok", False)
    fix_plan.error = cmd_result.get("error", "")

    investigation_result = {
        "started_at": started_at,
        "ok": cmd_result.get("ok", False),
        "error": cmd_result.get("error", ""),
        "result": fix_plan.to_dict(),
        "ended_at": datetime.now(timezone.utc).isoformat(),
    }
    return fix_plan, investigation_result


def summarize_evidence(fix_plan: FixPlan) -> dict:
    evidence_items = fix_plan.evidence if isinstance(fix_plan.evidence, list) else []
    excerpt_max_len = int(os.getenv("EVIDENCE_EXCERPT_MAX_LEN", "4000"))

    def _safe(value, max_len=1800):
        text = str(value or "")
        return text if len(text) <= max_len else text[: max_len - 3] + "..."

    query_summaries = []
    debugger_summaries = []
    for item in evidence_items:
        detail = _safe(item.get("detail", ""), max_len=excerpt_max_len)
        evidence_type = str(item.get("type", "")).lower()
        if evidence_type == "snapshot":
            debugger_summaries.append({"cmd": "agent_collected_snapshot", "returncode": 0, "stdout_excerpt": detail})
        else:
            query_summaries.append({"name": evidence_type or "evidence", "returncode": 0, "stdout_excerpt": detail})

    return {
        "query_count": len(query_summaries),
        "debugger_count": len(debugger_summaries),
        "queries": query_summaries,
        "debugger": debugger_summaries,
    }
