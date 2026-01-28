"""
WebSocket message handlers.
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from ai_core import get_logger
from ai_messaging import PubSubManager, RedisClient
from sqlalchemy import select

from ..commands import CommandHandler, extract_hashtags
from ..database import db_session_context
from .manager import Connection, ConnectionManager

logger = get_logger(__name__)


class MessageHandler:
    """
    Handles incoming WebSocket messages and routes them appropriately.
    """

    def __init__(
        self,
        manager: ConnectionManager,
        redis: RedisClient,
    ):
        self.manager = manager
        self.redis = redis
        self.pubsub = PubSubManager(redis)
        self.command_handler = CommandHandler(redis)

    async def _get_conversation_history(
        self, conversation_id: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        Fetch recent conversation history for context.

        Returns list of messages with role, content, timestamp.
        """
        try:
            conv_msgs_key = f"conversation:{conversation_id}:messages"
            # Get recent message IDs (stored newest first via lpush)
            message_ids = await self.redis.lrange(conv_msgs_key, 0, limit - 1)

            if not message_ids:
                return []

            history = []
            for msg_id in reversed(message_ids):  # Reverse to get chronological order
                msg_key = f"message:{msg_id}"
                msg_data = await self.redis.hgetall(msg_key)
                if msg_data:
                    history.append({
                        "role": msg_data.get("role", "user"),
                        "content": msg_data.get("content", ""),
                        "timestamp": msg_data.get("timestamp", ""),
                        "agent": msg_data.get("agent"),
                    })

            return history
        except Exception as e:
            logger.warning("Failed to fetch conversation history", error=str(e))
            return []

    async def _resolve_project_context(self, project_id: str | None) -> dict[str, Any]:
        """
        Resolve project context including root path from project and domains.

        Returns dict with:
        - project_id: str
        - project_name: str
        - root_path: str (project root_path or primary domain web_root)
        - agent_context: str (custom instructions)
        """
        if not project_id:
            return {}

        try:
            from database.models import Project, Domain

            async with db_session_context() as session:
                # Get project with domains
                result = await session.execute(
                    select(Project).where(Project.id == project_id)
                )
                project = result.scalar_one_or_none()

                if not project:
                    return {"project_id": project_id}

                context: dict[str, Any] = {
                    "project_id": project_id,
                    "project_name": project.name,
                    "agent_context": project.agent_context,
                }

                # Priority: project.root_path > primary domain web_root > first domain web_root
                if project.root_path:
                    context["root_path"] = project.root_path
                else:
                    # Check domains for web_root
                    domain_result = await session.execute(
                        select(Domain)
                        .where(Domain.project_id == project_id)
                        .order_by(Domain.is_primary.desc())
                    )
                    domains = domain_result.scalars().all()

                    for domain in domains:
                        if domain.web_root:
                            context["root_path"] = domain.web_root
                            context["domain_name"] = domain.domain_name
                            break

                return context
        except Exception as e:
            logger.debug("Failed to resolve project context", project_id=project_id, error=str(e))
            return {"project_id": project_id}

    async def handle_message(
        self,
        connection: Connection,
        data: dict[str, Any],
    ) -> None:
        """
        Route incoming message to appropriate handler.

        Args:
            connection: The WebSocket connection
            data: Parsed message data
        """
        message_type = data.get("type", "chat")

        handlers = {
            "chat": self._handle_chat_message,
            "ping": self._handle_ping,
            "typing": self._handle_typing,
            "subscribe": self._handle_subscribe,
            "unsubscribe": self._handle_unsubscribe,
            "task_control": self._handle_task_control,
            "add_message": self._handle_add_message,
            "rollback": self._handle_rollback,
            "redo": self._handle_redo,
        }

        handler = handlers.get(message_type)
        if handler:
            try:
                await handler(connection, data)
            except Exception as e:
                logger.error(
                    "Message handler error",
                    type=message_type,
                    error=str(e),
                )
                await self._send_error(connection, str(e))
        else:
            logger.warning("Unknown message type", type=message_type)
            await self._send_error(connection, f"Unknown message type: {message_type}")

    async def _handle_chat_message(
        self,
        connection: Connection,
        data: dict[str, Any],
    ) -> None:
        """
        Handle chat message from user.

        Routes the message to the supervisor agent via Redis.
        Handles slash commands and memory tagging.
        """
        content = data.get("content", "").strip()
        conversation_id = data.get("conversation_id")
        project_id = data.get("project_id")
        branch = data.get("branch")  # Git branch from frontend workspace

        logger.debug(
            "Chat message received",
            user_id=connection.user_id,
            conversation_id=conversation_id,
            has_content=bool(content),
            branch=branch,
            data_keys=list(data.keys()),
        )

        if not content:
            await self._send_error(connection, "Message content is required")
            return

        if not conversation_id:
            logger.warning(
                "Missing conversation_id in chat message",
                user_id=connection.user_id,
                data=data,
            )
            await self._send_error(connection, "Conversation ID is required")
            return

        # Check for slash commands
        if self.command_handler.is_command(content):
            await self._handle_command(connection, content, conversation_id, project_id, branch)
            return

        # Resolve project context (root_path, agent_context, domain info)
        project_context = await self._resolve_project_context(project_id)

        # Extract hashtags for memory tagging
        hashtags = extract_hashtags(content)
        memory_tags = None
        if hashtags:
            memory_tags = hashtags
            logger.debug(
                "Extracted memory tags",
                tags=hashtags,
                user_id=connection.user_id,
            )

        # Use client-provided message_id if available, otherwise generate
        message_id = data.get("message_id") or str(uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        # Store message in Redis
        msg_key = f"message:{message_id}"
        msg_data = {
            "id": message_id,
            "conversation_id": conversation_id,
            "user_id": connection.user_id,
            "role": "user",
            "content": content,
            "timestamp": timestamp,
        }
        if memory_tags:
            msg_data["memory_tags"] = json.dumps(memory_tags)
        await self.redis.hset(msg_key, mapping=msg_data)

        # Add to conversation message list
        conv_msgs_key = f"conversation:{conversation_id}:messages"
        await self.redis.lpush(conv_msgs_key, message_id)

        # Update conversation
        conv_key = f"conversation:{conversation_id}"
        await self.redis.hset(conv_key, "updated_at", timestamp)
        await self.redis.hincrby(conv_key, "message_count", 1)

        # Persist to PostgreSQL asynchronously
        asyncio.create_task(
            self._persist_message_to_db(
                message_id=message_id,
                conversation_id=conversation_id,
                role="user",
                content=content,
                user_id=connection.user_id,
            )
        )

        # Generate conversation title from first message (async, non-blocking)
        asyncio.create_task(
            self._maybe_generate_title(
                conversation_id=conversation_id,
                user_id=connection.user_id,
                user_message=content,
            )
        )

        # If hashtags found, save to memory
        if memory_tags:
            for tag in memory_tags:
                memory_id = str(uuid4())
                memory_key = f"memory:{memory_id}"
                await self.redis.hset(
                    memory_key,
                    mapping={
                        "id": memory_id,
                        "content": content,
                        "tag": tag,
                        "user_id": connection.user_id,
                        "project_id": project_id or "",
                        "conversation_id": conversation_id,
                        "source": "hashtag",
                        "created_at": timestamp,
                    },
                )
                # Add to tag index
                tag_key = f"memory:tag:{tag}"
                await self.redis.lpush(tag_key, memory_id)

            # Send memory saved notification
            await self.manager.send_personal(
                connection.user_id,
                {
                    "type": "memory_saved",
                    "conversation_id": conversation_id,
                    "tags": memory_tags,
                    "timestamp": timestamp,
                },
            )

        # Send acknowledgment to user
        await self.manager.send_personal(
            connection.user_id,
            {
                "type": "message_ack",
                "message_id": message_id,
                "conversation_id": conversation_id,
                "memory_tags": memory_tags,
                "timestamp": timestamp,
            },
        )

        # Check if there's an active/executing plan for this conversation
        active_plan_id = await self.redis.get(f"conversation:{conversation_id}:active_plan")
        plan_is_executing = False
        plan_is_paused = False
        plan_is_pending = False

        if active_plan_id:
            plan_data = await self.redis.get(f"plan:{active_plan_id}")
            if plan_data:
                import json as json_module
                plan = json_module.loads(plan_data)
                plan_status = plan.get("status")
                plan_is_executing = plan_status in ("executing", "approved")
                plan_is_paused = plan_status == "paused"
                plan_is_pending = plan_status == "pending"

        # Route to supervisor agent
        correlation_id = str(uuid4())

        # Handle resume command for paused plans
        content_lower = content.lower().strip()
        if plan_is_paused and content_lower in ("resume", "continue", "go", "start"):
            # Resume the paused plan
            await self.pubsub.publish(
                channel="agent:supervisor:tasks",
                message={
                    "type": "task_request",
                    "task_type": "execute_plan",
                    "correlation_id": correlation_id,
                    "user_id": connection.user_id,
                    "payload": {
                        "plan_id": active_plan_id,
                        "conversation_id": conversation_id,
                        "user_id": connection.user_id,
                        "project_id": project_context.get("project_id"),
                        "root_path": project_context.get("root_path"),
                        "agent_context": project_context.get("agent_context"),
                        "branch": branch,  # Git branch for mismatch detection
                    },
                    "metadata": {
                        "timestamp": timestamp,
                        "project_id": project_id,
                    },
                },
            )
            logger.info(
                "Resuming paused plan",
                plan_id=active_plan_id,
                user_id=connection.user_id,
            )
            # Send acknowledgment
            await self.manager.send_personal(
                connection.user_id,
                {
                    "type": "message",
                    "conversation_id": conversation_id,
                    "content": "▶️ Resuming plan execution...",
                    "agent": "wyld",
                    "timestamp": timestamp,
                },
            )
            return

        # If plan is pending/executing/paused, route messages as plan modifications.
        # When plan is PENDING (just generated, awaiting approval), any chat message
        # is treated as a refinement request — like Claude CLI plan mode where the
        # user iterates on the plan before approving.
        if plan_is_pending or plan_is_executing or plan_is_paused:
            # For pending plans: ALL messages are plan modifications (iterative refinement)
            # For executing/paused: only if message looks like a modification
            should_route_as_modification = plan_is_pending

            if not should_route_as_modification:
                modification_keywords = [
                    "add", "also", "include", "skip", "remove", "delete",
                    "change", "modify", "update", "reorder", "move", "first",
                    "before", "after", "instead", "don't", "stop", "cancel step"
                ]
                should_route_as_modification = any(kw in content_lower for kw in modification_keywords)

            if should_route_as_modification:
                # Send as modify_plan task for Claude to analyze intent
                await self.pubsub.publish(
                    channel="agent:supervisor:tasks",
                    message={
                        "type": "task_request",
                        "task_type": "modify_plan",
                        "correlation_id": correlation_id,
                        "user_id": connection.user_id,
                        "payload": {
                            "plan_id": active_plan_id,
                            "conversation_id": conversation_id,
                            "message": content,
                            "plan_status": "pending" if plan_is_pending else "executing",
                            "project_id": project_context.get("project_id"),
                            "root_path": project_context.get("root_path"),
                            "agent_context": project_context.get("agent_context"),
                            "branch": branch,  # Git branch for plan tracking
                        },
                        "metadata": {
                            "timestamp": timestamp,
                            "project_id": project_id,
                        },
                    },
                )
                logger.info(
                    "Message routed as plan modification",
                    message_id=message_id,
                    plan_id=active_plan_id,
                    plan_status="pending" if plan_is_pending else "executing",
                    user_id=connection.user_id,
                )
                return

        # Fetch recent conversation history for context
        conversation_history = await self._get_conversation_history(conversation_id, limit=10)

        await self.pubsub.publish(
            channel="agent:supervisor:tasks",
            message={
                "type": "task_request",
                "task_type": "chat",
                "correlation_id": correlation_id,
                "user_id": connection.user_id,
                "payload": {
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "content": content,
                    "conversation_history": conversation_history,
                    "memory_tags": memory_tags,
                    "project_id": project_context.get("project_id"),
                    "project_name": project_context.get("project_name"),
                    "root_path": project_context.get("root_path"),
                    "domain": project_context.get("domain_name"),
                    "agent_context": project_context.get("agent_context"),
                    "branch": branch,  # Git branch for plan tracking
                },
                "metadata": {
                    "timestamp": timestamp,
                    "project_id": project_id,
                },
            },
        )

        logger.info(
            "Chat message routed to supervisor",
            message_id=message_id,
            correlation_id=correlation_id,
            user_id=connection.user_id,
            has_memory_tags=bool(memory_tags),
            history_messages=len(conversation_history),
        )

    async def _handle_command(
        self,
        connection: Connection,
        content: str,
        conversation_id: str,
        project_id: str | None,
        branch: str | None = None,
    ) -> None:
        """Handle slash command from user."""
        command, args = self.command_handler.parse_command(content)

        logger.info(
            "Processing command",
            command=command,
            user_id=connection.user_id,
            conversation_id=conversation_id,
            branch=branch,
        )

        # Resolve project context including root_path
        project_context = await self._resolve_project_context(project_id)

        context = {
            "user_id": connection.user_id,
            "conversation_id": conversation_id,
            "project_id": project_id,
            "root_path": project_context.get("root_path"),
            "agent_context": project_context.get("agent_context"),
            "project_name": project_context.get("project_name"),
            "branch": branch,  # Git branch from frontend for plan tracking
        }

        result = await self.command_handler.handle(command, args, context)

        # Store command result as a message in Redis (for persistence)
        # Skip for plan_creating action since supervisor will send the final result
        if result.get("content") and result.get("action") != "plan_creating":
            timestamp = result.get("timestamp") or datetime.now(timezone.utc).isoformat()
            message_id = f"cmd-{uuid4()}"

            # Store message in Redis
            msg_key = f"message:{message_id}"
            await self.redis.hset(
                msg_key,
                mapping={
                    "id": message_id,
                    "conversation_id": conversation_id,
                    "user_id": connection.user_id,
                    "role": "assistant",
                    "content": result.get("content", ""),
                    "agent": "system",
                    "timestamp": timestamp,
                },
            )

            # Add to conversation message list
            conv_msgs_key = f"conversation:{conversation_id}:messages"
            await self.redis.lpush(conv_msgs_key, message_id)

            # Update conversation
            conv_key = f"conversation:{conversation_id}"
            await self.redis.hset(conv_key, "updated_at", timestamp)
            await self.redis.hincrby(conv_key, "message_count", 1)

        # Send command result to user
        await self.manager.send_personal(
            connection.user_id,
            {
                **result,
                "conversation_id": conversation_id,
            },
        )

        # Log command result for debugging
        logger.info(
            "Command result",
            action=result.get("action"),
            command=result.get("command"),
        )

        # Plan mode is handled by the command result message sent above
        # The frontend will display the plan panel based on plan_content/plan_status

    async def _handle_ping(
        self,
        connection: Connection,
        data: dict[str, Any],
    ) -> None:
        """Handle ping/heartbeat message."""
        await connection.websocket.send_json({
            "type": "pong",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def _handle_typing(
        self,
        connection: Connection,
        data: dict[str, Any],
    ) -> None:
        """Handle typing indicator (for future multi-user chat)."""
        conversation_id = data.get("conversation_id")
        if conversation_id:
            # Could broadcast to other users in the conversation
            pass

    async def _handle_subscribe(
        self,
        connection: Connection,
        data: dict[str, Any],
    ) -> None:
        """Handle subscription to specific events."""
        channels = data.get("channels", [])
        # Store subscription info for this connection
        # Implementation depends on subscription model
        await connection.websocket.send_json({
            "type": "subscribed",
            "channels": channels,
        })

    async def _handle_unsubscribe(
        self,
        connection: Connection,
        data: dict[str, Any],
    ) -> None:
        """Handle unsubscription from events."""
        channels = data.get("channels", [])
        await connection.websocket.send_json({
            "type": "unsubscribed",
            "channels": channels,
        })

    async def _handle_task_control(
        self,
        connection: Connection,
        data: dict[str, Any],
    ) -> None:
        """
        Handle task control commands (pause, resume, cancel).

        Allows users to control running agent tasks like Claude CLI.
        """
        action = data.get("action")  # pause, resume, cancel
        conversation_id = data.get("conversation_id")

        if action not in ("pause", "resume", "cancel"):
            await self._send_error(connection, f"Invalid task control action: {action}")
            return

        if not conversation_id:
            await self._send_error(connection, "conversation_id is required for task control")
            return

        logger.info(
            "Task control command",
            action=action,
            user_id=connection.user_id,
            conversation_id=conversation_id,
        )

        # Publish task control command to agents via Redis
        await self.pubsub.publish(
            "agent:task_control",
            {
                "action": action,
                "user_id": connection.user_id,
                "conversation_id": conversation_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        # Send acknowledgment
        await connection.websocket.send_json({
            "type": "task_control_ack",
            "action": action,
            "conversation_id": conversation_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def _handle_add_message(
        self,
        connection: Connection,
        data: dict[str, Any],
    ) -> None:
        """
        Handle adding a message while agent is working.

        Allows users to add context or instructions without waiting for completion.
        """
        content = data.get("content", "").strip()
        conversation_id = data.get("conversation_id")

        if not content:
            await self._send_error(connection, "Message content is required")
            return

        if not conversation_id:
            await self._send_error(connection, "conversation_id is required")
            return

        logger.info(
            "Add message while busy",
            user_id=connection.user_id,
            conversation_id=conversation_id,
            content_length=len(content),
        )

        # Publish the pending message to agents
        await self.pubsub.publish(
            "agent:pending_messages",
            {
                "content": content,
                "user_id": connection.user_id,
                "conversation_id": conversation_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        # Send acknowledgment
        await connection.websocket.send_json({
            "type": "message_queued",
            "content": content[:50] + "..." if len(content) > 50 else content,
            "conversation_id": conversation_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def _handle_rollback(
        self,
        connection: Connection,
        data: dict[str, Any],
    ) -> None:
        """
        Handle rollback request to undo file changes.

        Allows users to revert changes made during plan/step execution.
        """
        plan_id = data.get("plan_id")
        step_id = data.get("step_id")  # Optional - rollback specific step
        dry_run = data.get("dry_run", False)
        info_only = data.get("info_only", False)
        conversation_id = data.get("conversation_id")

        if not plan_id:
            await self._send_error(connection, "plan_id is required for rollback")
            return

        logger.info(
            "Rollback request",
            user_id=connection.user_id,
            plan_id=plan_id,
            step_id=step_id,
            dry_run=dry_run,
            info_only=info_only,
        )

        # Create rollback task request for supervisor
        from ai_messaging import TaskRequest, AgentType

        request = TaskRequest(
            task_type="rollback",
            payload={
                "plan_id": plan_id,
                "step_id": step_id,
                "dry_run": dry_run,
                "info_only": info_only,
                "user_id": connection.user_id,
                "conversation_id": conversation_id,
            },
            target_agent=AgentType.SUPERVISOR,
        )

        # Publish to supervisor task queue
        subscriber_count = await self.pubsub.publish(
            "agent:supervisor:tasks",
            request.model_dump_json(),
        )

        if subscriber_count == 0:
            await self._send_error(connection, "Supervisor agent is not running")
            return

        # Send acknowledgment
        await connection.websocket.send_json({
            "type": "rollback_initiated",
            "plan_id": plan_id,
            "step_id": step_id,
            "dry_run": dry_run,
            "info_only": info_only,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def _handle_redo(
        self,
        connection: Connection,
        data: dict[str, Any],
    ) -> None:
        """
        Handle redo request to reapply rolled-back file changes.

        Allows users to reapply changes that were previously rolled back.
        """
        plan_id = data.get("plan_id")
        task_id = data.get("task_id")
        step_id = data.get("step_id")  # Optional - redo specific step
        dry_run = data.get("dry_run", False)
        conversation_id = data.get("conversation_id")

        if not plan_id and not task_id:
            await self._send_error(connection, "plan_id or task_id is required for redo")
            return

        logger.info(
            "Redo request",
            user_id=connection.user_id,
            plan_id=plan_id,
            task_id=task_id,
            step_id=step_id,
            dry_run=dry_run,
        )

        # Create redo task request for supervisor
        from ai_messaging import TaskRequest, AgentType

        request = TaskRequest(
            task_type="redo",
            payload={
                "plan_id": plan_id,
                "task_id": task_id,
                "step_id": step_id,
                "dry_run": dry_run,
                "user_id": connection.user_id,
                "conversation_id": conversation_id,
            },
            target_agent=AgentType.SUPERVISOR,
        )

        # Publish to supervisor task queue
        subscriber_count = await self.pubsub.publish(
            "agent:supervisor:tasks",
            request.model_dump_json(),
        )

        if subscriber_count == 0:
            await self._send_error(connection, "Supervisor agent is not running")
            return

        # Send acknowledgment
        await connection.websocket.send_json({
            "type": "redo_initiated",
            "plan_id": plan_id,
            "task_id": task_id,
            "step_id": step_id,
            "dry_run": dry_run,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def _persist_message_to_db(
        self,
        message_id: str,
        conversation_id: str,
        role: str,
        content: str,
        agent: str | None = None,
        user_id: str | None = None,
    ) -> None:
        """Persist a message to PostgreSQL asynchronously."""
        try:
            from database.models import Message

            async with db_session_context() as session:
                msg = Message(
                    id=message_id,
                    conversation_id=conversation_id,
                    role=role,
                    content=content,
                    agent=agent,
                    user_id=user_id,
                )
                session.add(msg)
        except Exception as e:
            logger.warning(
                "Failed to persist message to DB",
                message_id=message_id,
                error=str(e),
            )

    async def _send_error(
        self,
        connection: Connection,
        error: str,
    ) -> None:
        """Send error message to connection."""
        try:
            await connection.websocket.send_json({
                "type": "error",
                "error": error,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            logger.warning("Failed to send error", error=str(e))

    async def _maybe_generate_title(
        self,
        conversation_id: str,
        user_id: str,
        user_message: str,
    ) -> None:
        """
        Check if conversation needs a title and generate one from the first message.
        Only generates for conversations with generic titles after the first exchange.
        """
        try:
            from database.models import Conversation

            async with db_session_context() as session:
                result = await session.execute(
                    select(Conversation).where(Conversation.id == conversation_id)
                )
                conversation = result.scalar_one_or_none()

                if not conversation:
                    return

                # Only generate title for new conversations with generic titles
                generic_titles = {
                    None, "", "New Chat", "New Conversation", "Chat with Wyld",
                    "Workspace Chat", "File Assistant", "Untitled"
                }
                if conversation.title not in generic_titles:
                    return

                # Only generate after first message (message_count should be 1 or 2)
                if conversation.message_count > 3:
                    return

                # Generate title using LLM
                title = await self._generate_title_from_message(user_message)

                if title:
                    # Update database
                    conversation.title = title
                    await session.commit()

                    # Publish rename event
                    await self.pubsub.publish(
                        "agent:responses",
                        {
                            "type": "conversation_renamed",
                            "user_id": user_id,
                            "conversation_id": conversation_id,
                            "title": title,
                        },
                    )
                    logger.info(
                        "Auto-generated conversation title",
                        conversation_id=conversation_id,
                        title=title,
                    )
        except Exception as e:
            logger.warning(
                "Failed to generate conversation title",
                conversation_id=conversation_id,
                error=str(e),
            )

    async def _generate_title_from_message(self, message: str) -> str | None:
        """Generate a concise title from the user's message using LLM."""
        import httpx
        import os

        prompt = f"Generate a very short (3-6 words) title for this conversation. Just output the title, nothing else.\n\nUser message: {message[:500]}"

        # Try Anthropic first
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
        if anthropic_key:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={
                            "x-api-key": anthropic_key,
                            "anthropic-version": "2023-06-01",
                            "content-type": "application/json",
                        },
                        json={
                            "model": "claude-3-5-haiku-latest",
                            "max_tokens": 30,
                            "messages": [{"role": "user", "content": prompt}],
                        },
                    )
                    if response.status_code == 200:
                        data = response.json()
                        title = data.get("content", [{}])[0].get("text", "").strip()
                        title = title.strip('"\'').strip()
                        if title:
                            if len(title) > 60:
                                title = title[:57] + "..."
                            return title
            except Exception as e:
                logger.warning("Anthropic title generation failed, trying OpenAI", error=str(e))

        # Try OpenAI as fallback
        openai_key = os.environ.get("OPENAI_API_KEY")
        if openai_key:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {openai_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": "gpt-4o-mini",
                            "max_tokens": 30,
                            "messages": [{"role": "user", "content": prompt}],
                        },
                    )
                    if response.status_code == 200:
                        data = response.json()
                        title = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                        title = title.strip('"\'').strip()
                        if title:
                            if len(title) > 60:
                                title = title[:57] + "..."
                            return title
            except Exception as e:
                logger.warning("OpenAI title generation failed", error=str(e))

        # Final fallback: extract first meaningful words
        words = message.strip().split()[:6]
        if words:
            title = " ".join(words)
            if len(title) > 50:
                title = title[:47] + "..."
            return title
        return None


class AgentResponseHandler:
    """
    Handles responses from agents and routes them to WebSocket clients.

    Listens to Redis pub/sub for agent responses and streams them to users.
    """

    def __init__(
        self,
        manager: ConnectionManager,
        redis: RedisClient,
    ):
        self.manager = manager
        self.redis = redis
        self._running = False

    async def start(self) -> None:
        """Start listening for agent responses."""
        self._running = True
        logger.info("Agent response handler started")

        # Subscribe to agent response channels
        pubsub = self.redis.pubsub()
        await pubsub.subscribe("agent:responses")

        try:
            while self._running:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0,
                )

                if message and message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        await self._handle_agent_response(data)
                    except json.JSONDecodeError:
                        logger.warning("Invalid JSON in agent response")
                    except Exception as e:
                        logger.error("Error handling agent response", error=str(e))

        finally:
            await pubsub.unsubscribe("agent:responses")
            await pubsub.aclose()  # Close connection to prevent memory leak
            logger.info("Agent response handler stopped")

    async def stop(self) -> None:
        """Stop listening for agent responses."""
        self._running = False

    async def _persist_agent_message_to_db(
        self,
        message_id: str,
        conversation_id: str,
        content: str,
        agent: str,
        user_id: str | None = None,
    ) -> None:
        """Persist an agent message to PostgreSQL asynchronously."""
        try:
            from database.models import Message

            async with db_session_context() as session:
                msg = Message(
                    id=message_id,
                    conversation_id=conversation_id,
                    role="assistant",
                    content=content,
                    agent=agent,
                    user_id=user_id,
                )
                session.add(msg)
        except Exception as e:
            logger.warning(
                "Failed to persist agent message to DB",
                message_id=message_id,
                error=str(e),
            )

    async def _maybe_generate_title(
        self,
        conversation_id: str,
        user_id: str,
        user_message: str,
    ) -> None:
        """
        Check if conversation needs a title and generate one from the first message.
        Only generates for conversations with generic titles after the first exchange.
        """
        try:
            from database.models import Conversation

            async with db_session_context() as session:
                result = await session.execute(
                    select(Conversation).where(Conversation.id == conversation_id)
                )
                conversation = result.scalar_one_or_none()

                if not conversation:
                    return

                # Only generate title for new conversations with generic titles
                generic_titles = {
                    None, "", "New Chat", "New Conversation", "Chat with Wyld",
                    "Workspace Chat", "File Assistant", "Untitled"
                }
                if conversation.title not in generic_titles:
                    return

                # Only generate after first message (message_count should be 1 or 2)
                if conversation.message_count > 3:
                    return

                # Generate title using LLM
                title = await self._generate_title_from_message(user_message)

                if title:
                    # Update database
                    conversation.title = title
                    await session.commit()

                    # Publish rename event
                    await self.pubsub.publish(
                        "agent:responses",
                        {
                            "type": "conversation_renamed",
                            "user_id": user_id,
                            "conversation_id": conversation_id,
                            "title": title,
                        },
                    )
                    logger.info(
                        "Auto-generated conversation title",
                        conversation_id=conversation_id,
                        title=title,
                    )
        except Exception as e:
            logger.warning(
                "Failed to generate conversation title",
                conversation_id=conversation_id,
                error=str(e),
            )

    async def _generate_title_from_message(self, message: str) -> str | None:
        """Generate a concise title from the user's message using LLM."""
        try:
            import httpx

            # Use a fast, small model for title generation
            api_key = None
            try:
                import os
                api_key = os.environ.get("ANTHROPIC_API_KEY")
            except Exception:
                pass

            if not api_key:
                # Fallback: extract first meaningful words
                words = message.strip().split()[:8]
                if words:
                    title = " ".join(words)
                    if len(title) > 50:
                        title = title[:47] + "..."
                    return title
                return None

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-3-5-haiku-latest",
                        "max_tokens": 30,
                        "messages": [
                            {
                                "role": "user",
                                "content": f"Generate a very short (3-6 words) title for this conversation. Just output the title, nothing else.\n\nUser message: {message[:500]}",
                            }
                        ],
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    title = data.get("content", [{}])[0].get("text", "").strip()
                    # Clean up and limit length
                    title = title.strip('"\'').strip()
                    if len(title) > 60:
                        title = title[:57] + "..."
                    return title if title else None
                else:
                    logger.warning(
                        "Title generation API call failed",
                        status_code=response.status_code,
                    )
                    return None
        except Exception as e:
            logger.warning("Title generation failed", error=str(e))
            # Fallback: extract first meaningful words
            words = message.strip().split()[:6]
            if words:
                title = " ".join(words)
                if len(title) > 50:
                    title = title[:47] + "..."
                return title
            return None

    async def _maybe_extract_learnings(
        self,
        content: str,
        conversation_id: str,
        project_id: str | None = None,
        agent: str | None = None,
    ) -> None:
        """
        Extract and store learnings from an agent response.

        Uses AI to identify discrete, reusable insights from the response.
        Only extracts significant learnings (code patterns, user preferences, etc.)
        """
        # Skip short or error responses
        if not content or len(content) < 200:
            return

        # Skip if content looks like an error or status message
        error_indicators = ["error", "failed", "cannot", "unable to", "sorry"]
        content_lower = content.lower()[:200]
        if any(ind in content_lower for ind in error_indicators):
            return

        try:
            from ai_core import LLMClient
            from ai_memory import LearningScope, QdrantStore
            from datetime import datetime, timezone

            LEARNINGS_COLLECTION = "agent_learnings"

            # Simple extraction prompt - focused on discrete learnings
            extraction_prompt = """Extract discrete, reusable insights from this AI assistant response.

Focus ONLY on:
- Code patterns or conventions discovered
- User preferences or workflow habits
- Technical gotchas or lessons learned
- Architecture decisions or configurations

Skip:
- Task-specific steps that aren't reusable
- Obvious/trivial information
- General explanations without specific insights

Output a JSON array (or empty array [] if nothing worth learning):
[{"content": "learning text", "category": "pattern|preference|gotcha|architecture", "confidence": 0.5-0.9}]

RESPONSE TO ANALYZE:
"""

            llm = LLMClient()

            # Use fast model for extraction
            response = await llm.create_message(
                model="fast",
                max_tokens=1024,
                system="You extract reusable learnings from text. Output only valid JSON array.",
                messages=[{"role": "user", "content": extraction_prompt + content[:3000]}],
            )

            # Parse response
            import json
            text = response.text_content.strip()
            # Strip markdown code fences if present
            if text.startswith("```"):
                lines = text.split("\n")
                lines = [l for l in lines[1:] if not l.strip().startswith("```")]
                text = "\n".join(lines)

            try:
                learnings = json.loads(text)
            except json.JSONDecodeError:
                return  # No valid learnings extracted

            if not learnings or not isinstance(learnings, list):
                return

            # Store extracted learnings
            store = QdrantStore(collection_name=LEARNINGS_COLLECTION)
            await store.connect()

            stored_count = 0
            for learning in learnings[:5]:  # Max 5 learnings per response
                learning_content = learning.get("content", "")
                if not learning_content or len(learning_content) < 20:
                    continue

                category = learning.get("category", "pattern")
                confidence = learning.get("confidence", 0.7)

                # Only store if confidence is reasonable
                if confidence < 0.5:
                    continue

                # Determine scope
                scope = "project" if project_id else "global"

                metadata = {
                    "category": category,
                    "phase": "learn",
                    "outcome": "success",
                    "confidence": confidence,
                    "agent": agent,
                    "scope": scope,
                    "project_id": project_id,
                    "conversation_id": conversation_id,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "auto_extracted": True,
                }

                await store.upsert(
                    id=None,
                    text=learning_content,
                    metadata=metadata,
                )
                stored_count += 1

            await store.disconnect()

            if stored_count > 0:
                logger.info(
                    "Auto-extracted learnings from response",
                    count=stored_count,
                    conversation_id=conversation_id,
                    project_id=project_id,
                )

        except Exception as e:
            # Don't let learning extraction failures affect the main flow
            logger.debug(
                "Learning extraction failed (non-critical)",
                conversation_id=conversation_id,
                error=str(e),
            )

    async def _handle_agent_response(self, data: dict[str, Any]) -> None:
        """Process an agent response and route to user."""
        user_id = data.get("user_id")
        response_type = data.get("type", "response")

        logger.info(
            "Agent response received",
            response_type=response_type,
            user_id=user_id,
            agent=data.get("agent"),
        )

        if not user_id:
            logger.warning("No user_id in agent response", response_type=response_type, data_keys=list(data.keys()))
            return

        if response_type == "token":
            # Streaming token
            await self.manager.send_personal(
                user_id,
                {
                    "type": "token",
                    "conversation_id": data.get("conversation_id"),
                    "message_id": data.get("message_id"),
                    "token": data.get("token"),
                    "agent": data.get("agent"),
                },
            )

        elif response_type == "response":
            # Complete response - store in Redis
            conversation_id = data.get("conversation_id")
            message_id = data.get("message_id")
            content = data.get("content")
            agent = data.get("agent")
            timestamp = data.get("timestamp")

            if conversation_id and content:
                # Generate message ID for agent response
                agent_message_id = f"agent-{message_id or uuid4()}"

                # Store message in Redis
                msg_key = f"message:{agent_message_id}"
                await self.redis.hset(
                    msg_key,
                    mapping={
                        "id": agent_message_id,
                        "conversation_id": conversation_id,
                        "user_id": user_id,
                        "role": "assistant",
                        "content": content,
                        "agent": agent or "supervisor",
                        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
                    },
                )

                # Add to conversation message list
                conv_msgs_key = f"conversation:{conversation_id}:messages"
                await self.redis.lpush(conv_msgs_key, agent_message_id)

                # Update conversation
                conv_key = f"conversation:{conversation_id}"
                await self.redis.hset(conv_key, "updated_at", timestamp or datetime.now(timezone.utc).isoformat())
                await self.redis.hincrby(conv_key, "message_count", 1)

                # Persist to PostgreSQL asynchronously
                asyncio.create_task(
                    self._persist_agent_message_to_db(
                        message_id=agent_message_id,
                        conversation_id=conversation_id,
                        content=content,
                        agent=agent or "supervisor",
                        user_id=user_id,
                    )
                )

                # Extract learnings from the response as a background task
                # Get project_id from conversation (agent response may not include it)
                project_id = data.get("project_id")
                if not project_id and conversation_id:
                    # Look up from conversation in Redis
                    conv_project_id = await self.redis.hget(f"conversation:{conversation_id}", "project_id")
                    if conv_project_id:
                        project_id = conv_project_id

                asyncio.create_task(
                    self._maybe_extract_learnings(
                        content=content,
                        conversation_id=conversation_id,
                        project_id=project_id,
                        agent=agent or "supervisor",
                    )
                )

            # Send to WebSocket (include usage data if available)
            ws_message: dict[str, Any] = {
                "type": "message",
                "conversation_id": conversation_id,
                "message_id": message_id,
                "content": content,
                "agent": agent,
                "timestamp": timestamp,
                "role": "assistant",
            }
            usage = data.get("usage")
            if usage:
                ws_message["usage"] = usage

            await self.manager.send_personal(user_id, ws_message)

        elif response_type == "status":
            # Agent status update
            await self.manager.send_personal(
                user_id,
                {
                    "type": "agent_status",
                    "agent": data.get("agent"),
                    "status": data.get("status"),
                    "task": data.get("task"),
                },
            )

        elif response_type == "action":
            # Real-time action update (Claude Code-style)
            sent_count = await self.manager.send_personal(
                user_id,
                {
                    "type": "agent_action",
                    "agent": data.get("agent"),
                    "action": data.get("action"),
                    "description": data.get("description"),
                    "conversation_id": data.get("conversation_id"),
                    "timestamp": data.get("timestamp"),
                },
            )
            logger.debug(
                "Action sent to user",
                user_id=user_id,
                agent=data.get("agent"),
                action=data.get("action"),
                sent_count=sent_count,
            )

        elif response_type == "thinking_stream":
            # Narrative thinking/reasoning stream (Thinking panel)
            sent_count = await self.manager.send_personal(
                user_id,
                {
                    "type": "thinking_stream",
                    "thought_type": data.get("thought_type"),
                    "content": data.get("content"),
                    "context": data.get("context"),
                    "agent": data.get("agent"),
                    "conversation_id": data.get("conversation_id"),
                    "timestamp": data.get("timestamp"),
                },
            )
            logger.debug(
                "Thinking stream sent to user",
                user_id=user_id,
                agent=data.get("agent"),
                thought_type=data.get("thought_type"),
                content_preview=data.get("content", "")[:50] if data.get("content") else None,
                sent_count=sent_count,
            )

        elif response_type == "quality_check_result":
            # Quality check result after task completion
            await self.manager.send_personal(
                user_id,
                {
                    "type": "quality_check_result",
                    "conversation_id": data.get("conversation_id"),
                    "task_id": data.get("task_id"),
                    "passed": data.get("passed", True),
                    "errors": data.get("errors", []),
                    "checks_run": data.get("checks_run", []),
                    "agent": data.get("agent"),
                    "timestamp": data.get("timestamp"),
                },
            )
            logger.info(
                "Quality check result sent to user",
                user_id=user_id,
                task_id=data.get("task_id"),
                passed=data.get("passed"),
                error_count=len(data.get("errors", [])),
            )

        elif response_type == "rollback_complete":
            # Rollback operation completed
            await self.manager.send_personal(
                user_id,
                {
                    "type": "rollback_complete",
                    "plan_id": data.get("plan_id"),
                    "task_id": data.get("task_id"),
                    "step_id": data.get("step_id"),
                    "files_restored": data.get("files_restored", []),
                    "files_deleted": data.get("files_deleted", []),
                    "conversation_id": data.get("conversation_id"),
                    "timestamp": data.get("timestamp"),
                },
            )
            logger.info(
                "Rollback complete sent to user",
                user_id=user_id,
                plan_id=data.get("plan_id"),
                task_id=data.get("task_id"),
                files_count=len(data.get("files_restored", [])) + len(data.get("files_deleted", [])),
            )

        elif response_type == "redo_complete":
            # Redo operation completed
            await self.manager.send_personal(
                user_id,
                {
                    "type": "redo_complete",
                    "plan_id": data.get("plan_id"),
                    "task_id": data.get("task_id"),
                    "step_id": data.get("step_id"),
                    "files_reapplied": data.get("files_reapplied", []),
                    "files_created": data.get("files_created", []),
                    "conversation_id": data.get("conversation_id"),
                    "timestamp": data.get("timestamp"),
                },
            )
            logger.info(
                "Redo complete sent to user",
                user_id=user_id,
                plan_id=data.get("plan_id"),
                task_id=data.get("task_id"),
                files_count=len(data.get("files_reapplied", [])) + len(data.get("files_created", [])),
            )

        elif response_type == "error":
            # Error from agent
            await self.manager.send_personal(
                user_id,
                {
                    "type": "error",
                    "conversation_id": data.get("conversation_id"),
                    "error": data.get("error"),
                    "agent": data.get("agent"),
                },
            )

        elif response_type == "plan_update":
            # Plan content update (Claude CLI style)
            conversation_id = data.get("conversation_id")
            plan_content = data.get("plan_content")
            plan_status_str = data.get("plan_status")
            timestamp = data.get("timestamp") or datetime.now(timezone.utc).isoformat()

            # Save plan to database (required for approve/reject to work)
            if conversation_id and plan_content:
                try:
                    # Import here to avoid circular imports
                    from database.models import Conversation, PlanStatus

                    async with db_session_context() as db:
                        result = await db.execute(
                            select(Conversation).where(Conversation.id == conversation_id)
                        )
                        conversation = result.scalar_one_or_none()

                        if conversation:
                            conversation.plan_content = plan_content
                            if plan_status_str:
                                try:
                                    conversation.plan_status = PlanStatus(plan_status_str.lower())
                                except ValueError:
                                    conversation.plan_status = PlanStatus.PENDING
                            else:
                                conversation.plan_status = PlanStatus.PENDING

                            logger.info(
                                "Plan saved to database",
                                conversation_id=conversation_id,
                                plan_status=conversation.plan_status.value,
                            )
                        else:
                            logger.warning(
                                "Conversation not found for plan update",
                                conversation_id=conversation_id,
                            )
                except Exception as e:
                    logger.error(
                        "Failed to save plan to database",
                        conversation_id=conversation_id,
                        error=str(e),
                    )

            await self.manager.send_personal(
                user_id,
                {
                    "type": "plan_update",
                    "conversation_id": conversation_id,
                    "plan_content": plan_content,
                    "plan_status": plan_status_str,
                    "branch": data.get("branch"),
                    "agent": data.get("agent"),
                    "timestamp": timestamp,
                },
            )
            logger.debug(
                "Plan update sent to user",
                user_id=user_id,
                conversation_id=conversation_id,
                plan_status=plan_status_str,
                branch=data.get("branch"),
            )

        elif response_type == "plan_status":
            # Plan status change notification
            await self.manager.send_personal(
                user_id,
                {
                    "type": "plan_status",
                    "conversation_id": data.get("conversation_id"),
                    "plan_status": data.get("plan_status"),
                    "timestamp": data.get("timestamp"),
                },
            )

        elif response_type == "step_update":
            # Plan step progress update (todo-style checkboxes)
            await self.manager.send_personal(
                user_id,
                {
                    "type": "step_update",
                    "conversation_id": data.get("conversation_id"),
                    "plan_id": data.get("plan_id"),
                    "steps": data.get("steps", []),
                    "current_step": data.get("current_step", 0),
                    "agent": data.get("agent"),
                    "timestamp": data.get("timestamp"),
                },
            )
            logger.debug(
                "Step update sent to user",
                user_id=user_id,
                conversation_id=data.get("conversation_id"),
                current_step=data.get("current_step"),
            )

        elif response_type == "todo_progress":
            # Individual todo item progress within a step
            await self.manager.send_personal(
                user_id,
                {
                    "type": "todo_progress",
                    "conversation_id": data.get("conversation_id"),
                    "plan_id": data.get("plan_id"),
                    "step_id": data.get("step_id"),
                    "todo_index": data.get("todo_index"),
                    "progress": data.get("progress", 0),
                    "status_message": data.get("status_message", ""),
                    "timestamp": data.get("timestamp"),
                },
            )
            logger.debug(
                "Todo progress sent to user",
                user_id=user_id,
                step_id=data.get("step_id"),
                todo_index=data.get("todo_index"),
                progress=data.get("progress"),
            )

        elif response_type == "conversation_renamed":
            # Conversation title was auto-generated
            await self.manager.send_personal(
                user_id,
                {
                    "type": "conversation_renamed",
                    "conversation_id": data.get("conversation_id"),
                    "title": data.get("title"),
                },
            )
            logger.info(
                "Conversation renamed",
                user_id=user_id,
                conversation_id=data.get("conversation_id"),
                title=data.get("title"),
            )

        elif response_type == "usage_update":
            # Real-time API usage update for frontend meter
            await self.manager.send_personal(
                user_id,
                {
                    "type": "usage_update",
                    "conversation_id": data.get("conversation_id"),
                    "input_tokens": data.get("input_tokens", 0),
                    "output_tokens": data.get("output_tokens", 0),
                    "cached_tokens": data.get("cached_tokens", 0),
                    "cost": data.get("cost", 0),
                    "model": data.get("model"),
                },
            )
            logger.debug(
                "Usage update sent to user",
                user_id=user_id,
                input_tokens=data.get("input_tokens"),
                output_tokens=data.get("output_tokens"),
                cost=data.get("cost"),
            )

        elif response_type == "branch_mismatch_warning":
            # Warning when plan branch differs from current branch
            await self.manager.send_personal(
                user_id,
                {
                    "type": "branch_mismatch_warning",
                    "conversation_id": data.get("conversation_id"),
                    "plan_branch": data.get("plan_branch"),
                    "current_branch": data.get("current_branch"),
                    "timestamp": data.get("timestamp"),
                },
            )
            logger.info(
                "Branch mismatch warning sent to user",
                user_id=user_id,
                conversation_id=data.get("conversation_id"),
                plan_branch=data.get("plan_branch"),
                current_branch=data.get("current_branch"),
            )
