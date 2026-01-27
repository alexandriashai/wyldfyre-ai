"""
Slash command handler for chat interface.

Provides Claude CLI-style slash commands for enhanced chat functionality.
"""

import re
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from ai_core import get_logger
from ai_messaging import PubSubManager, RedisClient

from .plan_mode import Plan, PlanManager, PlanStatus, StepStatus, format_plan_for_display

logger = get_logger(__name__)


# Command definitions
COMMANDS = {
    "help": {
        "description": "Show available commands",
        "usage": "/help",
        "aliases": ["?", "h"],
    },
    "clear": {
        "description": "Clear conversation history",
        "usage": "/clear",
        "aliases": ["c"],
    },
    "plan": {
        "description": "Plan management - create, browse, edit, and manage plans",
        "usage": "/plan [subcommand] [args]",
        "aliases": ["p"],
        "subcommands": {
            "list": "List plans by status: /plan list [active|paused|completed|failed|stuck|all]",
            "view": "View plan details: /plan view <plan_id>",
            "edit": "Edit plan: /plan edit <plan_id>",
            "delete": "Delete plan: /plan delete <plan_id>",
            "history": "View plan history: /plan history <plan_id>",
            "clone": "Clone plan: /plan clone <plan_id> [new_title]",
            "follow-up": "Resume stuck plan: /plan follow-up <plan_id> [context]",
            "restart": "Restart plan from beginning or specific step: /plan restart <plan_id> [step_number]",
            "modify": "AI modify plan: /plan modify <plan_id> <request>",
            "approve": "Approve current plan",
            "reject": "Reject/cancel current plan",
            "status": "Show current plan status",
            "pause": "Pause plan execution",
            "resume": "Resume plan execution",
        },
    },
    "memory": {
        "description": "Search project memory for relevant context",
        "usage": "/memory [search query]",
        "aliases": ["mem", "m"],
    },
    "remember": {
        "description": "Save information to project memory",
        "usage": "/remember [text to save]",
        "aliases": ["rem", "r"],
    },
    "tools": {
        "description": "List available tools for the current agent",
        "usage": "/tools",
        "aliases": ["t"],
    },
    "agent": {
        "description": "Switch to a specific agent for the conversation",
        "usage": "/agent [agent-name]",
        "aliases": ["a"],
    },
    "status": {
        "description": "Show current system and agent status",
        "usage": "/status",
        "aliases": ["s"],
    },
    "gh": {
        "description": "GitHub operations - PRs, issues, repos, and more",
        "usage": "/gh [subcommand] [args]",
        "aliases": ["github"],
        "subcommands": {
            "pr": "Pull request operations: /gh pr [list|create|view|checkout|merge] [args]",
            "issue": "Issue operations: /gh issue [list|create|view] [args]",
            "repo": "Repository operations: /gh repo [view|clone] [args]",
            "status": "Show GitHub CLI auth status",
            "browse": "Open repo in browser: /gh browse [path]",
        },
    },
    "git": {
        "description": "Git operations - push, pull, commit, branch, and more",
        "usage": "/git [subcommand] [args]",
        "aliases": [],
        "subcommands": {
            "status": "Show working tree status",
            "push": "Push commits to remote: /git push [remote] [branch]",
            "pull": "Pull changes from remote: /git pull [remote] [branch]",
            "add": "Stage files: /git add <files|.>",
            "commit": "Commit changes: /git commit -m \"message\"",
            "branch": "List or create branches: /git branch [name]",
            "checkout": "Switch branches: /git checkout <branch>",
            "merge": "Merge a branch: /git merge <branch>",
            "log": "Show commit history: /git log [--oneline]",
            "diff": "Show changes: /git diff [file]",
            "stash": "Stash changes: /git stash [pop|list|drop]",
            "reset": "Reset HEAD: /git reset [--hard] [ref]",
        },
    },
    "continue": {
        "description": "Continue a step that hit max iterations",
        "usage": "/continue [additional_iterations]",
        "aliases": ["cont"],
    },
}


class CommandHandler:
    """
    Handles slash commands in chat messages.

    Supports Claude CLI-style commands like /help, /memory, /plan, etc.
    """

    def __init__(self, redis: RedisClient):
        self.redis = redis
        self.plan_manager = PlanManager(redis)

    def is_command(self, content: str) -> bool:
        """Check if message starts with a command."""
        return content.strip().startswith("/")

    def parse_command(self, content: str) -> tuple[str, str]:
        """
        Parse command and arguments from message.

        Returns:
            Tuple of (command_name, arguments)
        """
        content = content.strip()
        if not content.startswith("/"):
            return "", content

        # Split on first whitespace
        parts = content[1:].split(None, 1)
        command = parts[0].lower() if parts else ""
        args = parts[1] if len(parts) > 1 else ""

        # Check for aliases
        for cmd_name, cmd_info in COMMANDS.items():
            if command == cmd_name or command in cmd_info.get("aliases", []):
                return cmd_name, args

        return command, args

    async def handle(
        self,
        command: str,
        args: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Handle a slash command.

        Args:
            command: The command name (without /)
            args: Arguments passed to the command
            context: Context dict with user_id, conversation_id, project_id, etc.

        Returns:
            Response dict with type, content, and optional metadata
        """
        handlers = {
            "help": self._cmd_help,
            "clear": self._cmd_clear,
            "plan": self._cmd_plan,
            "memory": self._cmd_memory,
            "remember": self._cmd_remember,
            "tools": self._cmd_tools,
            "agent": self._cmd_agent,
            "status": self._cmd_status,
            "gh": self._cmd_gh,
            "git": self._cmd_git,
        }

        handler = handlers.get(command, self._cmd_unknown)

        try:
            return await handler(args, context)
        except Exception as e:
            logger.error(
                "Command handler error",
                command=command,
                error=str(e),
            )
            return {
                "type": "command_error",
                "command": command,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    async def _cmd_help(self, args: str, context: dict[str, Any]) -> dict[str, Any]:
        """Show available commands."""
        lines = ["**Available Commands:**\n"]

        for cmd_name, cmd_info in COMMANDS.items():
            aliases = cmd_info.get("aliases", [])
            alias_str = f" (aliases: {', '.join('/' + a for a in aliases)})" if aliases else ""
            lines.append(f"- `{cmd_info['usage']}` - {cmd_info['description']}{alias_str}")

        lines.append("\n**Memory Tags:**")
        lines.append("- Use `#tag-name` in messages to save content with that tag")
        lines.append("- Example: `The API uses JWT auth #api-notes`")

        return {
            "type": "command_result",
            "command": "help",
            "content": "\n".join(lines),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _cmd_clear(self, args: str, context: dict[str, Any]) -> dict[str, Any]:
        """Clear conversation history."""
        conversation_id = context.get("conversation_id")

        if conversation_id:
            # Clear messages from Redis
            msgs_key = f"conversation:{conversation_id}:messages"
            await self.redis.delete(msgs_key)

        return {
            "type": "command_result",
            "command": "clear",
            "content": "Conversation cleared.",
            "action": "clear_conversation",
            "conversation_id": conversation_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _cmd_plan(self, args: str, context: dict[str, Any]) -> dict[str, Any]:
        """Handle /plan command with subcommands."""
        conversation_id = context.get("conversation_id")
        user_id = context.get("user_id")
        project_id = context.get("project_id")

        # Parse subcommand and arguments
        parts = args.strip().split(maxsplit=1) if args else []
        subcommand = parts[0].lower() if parts else ""
        sub_args = parts[1] if len(parts) > 1 else ""

        # Route to subcommand handlers
        new_subcommands = {
            "list": self._plan_list,
            "view": self._plan_view,
            "edit": self._plan_edit,
            "delete": self._plan_delete,
            "history": self._plan_history,
            "clone": self._plan_clone,
            "follow-up": self._plan_follow_up,
            "followup": self._plan_follow_up,  # alias
            "restart": self._plan_restart,
            "modify": self._plan_modify,
        }

        if subcommand in new_subcommands:
            return await new_subcommands[subcommand](sub_args, context)

        # Check for existing plan (for legacy subcommands)
        existing_plan = await self.plan_manager.get_active_plan(conversation_id)

        # Handle legacy plan subcommands
        legacy_subcommands = {"approve", "reject", "cancel", "status", "pause", "resume"}

        if subcommand in legacy_subcommands:
            if not existing_plan:
                return {
                    "type": "command_error",
                    "command": "plan",
                    "error": f"No active plan to {subcommand}. Use `/plan [description]` to create one.",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

            # Approve existing plan
            if subcommand == "approve":
                await self.plan_manager.approve_plan(existing_plan.id)

                # Trigger execution via supervisor
                pubsub = PubSubManager(self.redis)
                await pubsub.start()
                try:
                    await pubsub.publish(
                        "agent:supervisor:tasks",
                        {
                            "type": "task_request",
                            "task_type": "execute_plan",
                            "user_id": user_id,
                            "payload": {
                                "plan_id": existing_plan.id,
                                "conversation_id": conversation_id,
                                "user_id": user_id,
                                "project_id": context.get("project_id"),
                                "root_path": context.get("root_path"),
                                "agent_context": context.get("agent_context"),
                            },
                        },
                    )
                    logger.info(
                        "Plan execution triggered",
                        plan_id=existing_plan.id,
                        conversation_id=conversation_id,
                    )
                finally:
                    await pubsub.stop()

                return {
                    "type": "command_result",
                    "command": "plan",
                    "content": f"✅ Plan approved! Starting execution...\n\n{format_plan_for_display(existing_plan)}",
                    "action": "plan_approved",
                    "plan_id": existing_plan.id,
                    "plan_status": "APPROVED",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

            # Reject existing plan
            if subcommand in ("reject", "cancel"):
                await self.plan_manager.reject_plan(existing_plan.id)
                return {
                    "type": "command_result",
                    "command": "plan",
                    "content": "❌ Plan cancelled. What would you like to do instead?",
                    "action": "plan_rejected",
                    "plan_id": existing_plan.id,
                    "plan_content": "",  # Clear the plan panel
                    "plan_status": "REJECTED",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

            # Show current plan status
            if subcommand == "status":
                plan_dict = existing_plan.to_dict()
                return {
                    "type": "command_result",
                    "command": "plan",
                    "content": format_plan_for_display(existing_plan),
                    "action": "plan_status",
                    "plan": plan_dict,
                    "plan_content": plan_dict.get("content", ""),
                    "plan_status": existing_plan.status.value.upper(),
                    "plan_id": existing_plan.id,
                    "steps": [
                        {
                            "id": step.id,
                            "title": step.title,
                            "description": step.description,
                            "status": step.status.value,
                            "order_index": step.order_index,
                        }
                        for step in existing_plan.steps
                    ],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

            # Pause execution
            if subcommand == "pause":
                await self.plan_manager.pause_execution(existing_plan.id)
                return {
                    "type": "command_result",
                    "command": "plan",
                    "content": "⏸️ Plan execution paused. Use `/plan resume` to continue.",
                    "action": "plan_paused",
                    "plan_id": existing_plan.id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

            # Resume execution
            if subcommand == "resume":
                await self.plan_manager.resume_execution(existing_plan.id)
                return {
                    "type": "command_result",
                    "command": "plan",
                    "content": "▶️ Plan execution resumed.",
                    "action": "plan_resumed",
                    "plan_id": existing_plan.id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

        # If there's an existing pending plan, show it
        if existing_plan and existing_plan.status == PlanStatus.PENDING:
            return {
                "type": "command_result",
                "command": "plan",
                "content": f"You have an existing plan awaiting approval:\n\n{format_plan_for_display(existing_plan)}",
                "action": "show_existing_plan",
                "plan": existing_plan.to_dict(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        # Create new plan with intelligent exploration if args provided (and not a subcommand)
        if args and subcommand not in new_subcommands and subcommand not in legacy_subcommands:
            if not project_id:
                return {
                    "type": "command_result",
                    "command": "plan",
                    "content": "⚠️ Cannot create plan without a project. Please select or create a project first.",
                    "error": "project_required",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

            plan = await self.plan_manager.create_plan(
                conversation_id=conversation_id,
                user_id=user_id,
                title=args[:100],
                description=args,
                project_id=project_id,
            )

            # Delegate to supervisor for intelligent exploration and planning
            from ai_messaging import TaskRequest
            pubsub = PubSubManager(self.redis)
            await pubsub.start()

            try:
                task_request = TaskRequest(
                    task_type="create_plan",
                    user_id=user_id,
                    payload={
                        "plan_id": plan.id,
                        "description": args,
                        "conversation_id": conversation_id,
                        "user_id": user_id,
                        "project_id": project_id,
                        "root_path": context.get("root_path"),
                        "agent_context": context.get("agent_context"),
                        "project_name": context.get("project_name"),
                    },
                )
                await pubsub.publish(
                    "agent:supervisor:tasks",
                    task_request.model_dump_json(),
                )
                logger.info(
                    "Published plan creation task",
                    plan_id=plan.id,
                    task_id=task_request.id,
                )
            finally:
                await pubsub.stop()

            # Return initial response - supervisor will send updates via WebSocket
            return {
                "type": "command_result",
                "command": "plan",
                "content": f"Creating intelligent plan for: **{args[:50]}{'...' if len(args) > 50 else ''}**\n\n*Exploring codebase...*",
                "plan_content": f"## Creating Plan: {args[:50]}...\n\n*Analyzing codebase...*",
                "plan_status": "DRAFT",
                "action": "plan_creating",
                "plan_id": plan.id,
                "conversation_id": conversation_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        # No args provided - show help
        return {
            "type": "command_result",
            "command": "plan",
            "content": """**Plan Mode Commands:**

**Create & Execute:**
- `/plan [task description]` - Create a new plan for a task
- `/plan approve` - Approve the current plan
- `/plan reject` - Cancel the current plan
- `/plan pause` - Pause plan execution
- `/plan resume` - Resume paused execution
- `/plan status` - Show current plan status

**Browse & Manage:**
- `/plan list [status]` - List plans (active, paused, completed, failed, stuck, all)
- `/plan view <id>` - View plan details with progress
- `/plan edit <id>` - Edit plan (opens editor)
- `/plan delete <id>` - Delete a plan
- `/plan history <id>` - View modification history
- `/plan clone <id> [title]` - Clone plan as new draft
- `/plan restart <id> [step]` - Restart plan from beginning or specific step

**AI Assistance:**
- `/plan follow-up <id> [context]` - Resume stuck/paused plan with AI analysis
- `/plan modify <id> <request>` - AI-assisted plan modification

**Example:**
`/plan Add user authentication with JWT tokens`""",
            "action": "plan_help",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _plan_list(self, args: str, context: dict[str, Any]) -> dict[str, Any]:
        """List plans by status."""
        import json as json_mod

        user_id = context.get("user_id")
        status_filter = args.strip().lower() if args else "all"

        # Valid status filters
        valid_statuses = {"active", "paused", "completed", "failed", "stuck", "all"}
        if status_filter not in valid_statuses:
            status_filter = "all"

        # Scan all plans for this user
        plans = []
        cursor = 0
        while True:
            cursor, keys = await self.redis.scan(cursor=cursor, match="plan:*", count=100)
            for key in keys:
                if ":history" in key:
                    continue
                plan_data = await self.redis.get(key)
                if plan_data:
                    try:
                        plan = json_mod.loads(plan_data)
                        if plan.get("user_id") == user_id:
                            plans.append(plan)
                    except json_mod.JSONDecodeError:
                        continue
            if cursor == 0:
                break

        # Apply status filter
        status_map = {
            "active": ["executing", "approved"],
            "paused": ["paused"],
            "completed": ["completed"],
            "failed": ["failed"],
            "stuck": ["paused", "failed"],
            "all": None,
        }

        filter_statuses = status_map.get(status_filter)
        if filter_statuses:
            filtered_plans = []
            for plan in plans:
                plan_status = plan.get("status", "")
                if plan_status in filter_statuses:
                    if status_filter == "stuck":
                        steps = plan.get("steps", [])
                        completed = sum(1 for s in steps if s.get("status") == "completed")
                        if completed > 0:
                            filtered_plans.append(plan)
                    else:
                        filtered_plans.append(plan)
            plans = filtered_plans

        # Sort by created_at descending
        plans.sort(key=lambda p: p.get("created_at", ""), reverse=True)

        # Format plan list for display
        if not plans:
            return {
                "type": "command_result",
                "command": "plan",
                "content": f"No plans found with status: **{status_filter}**",
                "action": "plan_list",
                "plans": [],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        lines = [f"**Plans ({status_filter}):** {len(plans)} found\n"]
        status_icons = {
            "executing": "▶️",
            "approved": "✅",
            "pending": "⏳",
            "paused": "⏸️",
            "completed": "🎉",
            "failed": "💥",
            "cancelled": "❌",
            "exploring": "🔵",
            "drafting": "📝",
        }

        for plan in plans[:10]:  # Show first 10
            icon = status_icons.get(plan.get("status", ""), "○")
            steps = plan.get("steps", [])
            completed = sum(1 for s in steps if s.get("status") == "completed")
            title = plan.get("title", "Untitled")[:40]
            plan_id = plan.get("id", "")[:8]

            lines.append(f"- {icon} `{plan_id}` **{title}** ({completed}/{len(steps)} steps)")

        if len(plans) > 10:
            lines.append(f"\n*...and {len(plans) - 10} more*")

        lines.append("\n*Use `/plan view <id>` to see details*")

        return {
            "type": "command_result",
            "command": "plan",
            "content": "\n".join(lines),
            "action": "plan_list",
            "plans": [{"id": p.get("id"), "title": p.get("title"), "status": p.get("status")} for p in plans],
            "filter": status_filter,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _plan_view(self, args: str, context: dict[str, Any]) -> dict[str, Any]:
        """View plan details with progress and open plan panel."""
        plan_id = args.strip()
        if not plan_id:
            return {
                "type": "command_error",
                "command": "plan",
                "error": "Please provide a plan ID. Usage: `/plan view <plan_id>`",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        plan = await self.plan_manager.get_plan(plan_id)
        if not plan:
            return {
                "type": "command_error",
                "command": "plan",
                "error": f"Plan not found: {plan_id}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        if plan.user_id != context.get("user_id"):
            return {
                "type": "command_error",
                "command": "plan",
                "error": "Access denied",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        # Convert plan steps to frontend format
        frontend_steps = []
        for step in plan.steps:
            frontend_steps.append({
                "id": step.id,
                "title": step.title,
                "description": step.description,
                "status": step.status.value,
                "agent": step.agent,
                "files": getattr(step, 'files', []),
                "todos": getattr(step, 'todos', []),
                "output": step.output,
                "error": step.error,
                "started_at": step.started_at.isoformat() if step.started_at else None,
                "completed_at": step.completed_at.isoformat() if step.completed_at else None,
            })

        return {
            "type": "command_result",
            "command": "plan",
            "content": format_plan_for_display(plan),
            "action": "plan_view",
            "plan": plan.to_dict(),
            # These fields trigger the plan panel to open
            "plan_content": format_plan_for_display(plan),
            "plan_status": plan.status.value.upper(),
            "steps": frontend_steps,
            "plan_id": plan.id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _plan_edit(self, args: str, context: dict[str, Any]) -> dict[str, Any]:
        """Edit plan - opens editor modal on frontend."""
        plan_id = args.strip()
        if not plan_id:
            return {
                "type": "command_error",
                "command": "plan",
                "error": "Please provide a plan ID. Usage: `/plan edit <plan_id>`",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        plan = await self.plan_manager.get_plan(plan_id)
        if not plan:
            return {
                "type": "command_error",
                "command": "plan",
                "error": f"Plan not found: {plan_id}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        if plan.user_id != context.get("user_id"):
            return {
                "type": "command_error",
                "command": "plan",
                "error": "Access denied",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        return {
            "type": "command_result",
            "command": "plan",
            "content": f"Opening editor for plan: **{plan.title}**",
            "action": "plan_edit",
            "plan": plan.to_dict(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _plan_delete(self, args: str, context: dict[str, Any]) -> dict[str, Any]:
        """Delete a plan."""
        plan_id = args.strip()
        if not plan_id:
            return {
                "type": "command_error",
                "command": "plan",
                "error": "Please provide a plan ID. Usage: `/plan delete <plan_id>`",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        plan = await self.plan_manager.get_plan(plan_id)
        if not plan:
            return {
                "type": "command_error",
                "command": "plan",
                "error": f"Plan not found: {plan_id}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        if plan.user_id != context.get("user_id"):
            return {
                "type": "command_error",
                "command": "plan",
                "error": "Access denied",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        if plan.status == PlanStatus.EXECUTING:
            return {
                "type": "command_error",
                "command": "plan",
                "error": "Cannot delete a plan that is currently executing. Pause or cancel it first.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        # Delete the plan
        await self.redis.delete(f"plan:{plan_id}")
        await self.redis.delete(f"plan:{plan_id}:history")
        if plan.conversation_id:
            await self.redis.delete(f"conversation:{plan.conversation_id}:active_plan")

        return {
            "type": "command_result",
            "command": "plan",
            "content": f"🗑️ Plan deleted: **{plan.title}**",
            "action": "plan_deleted",
            "plan_id": plan_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _plan_history(self, args: str, context: dict[str, Any]) -> dict[str, Any]:
        """View plan modification history."""
        import json as json_mod

        plan_id = args.strip()
        if not plan_id:
            return {
                "type": "command_error",
                "command": "plan",
                "error": "Please provide a plan ID. Usage: `/plan history <plan_id>`",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        plan = await self.plan_manager.get_plan(plan_id)
        if not plan:
            return {
                "type": "command_error",
                "command": "plan",
                "error": f"Plan not found: {plan_id}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        if plan.user_id != context.get("user_id"):
            return {
                "type": "command_error",
                "command": "plan",
                "error": "Access denied",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        # Get history from Redis
        history_key = f"plan:{plan_id}:history"
        history_data = await self.redis.lrange(history_key, 0, 19)  # Last 20 entries

        entries = []
        for entry in history_data or []:
            try:
                entries.append(json_mod.loads(entry))
            except json_mod.JSONDecodeError:
                continue

        if not entries:
            return {
                "type": "command_result",
                "command": "plan",
                "content": f"No history found for plan: **{plan.title}**",
                "action": "plan_history",
                "plan_id": plan_id,
                "entries": [],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        lines = [f"**History for:** {plan.title}\n"]
        for entry in entries[:10]:
            action = entry.get("action", "unknown")
            ts = entry.get("timestamp", "")[:16]
            actor = entry.get("actor", "system")
            lines.append(f"- `{ts}` **{action}** by {actor}")

        return {
            "type": "command_result",
            "command": "plan",
            "content": "\n".join(lines),
            "action": "plan_history",
            "plan_id": plan_id,
            "entries": entries,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _plan_clone(self, args: str, context: dict[str, Any]) -> dict[str, Any]:
        """Clone plan as new draft."""
        parts = args.strip().split(maxsplit=1)
        plan_id = parts[0] if parts else ""
        new_title = parts[1] if len(parts) > 1 else None

        if not plan_id:
            return {
                "type": "command_error",
                "command": "plan",
                "error": "Please provide a plan ID. Usage: `/plan clone <plan_id> [new_title]`",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        plan = await self.plan_manager.get_plan(plan_id)
        if not plan:
            return {
                "type": "command_error",
                "command": "plan",
                "error": f"Plan not found: {plan_id}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        if plan.user_id != context.get("user_id"):
            return {
                "type": "command_error",
                "command": "plan",
                "error": "Access denied",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        # Create new plan as copy
        from .plan_mode import PlanStep
        new_plan = Plan(
            id=str(uuid4()),
            conversation_id=plan.conversation_id,
            user_id=context.get("user_id"),
            title=new_title or f"{plan.title} (Copy)",
            description=plan.description,
            status=PlanStatus.PENDING,
            metadata=plan.metadata.copy(),
            exploration_notes=plan.exploration_notes.copy(),
            files_explored=plan.files_explored.copy(),
        )

        # Copy steps with reset status
        from .plan_mode import StepStatus
        for step in plan.steps:
            new_step = PlanStep(
                id=str(uuid4()),
                order=step.order,
                title=step.title,
                description=step.description,
                status=StepStatus.PENDING,
                agent=step.agent,
                estimated_duration=step.estimated_duration,
                dependencies=[],
            )
            new_plan.steps.append(new_step)

        await self.plan_manager._save_plan(new_plan)

        return {
            "type": "command_result",
            "command": "plan",
            "content": f"📋 Plan cloned: **{new_plan.title}** (ID: `{new_plan.id[:8]}`)",
            "action": "plan_cloned",
            "plan_id": new_plan.id,
            "original_plan_id": plan_id,
            "plan": new_plan.to_dict(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _plan_follow_up(self, args: str, context: dict[str, Any]) -> dict[str, Any]:
        """Resume a stuck or paused plan with AI analysis."""
        parts = args.strip().split(maxsplit=1)
        plan_id = parts[0] if parts else ""
        additional_context = parts[1] if len(parts) > 1 else None

        if not plan_id:
            return {
                "type": "command_error",
                "command": "plan",
                "error": "Please provide a plan ID. Usage: `/plan follow-up <plan_id> [context]`",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        plan = await self.plan_manager.get_plan(plan_id)
        if not plan:
            return {
                "type": "command_error",
                "command": "plan",
                "error": f"Plan not found: {plan_id}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        if plan.user_id != context.get("user_id"):
            return {
                "type": "command_error",
                "command": "plan",
                "error": "Access denied",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        if plan.status not in (PlanStatus.PAUSED, PlanStatus.FAILED):
            return {
                "type": "command_error",
                "command": "plan",
                "error": f"Cannot follow up on plan with status: {plan.status.value}. Plan must be paused or failed.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        # Publish follow-up task to supervisor
        pubsub = PubSubManager(self.redis)
        await pubsub.start()

        try:
            task = {
                "type": "task_request",
                "task_type": "plan_follow_up",
                "user_id": context.get("user_id"),
                "payload": {
                    "plan_id": plan_id,
                    "plan": plan.to_dict(),
                    "context": additional_context,
                    "action": "analyze_and_resume",
                    "conversation_id": plan.conversation_id,
                },
            }
            await pubsub.publish("agent:supervisor:tasks", task)
        finally:
            await pubsub.stop()

        return {
            "type": "command_result",
            "command": "plan",
            "content": f"🔍 Analyzing plan for resumption: **{plan.title}**\n\n*The supervisor will analyze what went wrong and suggest how to proceed...*",
            "action": "plan_follow_up",
            "plan_id": plan_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _plan_restart(self, args: str, context: dict[str, Any]) -> dict[str, Any]:
        """Restart a plan from the beginning or a specific step."""
        parts = args.strip().split()
        plan_id = parts[0] if parts else ""
        start_step = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0

        if not plan_id:
            return {
                "type": "command_error",
                "command": "plan",
                "error": "Please provide a plan ID. Usage: `/plan restart <plan_id> [step_number]`",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        plan = await self.plan_manager.get_plan(plan_id)
        if not plan:
            return {
                "type": "command_error",
                "command": "plan",
                "error": f"Plan not found: {plan_id}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        if plan.user_id != context.get("user_id"):
            return {
                "type": "command_error",
                "command": "plan",
                "error": "Access denied",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        # Reset step statuses from start_step onwards
        for i, step in enumerate(plan.steps):
            if i >= start_step:
                step.status = StepStatus.PENDING
                step.result = None
                step.error = None

        # Set plan back to executing
        plan.status = PlanStatus.EXECUTING

        # Save updated plan
        await self.plan_manager.save_plan(plan)

        # Publish execution task to supervisor
        pubsub = PubSubManager(self.redis)
        await pubsub.start()

        try:
            conversation_id = context.get("conversation_id") or plan.conversation_id
            user_id = context.get("user_id")

            await pubsub.publish(
                "agent:supervisor:tasks",
                {
                    "type": "task_request",
                    "task_type": "execute_plan",
                    "user_id": user_id,
                    "payload": {
                        "plan_id": plan.id,
                        "conversation_id": conversation_id,
                        "user_id": user_id,
                        "project_id": context.get("project_id"),
                        "root_path": context.get("root_path"),
                        "start_step": start_step,
                    },
                },
            )
        finally:
            await pubsub.stop()

        step_info = f" from step {start_step + 1}" if start_step > 0 else ""
        return {
            "type": "command_result",
            "command": "plan",
            "content": f"🔄 Restarting plan{step_info}: **{plan.title}**\n\n*Execution starting...*",
            "action": "plan_restarted",
            "plan_id": plan.id,
            "plan_status": "APPROVED",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _plan_modify(self, args: str, context: dict[str, Any]) -> dict[str, Any]:
        """AI-assisted plan modification."""
        parts = args.strip().split(maxsplit=1)
        plan_id = parts[0] if parts else ""
        modification_request = parts[1] if len(parts) > 1 else ""

        if not plan_id:
            return {
                "type": "command_error",
                "command": "plan",
                "error": "Please provide a plan ID and modification request. Usage: `/plan modify <plan_id> <request>`",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        if not modification_request:
            return {
                "type": "command_error",
                "command": "plan",
                "error": "Please provide a modification request. Example: `/plan modify abc123 add a testing step`",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        plan = await self.plan_manager.get_plan(plan_id)
        if not plan:
            return {
                "type": "command_error",
                "command": "plan",
                "error": f"Plan not found: {plan_id}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        if plan.user_id != context.get("user_id"):
            return {
                "type": "command_error",
                "command": "plan",
                "error": "Access denied",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        if plan.status == PlanStatus.EXECUTING:
            return {
                "type": "command_error",
                "command": "plan",
                "error": "Cannot modify plan while it is executing. Pause it first.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        # Publish modification task to supervisor
        pubsub = PubSubManager(self.redis)
        await pubsub.start()

        try:
            task = {
                "type": "task_request",
                "task_type": "plan_modify",
                "user_id": context.get("user_id"),
                "payload": {
                    "plan_id": plan_id,
                    "plan": plan.to_dict(),
                    "modification_request": modification_request,
                    "conversation_id": plan.conversation_id,
                },
            }
            await pubsub.publish("agent:supervisor:tasks", task)
        finally:
            await pubsub.stop()

        return {
            "type": "command_result",
            "command": "plan",
            "content": f"🤖 Modifying plan: **{plan.title}**\n\nRequest: *{modification_request}*\n\n*The supervisor is updating the plan...*",
            "action": "plan_modify",
            "plan_id": plan_id,
            "modification_request": modification_request,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _cmd_memory(self, args: str, context: dict[str, Any]) -> dict[str, Any]:
        """Search project memory."""
        if not args:
            return {
                "type": "command_error",
                "command": "memory",
                "error": "Please provide a search query. Usage: /memory [query]",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        project_id = context.get("project_id")
        user_id = context.get("user_id")

        # Search in Redis for memories
        # For now, return a placeholder - actual implementation would query vector store
        return {
            "type": "command_result",
            "command": "memory",
            "content": f"Searching memory for: **{args}**",
            "action": "memory_search",
            "query": args,
            "project_id": project_id,
            "results": [],  # Would be populated by memory service
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _cmd_remember(self, args: str, context: dict[str, Any]) -> dict[str, Any]:
        """Save to project memory."""
        if not args:
            return {
                "type": "command_error",
                "command": "remember",
                "error": "Please provide text to save. Usage: /remember [text]",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        project_id = context.get("project_id")
        user_id = context.get("user_id")
        memory_id = str(uuid4())

        # Store in Redis
        memory_key = f"memory:{memory_id}"
        await self.redis.hset(
            memory_key,
            mapping={
                "id": memory_id,
                "content": args,
                "user_id": user_id,
                "project_id": project_id or "",
                "source": "command",
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        # Add to project memory index
        if project_id:
            index_key = f"project:{project_id}:memories"
            await self.redis.lpush(index_key, memory_id)

        return {
            "type": "command_result",
            "command": "remember",
            "content": f"Saved to memory: *{args[:50]}{'...' if len(args) > 50 else ''}*",
            "action": "memory_saved",
            "memory_id": memory_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _cmd_tools(self, args: str, context: dict[str, Any]) -> dict[str, Any]:
        """List available tools."""
        # This would typically come from agent configuration
        return {
            "type": "command_result",
            "command": "tools",
            "content": "View agent tools in the Agents section of the dashboard.",
            "action": "show_tools",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _cmd_agent(self, args: str, context: dict[str, Any]) -> dict[str, Any]:
        """Switch to specific agent."""
        if not args:
            return {
                "type": "command_result",
                "command": "agent",
                "content": "**Available agents:** wyld, code-agent, data-agent, infra-agent, research-agent, qa-agent",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        agent_name = args.strip().lower()
        valid_agents = ["wyld", "code-agent", "data-agent", "infra-agent", "research-agent", "qa-agent"]

        if agent_name not in valid_agents:
            return {
                "type": "command_error",
                "command": "agent",
                "error": f"Unknown agent: {agent_name}. Valid agents: {', '.join(valid_agents)}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        return {
            "type": "command_result",
            "command": "agent",
            "content": f"Switched to **{agent_name}**",
            "action": "switch_agent",
            "agent_name": agent_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _cmd_status(self, args: str, context: dict[str, Any]) -> dict[str, Any]:
        """Show system status."""
        return {
            "type": "command_result",
            "command": "status",
            "content": "System status: **Operational**\nUse the dashboard for detailed agent status.",
            "action": "show_status",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _cmd_gh(self, args: str, context: dict[str, Any]) -> dict[str, Any]:
        """
        Handle GitHub CLI operations.

        Supports: pr, issue, repo, status, browse subcommands.
        Delegates to supervisor for actual command execution.
        """
        conversation_id = context.get("conversation_id")
        user_id = context.get("user_id")
        project_id = context.get("project_id")
        root_path = context.get("root_path")

        # Require a project to be selected
        if not project_id or not root_path:
            return {
                "type": "command_error",
                "command": "gh",
                "error": "GitHub commands require a project to be selected. Please select a project first.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        if not args.strip():
            # Show help for /gh command
            return {
                "type": "command_result",
                "command": "gh",
                "content": """**GitHub CLI Commands:**

**Pull Requests:**
- `/gh pr list [state]` - List PRs (open, closed, merged, all)
- `/gh pr create [title]` - Create a new PR
- `/gh pr view <number>` - View PR details
- `/gh pr checkout <number>` - Checkout PR branch
- `/gh pr merge <number>` - Merge a PR

**Issues:**
- `/gh issue list [state]` - List issues (open, closed, all)
- `/gh issue create [title]` - Create a new issue
- `/gh issue view <number>` - View issue details

**Repository:**
- `/gh repo view [repo]` - View repo info
- `/gh repo clone <repo>` - Clone a repository

**Other:**
- `/gh status` - Check GitHub CLI auth status
- `/gh browse [path]` - Open repo/path in browser""",
                "action": "show_gh_help",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        # Parse subcommand
        parts = args.strip().split(maxsplit=1)
        subcommand = parts[0].lower()
        sub_args = parts[1] if len(parts) > 1 else ""

        # Build the gh CLI command
        gh_command = f"gh {args.strip()}"

        # Delegate to supervisor to execute the command
        from ai_messaging import TaskRequest

        pubsub = PubSubManager(self.redis)
        await pubsub.start()

        try:
            task_request = TaskRequest(
                task_type="host_command",
                user_id=user_id,
                payload={
                    "command": gh_command,
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "project_id": project_id,
                    "root_path": root_path,
                    "working_directory": root_path,
                },
            )
            await pubsub.publish(
                "agent:supervisor:tasks",
                task_request.model_dump_json(),
            )
            logger.info(
                "Published gh command task",
                command=gh_command,
                conversation_id=conversation_id,
            )

            return {
                "type": "command_result",
                "command": "gh",
                "content": f"Executing: `{gh_command}`...",
                "action": "gh_command",
                "gh_command": gh_command,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        finally:
            await pubsub.stop()

    async def _cmd_git(self, args: str, context: dict[str, Any]) -> dict[str, Any]:
        """
        Handle Git operations.

        Supports: status, push, pull, add, commit, branch, checkout, merge, log, diff, stash, reset.
        Delegates to supervisor for actual command execution.
        """
        conversation_id = context.get("conversation_id")
        user_id = context.get("user_id")
        project_id = context.get("project_id")
        root_path = context.get("root_path")

        # Require a project to be selected
        if not project_id or not root_path:
            return {
                "type": "command_error",
                "command": "git",
                "error": "Git commands require a project to be selected. Please select a project first.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        if not args.strip():
            # Show help for /git command
            return {
                "type": "command_result",
                "command": "git",
                "content": """**Git Commands:**

**Basic:**
- `/git status` - Show working tree status
- `/git add <files|.>` - Stage files for commit
- `/git commit -m "message"` - Commit staged changes
- `/git push [remote] [branch]` - Push commits to remote
- `/git pull [remote] [branch]` - Pull changes from remote

**Branches:**
- `/git branch [name]` - List or create branches
- `/git checkout <branch>` - Switch to a branch
- `/git merge <branch>` - Merge a branch into current

**History & Changes:**
- `/git log [--oneline] [-n N]` - Show commit history
- `/git diff [file]` - Show unstaged changes

**Advanced:**
- `/git stash [pop|list|drop]` - Stash/restore changes
- `/git reset [--hard] [ref]` - Reset HEAD or unstage files""",
                "action": "show_git_help",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        # Build the git command
        git_command = f"git {args.strip()}"

        # Delegate to supervisor to execute the command
        from ai_messaging import TaskRequest

        pubsub = PubSubManager(self.redis)
        await pubsub.start()

        try:
            task_request = TaskRequest(
                task_type="host_command",
                user_id=user_id,
                payload={
                    "command": git_command,
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "project_id": project_id,
                    "root_path": root_path,
                    "working_directory": root_path,
                },
            )
            await pubsub.publish(
                "agent:supervisor:tasks",
                task_request.model_dump_json(),
            )
            logger.info(
                "Published git command task",
                command=git_command,
                conversation_id=conversation_id,
            )

            return {
                "type": "command_result",
                "command": "git",
                "content": f"Executing: `{git_command}`...",
                "action": "git_command",
                "git_command": git_command,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        finally:
            await pubsub.stop()

    async def _cmd_continue(self, args: str, context: dict[str, Any]) -> dict[str, Any]:
        """
        Continue a step that hit max iterations.

        Usage: /continue [additional_iterations]
        """
        # Parse additional iterations (default 10)
        try:
            additional_iterations = int(args.strip()) if args.strip() else 10
            additional_iterations = max(5, min(100, additional_iterations))  # Clamp to 5-100
        except ValueError:
            additional_iterations = 10

        # Return a command result that instructs the frontend to send a continuation message
        # The message will be handled as a regular chat message by the supervisor
        return {
            "type": "command_result",
            "command": "continue",
            "action": "send_message",
            "content": f"Continue the current step with {additional_iterations} additional iterations. Pick up exactly where you left off.",
            "metadata": {
                "continuation": True,
                "additional_iterations": additional_iterations,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _cmd_unknown(self, args: str, context: dict[str, Any]) -> dict[str, Any]:
        """Handle unknown command."""
        return {
            "type": "command_error",
            "command": "unknown",
            "error": "Unknown command. Type /help for available commands.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


def extract_hashtags(content: str) -> list[str]:
    """
    Extract #hashtags from message content.

    Args:
        content: Message content to parse

    Returns:
        List of hashtag strings (without #)
    """
    # Match hashtags that are:
    # - At word boundary or start
    # - Followed by alphanumeric or dash/underscore
    # - Not part of a URL or code block
    pattern = r"(?:^|\s)#([a-zA-Z][a-zA-Z0-9_-]{0,49})(?=\s|$|[.,!?])"
    matches = re.findall(pattern, content)
    return list(set(matches))  # Deduplicate
