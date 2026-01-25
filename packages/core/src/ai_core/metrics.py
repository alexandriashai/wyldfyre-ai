"""
Prometheus metrics for AI Infrastructure.

Provides pre-defined metrics for monitoring:
- HTTP request metrics
- Agent task metrics
- Database connection metrics
- External API call metrics
- Memory system metrics
"""

from prometheus_client import Counter, Gauge, Histogram, Info

# =============================================================================
# Application Info
# =============================================================================

app_info = Info(
    "ai_infrastructure",
    "AI Infrastructure application information",
)

# =============================================================================
# HTTP Request Metrics
# =============================================================================

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

http_requests_in_progress = Gauge(
    "http_requests_in_progress",
    "Number of HTTP requests currently in progress",
    ["method", "endpoint"],
)

# =============================================================================
# Agent Metrics
# =============================================================================

agent_tasks_total = Counter(
    "agent_tasks_total",
    "Total agent tasks processed",
    ["agent_type", "task_type", "status"],
)

agent_task_duration_seconds = Histogram(
    "agent_task_duration_seconds",
    "Agent task duration in seconds",
    ["agent_type", "task_type"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0),
)

agent_active_tasks = Gauge(
    "agent_active_tasks",
    "Number of active tasks per agent",
    ["agent_type"],
)

agent_errors_total = Counter(
    "agent_errors_total",
    "Total agent errors",
    ["agent_type", "error_type"],
)

agent_tool_calls_total = Counter(
    "agent_tool_calls_total",
    "Total tool calls made by agents",
    ["agent_type", "tool_name", "status"],
)

# =============================================================================
# Database Metrics
# =============================================================================

db_connections_active = Gauge(
    "db_connections_active",
    "Number of active database connections",
    ["database"],
)

db_connections_idle = Gauge(
    "db_connections_idle",
    "Number of idle database connections",
    ["database"],
)

db_query_duration_seconds = Histogram(
    "db_query_duration_seconds",
    "Database query duration in seconds",
    ["database", "operation"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

db_errors_total = Counter(
    "db_errors_total",
    "Total database errors",
    ["database", "error_type"],
)

# =============================================================================
# External API Metrics
# =============================================================================

external_api_requests_total = Counter(
    "external_api_requests_total",
    "Total external API requests",
    ["service", "endpoint", "status_code"],
)

external_api_duration_seconds = Histogram(
    "external_api_duration_seconds",
    "External API request duration in seconds",
    ["service", "endpoint"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)

external_api_errors_total = Counter(
    "external_api_errors_total",
    "Total external API errors",
    ["service", "error_type"],
)

# Claude API specific
claude_api_tokens_total = Counter(
    "claude_api_tokens_total",
    "Total Claude API tokens used",
    ["agent_type", "token_type"],  # token_type: input, output
)

claude_api_cost_dollars = Counter(
    "claude_api_cost_dollars",
    "Estimated Claude API cost in dollars",
    ["agent_type", "model"],
)

# =============================================================================
# Memory System Metrics
# =============================================================================

memory_operations_total = Counter(
    "memory_operations_total",
    "Total memory system operations",
    ["tier", "operation", "status"],  # tier: hot, warm, cold
)

memory_operation_duration_seconds = Histogram(
    "memory_operation_duration_seconds",
    "Memory operation duration in seconds",
    ["tier", "operation"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5),
)

memory_items_count = Gauge(
    "memory_items_count",
    "Number of items in memory tier",
    ["tier"],
)

embedding_generation_duration_seconds = Histogram(
    "embedding_generation_duration_seconds",
    "Embedding generation duration in seconds",
    ["model"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

# =============================================================================
# Message Bus Metrics
# =============================================================================

messages_published_total = Counter(
    "messages_published_total",
    "Total messages published",
    ["channel"],
)

messages_consumed_total = Counter(
    "messages_consumed_total",
    "Total messages consumed",
    ["channel", "status"],
)

message_processing_duration_seconds = Histogram(
    "message_processing_duration_seconds",
    "Message processing duration in seconds",
    ["channel"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

message_queue_length = Gauge(
    "message_queue_length",
    "Number of messages in queue",
    ["channel"],
)

# =============================================================================
# PAI Algorithm Metrics
# =============================================================================

pai_phase_executions_total = Counter(
    "pai_phase_executions_total",
    "Total PAI algorithm phase executions",
    ["phase"],  # observe, think, plan, build, execute, verify, learn
)

pai_phase_duration_seconds = Histogram(
    "pai_phase_duration_seconds",
    "PAI phase execution duration in seconds",
    ["phase"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

pai_learnings_extracted_total = Counter(
    "pai_learnings_extracted_total",
    "Total learnings extracted by PAI",
    ["phase", "category"],
)

# =============================================================================
# Content Router Metrics
# =============================================================================

routing_decisions_total = Counter(
    "llm_routing_decisions_total",
    "Content router decisions",
    ["from_tier", "to_tier"],
)

routing_latency_seconds = Histogram(
    "llm_routing_latency_seconds",
    "Content router decision latency",
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25],
)

# =============================================================================
# System Metrics
# =============================================================================

system_uptime_seconds = Gauge(
    "system_uptime_seconds",
    "System uptime in seconds",
    ["service"],
)

agent_last_heartbeat_timestamp = Gauge(
    "agent_last_heartbeat_timestamp",
    "Unix timestamp of the last heartbeat from each agent",
    ["agent_name", "agent_type"],
)

# =============================================================================
# Security Metrics
# =============================================================================

security_violations_total = Counter(
    "security_violations_total",
    "Total security violations detected",
    ["threat_level", "rule_name", "agent"],
)
