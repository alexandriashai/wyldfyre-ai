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

from .plan_mode import Plan, PlanManager, PlanStatus, format_plan_for_display

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
        "description": "Enter planning mode for structured task breakdown",
        "usage": "/plan [task description]",
        "aliases": ["p"],
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
        """Enter planning mode or manage existing plan."""
        conversation_id = context.get("conversation_id")
        user_id = context.get("user_id")
        project_id = context.get("project_id")

        # Check for existing plan
        existing_plan = await self.plan_manager.get_active_plan(conversation_id)

        # Handle plan subcommands
        subcommands = {"approve", "reject", "cancel", "status", "pause", "resume"}

        if args:
            args_lower = args.lower().strip()

            # Check if this is a subcommand that requires an existing plan
            if args_lower in subcommands:
                if not existing_plan:
                    return {
                        "type": "command_error",
                        "command": "plan",
                        "error": f"No active plan to {args_lower}. Use `/plan [description]` to create one.",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }

                # Approve existing plan
                if args_lower == "approve":
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
                if args_lower in ("reject", "cancel"):
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
                if args_lower == "status":
                    return {
                        "type": "command_result",
                        "command": "plan",
                        "content": format_plan_for_display(existing_plan),
                        "action": "plan_status",
                        "plan": existing_plan.to_dict(),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }

                # Pause execution
                if args_lower == "pause":
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
                if args_lower == "resume":
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

        # Create new plan with intelligent exploration
        if args:
            plan = await self.plan_manager.create_plan(
                conversation_id=conversation_id,
                user_id=user_id,
                title=args[:100],
                description=args,
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

- `/plan [task description]` - Create a new plan for a task
- `/plan status` - Show current plan status
- `/plan approve` - Approve the current plan
- `/plan reject` - Cancel the current plan
- `/plan pause` - Pause plan execution
- `/plan resume` - Resume paused execution

**Example:**
`/plan Add user authentication with JWT tokens`""",
            "action": "plan_help",
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
