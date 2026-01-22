"""
Commit Commands Plugin Tools.

Git commit automation with conventional commits support.
"""

import re
from typing import Any


COMMIT_TYPES = {
    "feat": "A new feature",
    "fix": "A bug fix",
    "docs": "Documentation only changes",
    "style": "Changes that do not affect the meaning of the code",
    "refactor": "A code change that neither fixes a bug nor adds a feature",
    "test": "Adding missing tests or correcting existing tests",
    "chore": "Changes to the build process or auxiliary tools",
    "perf": "A code change that improves performance",
    "ci": "Changes to CI configuration files and scripts",
    "build": "Changes that affect the build system or external dependencies",
    "revert": "Reverts a previous commit",
}


def generate_commit_message(
    diff: str,
    type: str | None = None,
    scope: str | None = None,
) -> dict[str, Any]:
    """
    Generate a commit message based on staged changes.

    Args:
        diff: Git diff of staged changes
        type: Conventional commit type
        scope: Commit scope

    Returns:
        Generated commit message
    """
    # Analyze diff to determine type if not provided
    if not type:
        analysis = analyze_changes(diff)
        type = analysis.get("suggested_type", "chore")
        if not scope:
            scope = analysis.get("suggested_scope")

    # Extract key changes from diff
    added_files = []
    modified_files = []
    deleted_files = []

    for line in diff.split("\n"):
        if line.startswith("+++ b/"):
            file_path = line[6:]
            if "new file" in diff[:diff.index(line)].split("diff --git")[-1]:
                added_files.append(file_path)
            else:
                modified_files.append(file_path)
        elif line.startswith("deleted file"):
            # Get the file from the previous line
            pass

    # Count changes
    additions = len(re.findall(r"^\+[^+]", diff, re.MULTILINE))
    deletions = len(re.findall(r"^-[^-]", diff, re.MULTILINE))

    # Generate message based on changes
    if len(added_files) == 1 and not modified_files:
        subject = f"Add {added_files[0].split('/')[-1]}"
    elif len(modified_files) == 1:
        subject = f"Update {modified_files[0].split('/')[-1]}"
    elif added_files:
        subject = f"Add {len(added_files)} new files"
    elif deletions > additions:
        subject = "Remove unused code"
    else:
        subject = "Update code"

    # Build conventional commit message
    prefix = type
    if scope:
        prefix = f"{type}({scope})"

    message = f"{prefix}: {subject}"

    # Generate body if significant changes
    body_lines = []
    if additions + deletions > 50:
        body_lines.append(f"- {additions} additions, {deletions} deletions")
    if added_files:
        body_lines.append(f"- Added: {', '.join(f.split('/')[-1] for f in added_files[:3])}")
    if modified_files:
        body_lines.append(f"- Modified: {', '.join(f.split('/')[-1] for f in modified_files[:3])}")

    body = "\n".join(body_lines) if body_lines else None

    return {
        "success": True,
        "message": message,
        "body": body,
        "full_message": f"{message}\n\n{body}" if body else message,
        "type": type,
        "scope": scope,
        "stats": {
            "additions": additions,
            "deletions": deletions,
            "files_added": len(added_files),
            "files_modified": len(modified_files),
        },
    }


def commit_changes(
    message: str,
    files: list[str] | None = None,
    amend: bool = False,
) -> dict[str, Any]:
    """
    Stage and commit changes.

    Note: This returns the command to execute, not actually executing it.
    The agent should use the bash tool to run these commands.

    Args:
        message: Commit message
        files: Files to stage
        amend: Whether to amend previous commit

    Returns:
        Commands to execute
    """
    commands = []

    # Stage files
    if files:
        commands.append(f"git add {' '.join(files)}")
    else:
        commands.append("git add -A")

    # Commit
    commit_cmd = "git commit"
    if amend:
        commit_cmd += " --amend"

    # Escape message for shell
    escaped_message = message.replace('"', '\\"').replace("$", "\\$")
    commit_cmd += f' -m "{escaped_message}"'

    commands.append(commit_cmd)

    return {
        "success": True,
        "commands": commands,
        "full_command": " && ".join(commands),
        "message": message,
        "files": files or ["all staged"],
        "amend": amend,
    }


def analyze_changes(diff: str) -> dict[str, Any]:
    """
    Analyze changes to suggest commit type and scope.

    Args:
        diff: Git diff to analyze

    Returns:
        Analysis with suggested type and scope
    """
    # Extract changed files
    files = re.findall(r"\+\+\+ b/(.+)", diff)

    # Determine type based on files and content
    suggested_type = "chore"
    suggested_scope = None

    # Check file patterns
    test_patterns = ["test_", "_test.", ".test.", "spec.", "__tests__"]
    doc_patterns = [".md", "README", "CHANGELOG", "docs/"]
    config_patterns = [".yaml", ".yml", ".json", ".toml", "config"]

    has_tests = any(any(p in f for p in test_patterns) for f in files)
    has_docs = any(any(p in f for p in doc_patterns) for f in files)
    has_config = any(any(p in f for p in config_patterns) for f in files)

    # Check content patterns
    has_new_function = bool(re.search(r"^\+\s*(def|function|const\s+\w+\s*=)", diff, re.MULTILINE))
    has_fix_keywords = bool(re.search(r"fix|bug|error|issue", diff, re.IGNORECASE))
    has_refactor = bool(re.search(r"refactor|rename|move|reorganize", diff, re.IGNORECASE))

    # Determine type
    if has_tests and not has_new_function:
        suggested_type = "test"
    elif has_docs:
        suggested_type = "docs"
    elif has_fix_keywords:
        suggested_type = "fix"
    elif has_new_function:
        suggested_type = "feat"
    elif has_refactor:
        suggested_type = "refactor"
    elif has_config:
        suggested_type = "chore"

    # Determine scope from common path
    if files:
        # Find common directory
        parts = [f.split("/") for f in files]
        common = []
        for i in range(min(len(p) for p in parts)):
            if len(set(p[i] for p in parts)) == 1:
                common.append(parts[0][i])
            else:
                break

        if common and common[0] not in ["src", "lib", "."]:
            suggested_scope = common[0]

    return {
        "success": True,
        "suggested_type": suggested_type,
        "suggested_scope": suggested_scope,
        "type_reason": COMMIT_TYPES.get(suggested_type, ""),
        "files_analyzed": len(files),
        "patterns_detected": {
            "has_tests": has_tests,
            "has_docs": has_docs,
            "has_new_code": has_new_function,
            "has_fix": has_fix_keywords,
        },
    }
