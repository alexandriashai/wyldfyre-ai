"""
Terminal WebSocket endpoint supporting both tmux and Docker exec modes.

For legacy projects: Uses tmux for persistent shell sessions
For Docker projects: Uses docker exec for container isolation
"""

import asyncio
import os
import pty
import struct
import fcntl
import termios
import subprocess

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect

from ai_core import get_logger
from ai_messaging import RedisClient

from ..config import get_api_config
from ..dependencies import get_redis
from ..services.auth_service import AuthService, TokenPayload

logger = get_logger(__name__)

router = APIRouter(tags=["Terminal"])


async def get_user_from_token(token: str) -> TokenPayload | None:
    """Validate token for WebSocket authentication."""
    try:
        config = get_api_config()
        auth_service = AuthService(db=None, config=config)  # type: ignore
        return auth_service.verify_token(token)
    except Exception as e:
        logger.warning("Terminal WebSocket auth failed", error=str(e))
        return None


def set_terminal_size(fd: int, rows: int, cols: int) -> None:
    """Set the terminal size for the PTY."""
    winsize = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)


def get_tmux_session_name(user_id: str, project_id: str) -> str:
    """Generate a stable tmux session name for a user+project."""
    return f"wyld-{user_id[:8]}-{project_id[:8]}"


def get_container_name(project_id: str) -> str:
    """Generate container name from project ID."""
    return f"wyld-project-{project_id[:12]}"


def get_pai_env_vars(
    token: str,
    project_id: str,
    project_name: str,
    root_path: str,
) -> dict[str, str]:
    """Generate environment variables for PAI/Claude integration."""
    api_url = os.environ.get("API_BASE_URL", "http://localhost:8000")
    cli_path = "/home/wyld-core/packages/cli"

    return {
        "PAI_API_URL": api_url,
        "PAI_TOKEN": token,
        "PAI_PROJECT_ID": project_id,
        "PAI_PROJECT_NAME": project_name,
        "PAI_PROJECT_ROOT": root_path,
        # Note: Do NOT set ANTHROPIC_AUTH_TOKEN - it conflicts with Claude CLI OAuth
        "PATH": f"{cli_path}:{os.environ.get('PATH', '/usr/bin')}",
        "TERM": "xterm-256color",  # Ensure terminal capabilities work
        # Point Claude CLI to shared credentials location
        "CLAUDE_CONFIG_DIR": "/home/wyld-api/.claude",
    }


def get_env_unsets() -> list[str]:
    """Return list of environment variables to unset in terminal sessions.

    This prevents API keys from being inherited by terminal sessions,
    allowing users to use their own Claude subscription credentials.
    """
    return [
        "ANTHROPIC_API_KEY",  # Don't pass API key - let users use their subscription
    ]


def get_docker_env_vars(
    token: str,
    project_id: str,
    project_name: str,
) -> dict[str, str]:
    """Generate environment variables for Docker container sessions.

    Note: ANTHROPIC_API_KEY is intentionally NOT passed to allow users
    to use their own Claude subscription credentials instead.
    """
    # In Docker, the API URL needs to use host.docker.internal
    api_url = os.environ.get("API_BASE_URL", "http://host.docker.internal:8000")

    return {
        "PAI_API_URL": api_url,
        "PAI_TOKEN": token,
        "PAI_PROJECT_ID": project_id,
        "PAI_PROJECT_NAME": project_name,
        "PAI_PROJECT_ROOT": "/app",  # Standard mount point in container
        # Note: Do NOT set ANTHROPIC_AUTH_TOKEN - it conflicts with Claude CLI OAuth
        "TERM": "xterm-256color",  # Required for Claude CLI and proper terminal behavior
        "CLAUDE_CONFIG_DIR": "/home/wyld/.claude-local",  # Writable config location
    }


def user_exists(username: str) -> bool:
    """Check if a system user exists."""
    try:
        result = subprocess.run(["id", username], capture_output=True)
        return result.returncode == 0
    except Exception:
        return False


def ensure_tmux_session(
    session_name: str,
    root_path: str,
    terminal_user: str | None = None,
    env_vars: dict[str, str] | None = None,
) -> bool:
    """Ensure a tmux session exists, creating one if needed."""
    # Check if terminal_user exists - if not, run as current user
    use_sudo = terminal_user and user_exists(terminal_user)
    if terminal_user and not use_sudo:
        logger.warning(f"Terminal user '{terminal_user}' does not exist, running as current user")

    # Check if session exists
    check_cmd = ["tmux", "has-session", "-t", session_name]
    if use_sudo:
        check_cmd = ["sudo", "-u", terminal_user, "--"] + check_cmd

    result = subprocess.run(check_cmd, capture_output=True)
    if result.returncode == 0:
        # Session exists - update environment variables
        if env_vars:
            for key, value in env_vars.items():
                set_env_cmd = ["tmux", "set-environment", "-t", session_name, key, value]
                if use_sudo:
                    set_env_cmd = ["sudo", "-u", terminal_user, "--"] + set_env_cmd
                subprocess.run(set_env_cmd, capture_output=True)
        return True

    # Build environment string for new session
    env_str = ""
    if env_vars:
        env_exports = " ".join([f'{k}="{v}"' for k, v in env_vars.items()])
        env_str = f"export {env_exports}; "

    # Write PAI environment to file for persistence
    if env_vars and use_sudo:
        pai_env_file = os.path.join(root_path, ".pai_env")
        try:
            env_content = "\n".join([f'export {k}="{v}"' for k, v in env_vars.items()])
            with open(pai_env_file, "w") as f:
                f.write(env_content + "\n")
            # Set ownership to terminal user
            subprocess.run(["chown", terminal_user, pai_env_file], capture_output=True)
        except Exception as e:
            logger.warning(f"Failed to write PAI env file: {e}")

    # Create new session with proper terminal type
    shell = "bash"
    # Unset inherited env vars that shouldn't be in terminal (e.g., ANTHROPIC_API_KEY)
    unset_str = " ".join([f"unset {var};" for var in get_env_unsets()])
    shell_cmd = f'{unset_str} {env_str}exec {shell} --login'

    create_cmd = [
        "tmux", "-2",  # Force 256 color support
        "new-session",
        "-d",  # Detached
        "-s", session_name,
        "-c", root_path,  # Start in project root
        "-x", "80", "-y", "24",  # Initial size
        "bash", "-c", shell_cmd,
    ]
    if use_sudo:
        create_cmd = ["sudo", "-u", terminal_user, "-i", "--"] + create_cmd

    result = subprocess.run(create_cmd, capture_output=True)

    # Set environment variables in the session
    if result.returncode == 0 and env_vars:
        for key, value in env_vars.items():
            set_env_cmd = ["tmux", "set-environment", "-t", session_name, key, value]
            if use_sudo:
                set_env_cmd = ["sudo", "-u", terminal_user, "--"] + set_env_cmd
            subprocess.run(set_env_cmd, capture_output=True)

    return result.returncode == 0


def is_container_running(container_name: str) -> bool:
    """Check if a Docker container is running."""
    result = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", container_name],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def start_container(container_name: str) -> bool:
    """Start a Docker container if it exists but isn't running."""
    result = subprocess.run(
        ["docker", "start", container_name],
        capture_output=True,
    )
    return result.returncode == 0


@router.websocket("/ws/terminal")
async def websocket_terminal(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token"),
    project_id: str = Query(..., description="Project ID for session scoping"),
    root_path: str = Query("/tmp", description="Working directory for terminal"),
    terminal_user: str | None = Query(None, description="System user to run as (legacy mode)"),
    project_name: str = Query("", description="Project name for context"),
    docker_enabled: bool = Query(False, description="Use Docker container instead of tmux"),
) -> None:
    """
    WebSocket endpoint for terminal shell access.

    Supports two modes:
    1. Docker mode (docker_enabled=True): Connects to project's Docker container
    2. Legacy mode (docker_enabled=False): Uses tmux sessions

    Features:
    - PAI memory CLI access (pai-memory command)
    - Claude Code with session passthrough (wyld-claude command)
    - Project context injection
    """
    # Authenticate
    user = await get_user_from_token(token)
    if not user:
        await websocket.close(code=4001, reason="Authentication failed")
        return

    await websocket.accept()

    if docker_enabled:
        # Docker container mode
        await handle_docker_terminal(
            websocket=websocket,
            user=user,
            project_id=project_id,
            project_name=project_name,
            token=token,
        )
    else:
        # Legacy tmux mode
        await handle_tmux_terminal(
            websocket=websocket,
            user=user,
            project_id=project_id,
            project_name=project_name,
            root_path=root_path,
            terminal_user=terminal_user,
            token=token,
        )


def setup_docker_tmux_env(container_name: str, session_name: str, env_vars: dict[str, str]) -> None:
    """Set up environment variables and options for a tmux session inside a Docker container."""
    # Check if session exists and set environment variables
    check_result = subprocess.run(
        ["docker", "exec", "-u", "wyld", container_name, "tmux", "has-session", "-t", session_name],
        capture_output=True,
    )

    if check_result.returncode == 0:
        # Session exists - update environment variables
        for key, value in env_vars.items():
            subprocess.run(
                ["docker", "exec", "-u", "wyld", container_name, "tmux", "set-environment", "-t", session_name, key, value],
                capture_output=True,
            )

    # Set tmux options for better resize behavior and mouse support
    tmux_options = [
        ("window-size", "latest"),    # Use size of most recently active client
        ("mouse", "on"),              # Enable mouse scrolling and selection
        ("history-limit", "10000"),   # Increase scrollback buffer
    ]
    for option, value in tmux_options:
        subprocess.run(
            ["docker", "exec", "-u", "wyld", container_name, "tmux", "set-option", "-g", option, value],
            capture_output=True,
        )


def fix_container_permissions(container_name: str) -> None:
    """Fix file permissions in container so wyld user can edit files."""
    try:
        # Run chown as root to fix /app ownership
        subprocess.run(
            [
                "docker", "exec", "-u", "root", container_name,
                "chown", "-R", "wyld:wyld", "/app",
            ],
            capture_output=True,
            timeout=30,
        )
        logger.debug(f"Fixed permissions in container: {container_name}")
    except Exception as e:
        logger.warning(f"Failed to fix permissions: {e}")


async def handle_docker_terminal(
    websocket: WebSocket,
    user: TokenPayload,
    project_id: str,
    project_name: str,
    token: str,
) -> None:
    """Handle terminal connection via Docker exec with persistent tmux session."""
    container_name = get_container_name(project_id)
    session_name = f"wyld-{project_id[:8]}"

    # Check if container is running
    if not is_container_running(container_name):
        # Try to start it
        if not start_container(container_name):
            await websocket.send_text('{"error": "Container not running. Start it from project settings."}')
            await websocket.close(code=4002, reason="Container not running")
            return

    # Fix file permissions so wyld user can edit files
    fix_container_permissions(container_name)

    # Prepare environment variables for the container session
    env_vars = get_docker_env_vars(
        token=token,
        project_id=project_id,
        project_name=project_name,
    )

    # Set up tmux environment (if session exists)
    setup_docker_tmux_env(container_name, session_name, env_vars)

    # Build environment string for shell
    env_exports = " ".join([f'export {k}="{v}";' for k, v in env_vars.items()])

    # Spawn PTY for docker exec to attach to tmux
    master_fd, slave_fd = pty.openpty()

    pid = os.fork()
    if pid == 0:
        # Child process - execute docker exec to attach/create tmux session
        os.close(master_fd)
        os.setsid()
        os.dup2(slave_fd, 0)
        os.dup2(slave_fd, 1)
        os.dup2(slave_fd, 2)
        os.close(slave_fd)

        # Use tmux new-session -A which attaches to existing session or creates new one
        # Detach other clients first, then attach with size hints
        exec_cmd = [
            "docker", "exec",
            "-it",
            "-u", "wyld",  # Run as wyld user inside container
            "-w", "/app",  # Working directory
            "-e", f"TMUX_ENV={env_exports}",  # Pass env vars
            container_name,
            "bash", "-c",
            # Detach other clients, set aggressive-resize, then attach
            f'{env_exports} tmux set-option -g aggressive-resize on 2>/dev/null; '
            f'tmux detach-client -a -t {session_name} 2>/dev/null; '
            f'exec tmux new-session -A -s {session_name}',
        ]
        os.execvp("docker", exec_cmd)
        os._exit(1)

    # Parent process
    os.close(slave_fd)
    set_terminal_size(master_fd, 24, 80)

    # Make master_fd non-blocking
    flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
    fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    logger.info(
        "Docker terminal attached",
        user_id=user.sub,
        project_id=project_id,
        container=container_name,
        session=session_name,
        pid=pid,
    )

    await run_terminal_loop(
        websocket, master_fd, pid, user.sub, container_name,
        docker_container=container_name, docker_session=session_name
    )


async def handle_tmux_terminal(
    websocket: WebSocket,
    user: TokenPayload,
    project_id: str,
    project_name: str,
    root_path: str,
    terminal_user: str | None,
    token: str,
) -> None:
    """Handle terminal connection via tmux (legacy mode)."""
    # Validate root_path
    if not os.path.isdir(root_path):
        root_path = "/tmp"

    # Prepare environment variables for PAI/Claude integration
    pai_env = get_pai_env_vars(
        token=token,
        project_id=project_id,
        project_name=project_name,
        root_path=root_path,
    )

    # Check if terminal_user exists
    use_sudo = terminal_user and user_exists(terminal_user)

    # Ensure tmux session exists with PAI environment
    session_name = get_tmux_session_name(user.sub, project_id)
    if not ensure_tmux_session(session_name, root_path, terminal_user, pai_env):
        await websocket.send_text('{"error": "Failed to create terminal session"}')
        await websocket.close(code=4002, reason="Session creation failed")
        return

    # Spawn PTY that attaches to the tmux session
    master_fd, slave_fd = pty.openpty()

    pid = os.fork()
    if pid == 0:
        # Child process - attach to tmux as scoped user or current user
        os.close(master_fd)
        os.setsid()
        os.dup2(slave_fd, 0)
        os.dup2(slave_fd, 1)
        os.dup2(slave_fd, 2)
        os.close(slave_fd)
        # Set TERM before attaching
        os.environ["TERM"] = "xterm-256color"
        if use_sudo:
            # Run tmux attach as the configured project user
            os.execvp("sudo", [
                "sudo", "-u", terminal_user, "--",
                "tmux", "-2", "attach-session", "-t", session_name,
            ])
        else:
            os.execvp("tmux", ["tmux", "-2", "attach-session", "-t", session_name])
        os._exit(1)

    # Parent process
    os.close(slave_fd)
    set_terminal_size(master_fd, 24, 80)

    # Make master_fd non-blocking
    flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
    fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    logger.info(
        "Tmux terminal attached",
        user_id=user.sub,
        project_id=project_id,
        session=session_name,
        pid=pid,
    )

    await run_terminal_loop(websocket, master_fd, pid, user.sub, session_name)


def resize_docker_tmux(container_name: str, session_name: str, rows: int, cols: int) -> None:
    """Resize a tmux session inside a Docker container."""
    try:
        # Detach all other clients first - they may be limiting the size
        subprocess.run(
            [
                "docker", "exec", "-u", "wyld", container_name,
                "tmux", "detach-client", "-a", "-t", session_name,
            ],
            capture_output=True,
            timeout=5,
        )

        # Force window size using set-window-option
        subprocess.run(
            [
                "docker", "exec", "-u", "wyld", container_name,
                "tmux", "set-window-option", "-t", session_name, "force-width", str(cols),
            ],
            capture_output=True,
            timeout=5,
        )
        subprocess.run(
            [
                "docker", "exec", "-u", "wyld", container_name,
                "tmux", "set-window-option", "-t", session_name, "force-height", str(rows),
            ],
            capture_output=True,
            timeout=5,
        )

        # Explicitly resize the window
        subprocess.run(
            [
                "docker", "exec", "-u", "wyld", container_name,
                "tmux", "resize-window", "-t", session_name, "-x", str(cols), "-y", str(rows),
            ],
            capture_output=True,
            timeout=5,
        )

        # Resize the pane as well
        subprocess.run(
            [
                "docker", "exec", "-u", "wyld", container_name,
                "tmux", "resize-pane", "-t", session_name, "-x", str(cols), "-y", str(rows),
            ],
            capture_output=True,
            timeout=5,
        )

        # Refresh the client
        subprocess.run(
            [
                "docker", "exec", "-u", "wyld", container_name,
                "tmux", "refresh-client", "-S",
            ],
            capture_output=True,
            timeout=5,
        )
    except Exception:
        pass  # Best effort resize


def refresh_docker_tmux(container_name: str, session_name: str) -> None:
    """Force refresh a tmux session to pick up current terminal size."""
    try:
        # Detach other clients that might be limiting size
        subprocess.run(
            [
                "docker", "exec", "-u", "wyld", container_name,
                "tmux", "detach-client", "-a", "-t", session_name,
            ],
            capture_output=True,
            timeout=5,
        )

        # Force refresh all clients
        subprocess.run(
            [
                "docker", "exec", "-u", "wyld", container_name,
                "tmux", "refresh-client", "-S",
            ],
            capture_output=True,
            timeout=5,
        )

        # Also send SIGWINCH to the shell to force it to check size
        subprocess.run(
            [
                "docker", "exec", "-u", "wyld", container_name,
                "tmux", "send-keys", "-t", session_name, "", "",  # Empty to trigger refresh
            ],
            capture_output=True,
            timeout=5,
        )
    except Exception:
        pass  # Best effort refresh


async def run_terminal_loop(
    websocket: WebSocket,
    master_fd: int,
    pid: int,
    user_id: str,
    session_id: str,
    docker_container: str | None = None,
    docker_session: str | None = None,
) -> None:
    """Main terminal I/O loop for both Docker and tmux modes."""

    async def read_from_pty():
        """Read output from PTY and send to WebSocket."""
        import errno
        try:
            while True:
                await asyncio.sleep(0.01)
                try:
                    data = os.read(master_fd, 4096)
                    if data:
                        await websocket.send_bytes(data)
                except OSError as e:
                    # EAGAIN/EWOULDBLOCK means no data available yet (non-blocking)
                    if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                        continue
                    # Other OSError means PTY closed
                    break
                except Exception:
                    break
        except asyncio.CancelledError:
            pass

    read_task = asyncio.create_task(read_from_pty())

    try:
        while True:
            message = await websocket.receive()

            if message.get("type") == "websocket.disconnect":
                break

            if "bytes" in message:
                os.write(master_fd, message["bytes"])
            elif "text" in message:
                try:
                    import json
                    control = json.loads(message["text"])
                    if control.get("type") == "resize":
                        rows = control.get("rows", 24)
                        cols = control.get("cols", 80)
                        set_terminal_size(master_fd, rows, cols)
                        # Also resize tmux session inside Docker container
                        if docker_container and docker_session:
                            resize_docker_tmux(docker_container, docker_session, rows, cols)
                    elif control.get("type") == "tmux-refresh":
                        # Force tmux to refresh and pick up current size
                        if docker_container and docker_session:
                            refresh_docker_tmux(docker_container, docker_session)
                    elif control.get("type") == "input":
                        os.write(master_fd, control["data"].encode())
                except (json.JSONDecodeError, KeyError):
                    os.write(master_fd, message["text"].encode())

    except WebSocketDisconnect:
        logger.info("Terminal disconnected", user_id=user_id, session=session_id)
    except Exception as e:
        logger.error("Terminal error", error=str(e), user_id=user_id)
    finally:
        read_task.cancel()
        try:
            await read_task
        except asyncio.CancelledError:
            pass

        os.close(master_fd)
        try:
            os.kill(pid, 9)
            os.waitpid(pid, 0)
        except (OSError, ChildProcessError):
            pass

        logger.info("Terminal detached", user_id=user_id, session=session_id)
