#!/usr/bin/env python3
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from outputs.dynatrace_output import post_dynatrace_event
from outputs.github_output import build_completion_comment, build_start_comment, create_pull_request, post_issue_comment
from pipeline import run_investigation, summarize_evidence
from triggers.github_trigger import load_issue_context

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / "investigation_output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _env_flag(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _now_utc():
    return datetime.now(timezone.utc).isoformat()


def _persist(name, data):
    path = OUTPUT_DIR / name
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _extract_pr_info(fix_plan, auto_pr: bool) -> dict:
    if not auto_pr:
        return {"status": "skipped", "reason": "AUTO_PR=false"}
    if fix_plan.pr_url:
        return {"status": "created", "pr_url": fix_plan.pr_url, "pr_number": fix_plan.pr_number, "branch": fix_plan.branch}
    return {
        "status": "pending",
        "reason": "Agent did not include PR details in response. This may indicate PR creation succeeded silently or encountered an issue.",
    }


def main():
    # ===============================================================================
    # 1. INTAKE: Load issue context from the trigger source (GitHub by default)
    # ===============================================================================
    issue_ctx = load_issue_context()
    _persist("issue_context.json", issue_ctx.to_dict())

    if not issue_ctx.problem_id:
        raise RuntimeError("Could not extract Dynatrace problem ID from the issue body/title")

    # ========================================================================
    # 2. NOTIFY: Post "investigation started" comment on the GitHub issue
    # ========================================================================
    start_comment_result = post_issue_comment(issue_ctx, build_start_comment(issue_ctx))
    _persist("issue_start_comment_result.json", start_comment_result)

    # ========================================================================
    # 3. INVESTIGATE: Single handoff to agent runtime (agent chooses dtctl)
    # ========================================================================
    auto_pr = _env_flag("AUTO_PR", False)
    fix_plan, investigation_result = run_investigation(issue_ctx, OUTPUT_DIR, auto_pr)
    _persist("fix_plan.json", fix_plan.to_dict())
    _persist("investigation_result.json", investigation_result)
    evidence_summary = summarize_evidence(fix_plan)
    _persist("evidence_summary.json", evidence_summary)

    # ========================================================================
    # 4. CREATE PR (optional): Orchestrator creates PR via GitHub API
    # ========================================================================
    pr_result = {}
    if auto_pr and fix_plan.branch:
        pr_result = create_pull_request(issue_ctx, fix_plan)
        _persist("pr_result.json", pr_result)
        if pr_result.get("pr_url"):
            fix_plan.pr_url = pr_result["pr_url"]
            fix_plan.pr_number = pr_result["pr_number"]

    pr_info = _extract_pr_info(fix_plan, auto_pr)
    _persist("pr_info.json", pr_info)

    # ========================================================================
    # 5. REPORT RESULTS: Post completion comment with evidence summary
    # ========================================================================
    comment_body = build_completion_comment(issue_ctx, fix_plan, pr_info, evidence_summary)
    comment_result = post_issue_comment(issue_ctx, comment_body)
    _persist("issue_comment_result.json", comment_result)

    # ========================================================================
    # 6. UPDATE DYNATRACE: Post investigation event linked to problem ID
    # ========================================================================
    dt_event_result = post_dynatrace_event(issue_ctx, fix_plan, pr_info, evidence_summary)
    _persist("dynatrace_event_result.json", dt_event_result)

    # ========================================================================
    # 7. FINALIZE: Persist summary and output to stdout for CI logging
    # ========================================================================
    summary = {
        "issue_context": issue_ctx.to_dict(),
        "fix_plan": fix_plan.to_dict(),
        "pr_info": pr_info,
        "investigation_result": investigation_result,
        "evidence_summary": evidence_summary,
        "start_comment_result": start_comment_result,
        "comment_result": comment_result,
        "dynatrace_event_result": dt_event_result,
        "finished_at": _now_utc(),
    }
    _persist("summary.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as err:
        print(f"orchestrator failed: {err}", file=sys.stderr)
        sys.exit(1)
