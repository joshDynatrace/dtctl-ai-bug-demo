import json
import os
import re
from pathlib import Path

from pipeline import IssueContext


def load_issue_context() -> IssueContext:
    event_path = os.getenv("GITHUB_EVENT_PATH")
    if not event_path or not Path(event_path).exists():
        raise RuntimeError("GITHUB_EVENT_PATH is missing or invalid")
    event = json.loads(Path(event_path).read_text(encoding="utf-8"))
    issue = event.get("issue", {})
    body = issue.get("body", "") or ""
    title = issue.get("title", "") or ""
    return IssueContext(
        issue_number=issue.get("number"),
        issue_url=issue.get("html_url", ""),
        issue_title=title,
        issue_body=body,
        problem_id=_extract_problem_id(body, title),
        event_id=_extract_event_id(body, title),
        service_name=os.getenv("DEFAULT_SERVICE_NAME", ""),
        repo=os.getenv("GITHUB_REPOSITORY", ""),
        run_id=os.getenv("GITHUB_RUN_ID", ""),
        sha=os.getenv("GITHUB_SHA", ""),
    )


def _extract_problem_id(issue_body: str, issue_title: str = "") -> "str | None":
    source = f"{issue_title}\n{issue_body}"
    for pattern in [r"Problem:[*\s]*(P-\d+)", r"problem\.id\s*[:=]\s*(P-\d+)", r"\b(P-\d{3,})\b"]:
        match = re.search(pattern, source or "", re.IGNORECASE)
        if match:
            return match.group(1).upper()
    return None


def _extract_event_id(issue_body: str, issue_title: str = "") -> "str | None":
    source = f"{issue_title}\n{issue_body}"
    match = re.search(r"EventID:[*\s]*(-?\d+_\d+V2)", source or "", re.IGNORECASE)
    return match.group(1) if match else None
