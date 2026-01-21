"""
Supervisor Agent - Task routing and orchestration.

The Supervisor is the central coordinator for all AI Infrastructure tasks:
- Receives all incoming task requests
- Analyzes and routes tasks to appropriate agents
- Handles multi-agent orchestration
- Manages escalation and fallback
"""

from .agent import SupervisorAgent
from .router import TaskRouter, RoutingDecision

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "SupervisorAgent",
    "TaskRouter",
    "RoutingDecision",
]
