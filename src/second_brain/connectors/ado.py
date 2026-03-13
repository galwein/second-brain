"""Azure DevOps work item hygiene checker.

Accepts work item data (from the ADO MCP server or any other source) and
checks items for completeness.  No subprocess / az CLI calls — Copilot
orchestrates fetching via the ADO MCP and pipes results here.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from html.parser import HTMLParser

logger = logging.getLogger("second-brain.connectors.ado")


class HTMLStripper(HTMLParser):
    """Strip HTML tags from ADO rich text fields."""

    def __init__(self):
        super().__init__()
        self.result: list[str] = []

    def handle_data(self, data):
        self.result.append(data)

    def get_text(self):
        return "".join(self.result).strip()


def strip_html(html: str) -> str:
    if not html:
        return ""
    stripper = HTMLStripper()
    stripper.feed(html)
    return stripper.get_text()


@dataclass
class HygieneIssue:
    """A single completeness issue found in a work item."""

    severity: str  # "error" or "warning"
    message: str


@dataclass
class WorkItemReview:
    """Review result for a single work item."""

    id: int
    title: str
    item_type: str  # Bug, Task
    state: str
    priority: int
    url: str
    issues: list[HygieneIssue] = field(default_factory=list)
    stale_days: int | None = None

    @property
    def has_issues(self) -> bool:
        return len(self.issues) > 0

    @property
    def score(self) -> str:
        errors = sum(1 for issue in self.issues if issue.severity == "error")
        warnings = sum(1 for issue in self.issues if issue.severity == "warning")
        if errors > 0:
            return "🔴"
        if warnings > 0:
            return "🟡"
        return "🟢"


@dataclass
class HygieneReport:
    """Full hygiene report for a sprint."""

    reviews: list[WorkItemReview] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.now)

    @property
    def items_with_issues(self) -> list[WorkItemReview]:
        return [review for review in self.reviews if review.has_issues]

    def format(self) -> str:
        items_with_issues = self.items_with_issues
        if not items_with_issues:
            return (
                f"🟢 **Sprint Hygiene Report** — All {len(self.reviews)} items look good!\n\n"
                f"Generated: {self.generated_at.strftime('%Y-%m-%d %H:%M')}"
            )

        lines = [
            f"🔍 **Sprint Hygiene Report** — {len(items_with_issues)}/{len(self.reviews)} items need attention\n",
            f"Generated: {self.generated_at.strftime('%Y-%m-%d %H:%M')}\n",
            "---\n",
        ]

        items_with_issues.sort(
            key=lambda review: (
                -sum(1 for issue in review.issues if issue.severity == "error"),
                review.priority,
            )
        )

        for review in items_with_issues:
            priority_label = {1: "P1", 2: "P2", 3: "P3", 4: "P4"}.get(review.priority, "")
            lines.append(
                f"{review.score} **{review.item_type} #{review.id}** ({priority_label} | {review.state}) "
                f"[{review.title}]({review.url})"
            )
            for issue in review.issues:
                icon = "❌" if issue.severity == "error" else "⚠️"
                lines.append(f"  {icon} {issue.message}")
            if review.stale_days and review.stale_days > 14:
                lines.append(f"  ⏰ No updates in {review.stale_days} days")
            lines.append("")

        total_errors = sum(
            1
            for review in items_with_issues
            for issue in review.issues
            if issue.severity == "error"
        )
        total_warnings = sum(
            1
            for review in items_with_issues
            for issue in review.issues
            if issue.severity == "warning"
        )
        lines.append("---")
        lines.append(
            f"**Summary:** {total_errors} errors, {total_warnings} warnings across {len(items_with_issues)} items"
        )
        lines.append(
            "\nReview each item and add missing information. Items that are clear enough don't need changes."
        )

        return "\n".join(lines)


def review_work_items(work_items: list[dict], stale_threshold_days: int = 14) -> HygieneReport:
    """Check a list of work items for hygiene issues.

    Accepts work items as dicts — typically piped in by Copilot from the
    ADO MCP server.  Each dict should have at minimum:
        id, title, work_item_type (Bug/Task), state, priority,
        url (optional), description (optional), repro_steps (optional),
        acceptance_criteria (optional), changed_date (optional, ISO 8601)
    """

    report = HygieneReport()

    for item in work_items:
        work_item_id = item.get("id", 0)
        title = item.get("title", "")
        item_type = item.get("work_item_type", item.get("type", ""))
        state = item.get("state", "")
        priority = item.get("priority", 0)
        if isinstance(priority, str):
            try:
                priority = int(priority)
            except ValueError:
                priority = 0
        url = item.get("url", "")
        description = strip_html(item.get("description", "") or "")
        repro_steps = strip_html(item.get("repro_steps", "") or "")
        acceptance = strip_html(item.get("acceptance_criteria", "") or "")
        changed_date_str = item.get("changed_date", "")

        if "placeholder" in title.lower():
            continue
        if item_type not in ("Bug", "Task"):
            continue

        review = WorkItemReview(
            id=work_item_id,
            title=title,
            item_type=item_type,
            state=state,
            priority=priority,
            url=url,
        )

        if changed_date_str:
            try:
                changed = datetime.fromisoformat(str(changed_date_str).replace("Z", "+00:00"))
                review.stale_days = (datetime.now(changed.tzinfo) - changed).days
            except (TypeError, ValueError):
                pass

        if item_type == "Bug":
            if not description and not repro_steps:
                review.issues.append(HygieneIssue("error", "Missing description and repro steps"))
            elif not description:
                review.issues.append(HygieneIssue("warning", "Missing description (has repro steps)"))

            if not repro_steps:
                review.issues.append(HygieneIssue("error", "Missing repro steps"))

            combined = f"{description} {repro_steps}".lower()
            if "expected" not in combined and "actual" not in combined:
                review.issues.append(HygieneIssue("warning", "No expected/actual behavior described"))

            has_evidence = any(
                keyword in combined
                for keyword in ["log", "error", "exception", "stack", "screenshot", "trace", "output"]
            )
            if not has_evidence:
                review.issues.append(HygieneIssue("warning", "No logs, errors, or evidence mentioned"))

        elif item_type == "Task":
            if not description:
                review.issues.append(HygieneIssue("error", "Missing description"))
            elif len(description) < 30:
                review.issues.append(
                    HygieneIssue("warning", "Description is very short — may need more detail")
                )

            if not acceptance:
                review.issues.append(HygieneIssue("warning", "No acceptance criteria defined"))

            if len(title) < 15 and "[" not in title:
                review.issues.append(
                    HygieneIssue("warning", "Title may be too vague — consider adding more detail")
                )

        if review.stale_days and review.stale_days > stale_threshold_days:
            review.issues.append(HygieneIssue("warning", f"No updates in {review.stale_days} days"))

        report.reviews.append(review)

    return report
