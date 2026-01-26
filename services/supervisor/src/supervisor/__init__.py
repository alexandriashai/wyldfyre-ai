"""
Supervisor Agent - Task routing and orchestration.

The Supervisor is the central coordinator for all AI Infrastructure tasks:
- Receives all incoming task requests
- Analyzes and routes tasks to appropriate agents
- Handles multi-agent orchestration
- Manages escalation and fallback

Includes learning improvements:
- Outcome Feedback Loop (Improvement 1)
- Process Reward Model with step scoring (Improvement 2)
- Experience Replay and Consolidation (Improvement 4)
- Plan Quality Prediction (Improvement 6)
"""

from .agent import SupervisorAgent
from .consolidation import (
    LearningConsolidator,
    run_immediate_consolidation,
    schedule_consolidation,
)
from .router import RoutingDecision, TaskRouter

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "SupervisorAgent",
    "TaskRouter",
    "RoutingDecision",
    # Consolidation (Improvement 4)
    "LearningConsolidator",
    "schedule_consolidation",
    "run_immediate_consolidation",
]
