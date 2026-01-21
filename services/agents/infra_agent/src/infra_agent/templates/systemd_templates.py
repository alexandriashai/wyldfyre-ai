"""
Systemd unit file templates.
"""

from string import Template


# Basic service template
SYSTEMD_SERVICE_TEMPLATE = Template("""[Unit]
Description=${description}
After=${after}
${wants_line}

[Service]
Type=${type}
ExecStart=${exec_start}
${exec_stop_line}
${exec_reload_line}
${working_directory_line}
${user_line}
${group_line}
Restart=${restart}
RestartSec=${restart_sec}
${environment_lines}
${environment_file_line}

# Security hardening
${security_options}

[Install]
WantedBy=${wanted_by}
""")


# Timer template
SYSTEMD_TIMER_TEMPLATE = Template("""[Unit]
Description=${description}

[Timer]
${on_calendar_line}
${on_boot_sec_line}
${on_unit_active_sec_line}
${on_unit_inactive_sec_line}
${accuracy_sec_line}
${randomized_delay_sec_line}
Persistent=${persistent}
Unit=${unit}

[Install]
WantedBy=timers.target
""")


# Socket activation template
SYSTEMD_SOCKET_TEMPLATE = Template("""[Unit]
Description=${description}

[Socket]
ListenStream=${listen_stream}
${listen_datagram_line}
${socket_user_line}
${socket_group_line}
${socket_mode_line}
Accept=${accept}

[Install]
WantedBy=sockets.target
""")


# Path watch template
SYSTEMD_PATH_TEMPLATE = Template("""[Unit]
Description=${description}

[Path]
${path_exists_line}
${path_exists_glob_line}
${path_changed_line}
${path_modified_line}
${directory_not_empty_line}
Unit=${unit}
MakeDirectory=${make_directory}
DirectoryMode=${directory_mode}

[Install]
WantedBy=multi-user.target
""")


def _build_line(prefix: str, value: str | None) -> str:
    """Build an optional line for a template."""
    if value:
        return f"{prefix}={value}"
    return ""


def _build_lines(prefix: str, values: list[str] | None) -> str:
    """Build multiple optional lines."""
    if not values:
        return ""
    return "\n".join(f"{prefix}={v}" for v in values)


def _build_environment_lines(env: dict | None) -> str:
    """Build environment variable lines."""
    if not env:
        return ""
    return "\n".join(f'Environment="{k}={v}"' for k, v in env.items())


def _build_security_options(hardening_level: str = "default") -> str:
    """Build security hardening options based on level."""
    if hardening_level == "none":
        return ""

    options = []

    if hardening_level in ("default", "strict"):
        options.extend([
            "NoNewPrivileges=true",
            "PrivateTmp=true",
            "ProtectSystem=strict",
            "ProtectHome=true",
        ])

    if hardening_level == "strict":
        options.extend([
            "ProtectKernelTunables=true",
            "ProtectKernelModules=true",
            "ProtectControlGroups=true",
            "RestrictRealtime=true",
            "RestrictSUIDSGID=true",
            "MemoryDenyWriteExecute=true",
            "LockPersonality=true",
        ])

    return "\n".join(options)


def render_systemd_template(
    template_name: str,
    **kwargs,
) -> str:
    """
    Render a systemd template with the given parameters.

    Args:
        template_name: Name of the template (service, timer, socket, path)
        **kwargs: Template variables

    Returns:
        Rendered template string

    Example:
        unit = render_systemd_template(
            "service",
            description="My Service",
            exec_start="/usr/bin/myapp",
            user="myuser",
        )
    """
    templates = {
        "service": SYSTEMD_SERVICE_TEMPLATE,
        "timer": SYSTEMD_TIMER_TEMPLATE,
        "socket": SYSTEMD_SOCKET_TEMPLATE,
        "path": SYSTEMD_PATH_TEMPLATE,
    }

    template = templates.get(template_name)
    if not template:
        raise ValueError(f"Unknown template: {template_name}")

    # Set defaults
    defaults = {
        "after": "network.target",
        "type": "simple",
        "restart": "on-failure",
        "restart_sec": "5",
        "wanted_by": "multi-user.target",
        "persistent": "false",
        "accept": "false",
        "make_directory": "false",
        "directory_mode": "0755",
    }

    for key, value in defaults.items():
        kwargs.setdefault(key, value)

    # Build optional lines for service template
    if template_name == "service":
        kwargs["wants_line"] = _build_line("Wants", kwargs.get("wants"))
        kwargs["exec_stop_line"] = _build_line("ExecStop", kwargs.get("exec_stop"))
        kwargs["exec_reload_line"] = _build_line("ExecReload", kwargs.get("exec_reload"))
        kwargs["working_directory_line"] = _build_line(
            "WorkingDirectory", kwargs.get("working_directory")
        )
        kwargs["user_line"] = _build_line("User", kwargs.get("user"))
        kwargs["group_line"] = _build_line("Group", kwargs.get("group"))
        kwargs["environment_lines"] = _build_environment_lines(kwargs.get("environment"))
        kwargs["environment_file_line"] = _build_line(
            "EnvironmentFile", kwargs.get("environment_file")
        )
        kwargs["security_options"] = _build_security_options(
            kwargs.get("hardening_level", "default")
        )

    # Build optional lines for timer template
    elif template_name == "timer":
        kwargs["on_calendar_line"] = _build_line("OnCalendar", kwargs.get("on_calendar"))
        kwargs["on_boot_sec_line"] = _build_line("OnBootSec", kwargs.get("on_boot_sec"))
        kwargs["on_unit_active_sec_line"] = _build_line(
            "OnUnitActiveSec", kwargs.get("on_unit_active_sec")
        )
        kwargs["on_unit_inactive_sec_line"] = _build_line(
            "OnUnitInactiveSec", kwargs.get("on_unit_inactive_sec")
        )
        kwargs["accuracy_sec_line"] = _build_line("AccuracySec", kwargs.get("accuracy_sec"))
        kwargs["randomized_delay_sec_line"] = _build_line(
            "RandomizedDelaySec", kwargs.get("randomized_delay_sec")
        )

    # Build optional lines for socket template
    elif template_name == "socket":
        kwargs["listen_datagram_line"] = _build_line(
            "ListenDatagram", kwargs.get("listen_datagram")
        )
        kwargs["socket_user_line"] = _build_line("SocketUser", kwargs.get("socket_user"))
        kwargs["socket_group_line"] = _build_line("SocketGroup", kwargs.get("socket_group"))
        kwargs["socket_mode_line"] = _build_line("SocketMode", kwargs.get("socket_mode"))

    # Build optional lines for path template
    elif template_name == "path":
        kwargs["path_exists_line"] = _build_line("PathExists", kwargs.get("path_exists"))
        kwargs["path_exists_glob_line"] = _build_line(
            "PathExistsGlob", kwargs.get("path_exists_glob")
        )
        kwargs["path_changed_line"] = _build_line("PathChanged", kwargs.get("path_changed"))
        kwargs["path_modified_line"] = _build_line("PathModified", kwargs.get("path_modified"))
        kwargs["directory_not_empty_line"] = _build_line(
            "DirectoryNotEmpty", kwargs.get("directory_not_empty")
        )

    rendered = template.safe_substitute(**kwargs)

    # Clean up empty lines from optional fields
    lines = rendered.splitlines()
    cleaned_lines = []
    prev_empty = False

    for line in lines:
        is_empty = not line.strip()
        # Skip consecutive empty lines
        if is_empty and prev_empty:
            continue
        cleaned_lines.append(line)
        prev_empty = is_empty

    return "\n".join(cleaned_lines)
