"""PR Review Toolkit Plugin Hooks."""

from typing import Any


def auto_review_pr(context: dict[str, Any]) -> dict[str, Any]:
    """
    Automatically review new PRs.

    Triggered when a PR is opened.
    """
    pr_data = context.get("pr_data", {})
    pr_number = pr_data.get("number")

    if pr_number:
        context["auto_review"] = {
            "enabled": True,
            "pr_number": pr_number,
            "instruction": f"New PR #{pr_number} opened. Running automatic review.",
        }

    return context


def review_pr_changes(context: dict[str, Any]) -> dict[str, Any]:
    """
    Review PR when changes are pushed.

    Triggered when commits are added to an open PR.
    """
    pr_data = context.get("pr_data", {})
    pr_number = pr_data.get("number")
    new_commits = context.get("new_commits", [])

    if pr_number and new_commits:
        context["incremental_review"] = {
            "enabled": True,
            "pr_number": pr_number,
            "new_commits": len(new_commits),
            "instruction": f"PR #{pr_number} updated with {len(new_commits)} new commits. Reviewing changes.",
        }

    return context
