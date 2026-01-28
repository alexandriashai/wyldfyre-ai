"""
Router Training Package for MFRouter.

Provides utilities for training content-based routing models:
- Synthetic data generation
- Model training and evaluation
- Cost analytics
"""

from .data_generator import (
    TrainingSample,
    generate_sample,
    generate_training_data,
    generate_pairwise_data,
)
from .trainer import (
    RouterTrainer,
    TrainingConfig,
)
from .cost_analytics import (
    CostAnalytics,
    CostAnalyticsTracker,
    RoutingDecision,
    calculate_routing_savings,
    estimate_monthly_savings,
    get_cost_analytics_tracker,
)

__all__ = [
    # Data Generator
    "TrainingSample",
    "generate_sample",
    "generate_training_data",
    "generate_pairwise_data",
    # Trainer
    "RouterTrainer",
    "TrainingConfig",
    # Cost Analytics
    "CostAnalytics",
    "CostAnalyticsTracker",
    "RoutingDecision",
    "calculate_routing_savings",
    "estimate_monthly_savings",
    "get_cost_analytics_tracker",
]
