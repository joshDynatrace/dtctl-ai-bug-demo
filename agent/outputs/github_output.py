import os

import requests

from pipeline import FixPlan, IssueContext


def create_pull_request(issue_ctx: IssueContext, fix_plan: FixPlan) -> dict:
    token = os.getenv("GITHUB_TOKEN")
    if not issue_ctx.repo or not token or not fix_plan.branch:
        return {"status": "skipped", "reason": "missing repo, token, or branch"}

    title = fix_plan.pr_title or f"fix: agent investigation fix for issue #{issue_ctx.issue_number}"
    body = fix_plan.pr_body_markdown or (
        f"Automated fix by AI agent for issue #{issue_ctx.issue_number}.\n\n"
        f"**Root cause:** {fix_plan.root_cause}\n\n"
        f"**Confidence:** {fix_plan.confidence}"
    )
    url = f"https://api.github.com/repos/{issue_ctx.repo}/pulls"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = {"title": title, "body": body, "head": fix_plan.branch, "base": "main"}
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    data = response.json() if response.content else {}
    return {
        "status": response.status_code,
        "pr_url": data.get("html_url"),
        "pr_number": data.get("number"),
        "branch": fix_plan.branch,
        "response": response.text[:500],
    }


def post_issue_comment(issue_ctx: IssueContext, body: str) -> dict:
    token = os.getenv("GITHUB_TOKEN")
    if not issue_ctx.repo or not token or not issue_ctx.issue_number:
        return {"status": "skipped", "reason": "missing GitHub env or issue number"}

    url = f"https://api.github.com/repos/{issue_ctx.repo}/issues/{issue_ctx.issue_number}/comments"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    response = requests.post(url, headers=headers, json={"body": body}, timeout=30)
    return {"status": response.status_code, "response": response.text[:1000]}


def build_start_comment(issue_ctx: IssueContext) -> str:
    return (
        "AI investigation started.\n\n"
        f"- Problem: {issue_ctx.problem_id}\n"
        f"- Issue: {issue_ctx.issue_url}\n"
        "- Next steps: collect dtctl logs, capture Dynatrace Live Debugger evidence, propose fix, and update this issue.\n"
    )


def build_completion_comment(
    issue_ctx: IssueContext,
    fix_plan: FixPlan,
    pr_info: dict,
    evidence_summary: dict,
) -> str:
    lines = [
        "AI investigation completed.",
        "",
        f"- Problem: {issue_ctx.problem_id}",
        f"- Root cause: {fix_plan.root_cause}",
        f"- Confidence: {fix_plan.confidence}",
        f"- PR: {pr_info.get('pr_url', 'not created')}",
        f"- Evidence queries collected: {evidence_summary.get('query_count')}",
        f"- Live Debugger commands run: {evidence_summary.get('debugger_count')}",
        "",
        "Evidence summary:",
    ]

    for item in evidence_summary.get("queries", []):
        lines.append(
            f"- Query `{item.get('name')}` rc={item.get('returncode')} excerpt={item.get('stdout_excerpt')}"
        )

    for item in evidence_summary.get("debugger", []):
        lines.append(
            f"- Debugger `{item.get('cmd')}` rc={item.get('returncode')} excerpt={item.get('stdout_excerpt')}"
        )

    return "\n".join(lines)
