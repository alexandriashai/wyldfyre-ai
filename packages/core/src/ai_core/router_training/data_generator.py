"""
Training data generator for MFRouter - Wyld Fyre AI.

Generates labeled training examples based on actual request patterns:
- FAST: Status checks, simple questions, quick lookups, basic commands
- BALANCED: Code writing, debugging, explanations, moderate analysis
- POWERFUL: Architecture design, complex refactoring, multi-step planning
"""

import json
import random
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TrainingSample:
    """A single training sample for MFRouter."""

    query: str
    model_name: str  # "fast", "balanced", "powerful"
    performance: float  # Simulated performance score (0.0-1.0)
    embedding_id: int  # Index for embedding lookup


# =============================================================================
# FAST TIER - Simple tasks that Haiku handles well
# Status checks, simple questions, basic commands, yes/no answers
# =============================================================================

FAST_TEMPLATES = [
    # Status checks
    "What's the status of {agent}?",
    "Is {service} running?",
    "Show me the current {resource} status",
    "Check if {component} is healthy",
    "What agents are available?",
    "List active tasks",
    "Show system status",
    "What's the current branch?",
    "Is the build passing?",
    "Are there any errors in the logs?",

    # Git simple commands
    "Show git status",
    "What branch am I on?",
    "List recent commits",
    "Show the last commit message",
    "Are there uncommitted changes?",
    "List all branches",
    "Show git diff",
    "What files changed?",
    "Is there anything to push?",
    "Show stash list",

    # Simple file operations
    "Does {file} exist?",
    "What's in the {directory} folder?",
    "List files in {path}",
    "Show me {filename}",
    "Read {config_file}",
    "What's the file size of {file}?",
    "When was {file} last modified?",
    "Is {file} writable?",

    # Quick lookups
    "What does {acronym} stand for?",
    "What is {term}?",
    "Define {concept}",
    "What's the port for {service}?",
    "What's the default value of {setting}?",
    "Where is {config} stored?",
    "What's the syntax for {command}?",
    "What version of {package} is installed?",

    # Yes/no questions
    "Can I use {feature} in {version}?",
    "Is {option} enabled?",
    "Does {component} support {capability}?",
    "Should I commit these changes?",
    "Is this a breaking change?",
    "Are the tests passing?",
    "Is the database connected?",
    "Is Redis available?",

    # Simple calculations/conversions
    "Convert {value} {from_unit} to {to_unit}",
    "What's {num1} + {num2}?",
    "Calculate {percent}% of {number}",
    "How many {unit} in {larger_unit}?",

    # Help commands
    "/help",
    "/status",
    "/tools",
    "What commands are available?",
    "Show me the help menu",
    "List available tools",

    # Quick confirmations
    "Confirm deployment to {environment}",
    "Yes, proceed",
    "No, cancel that",
    "Thanks, that's all",
    "Got it",
    "Okay",
    "Perfect, thanks",
]

# =============================================================================
# BALANCED TIER - Moderate complexity tasks that Sonnet handles well
# Code writing, debugging, explanations, API work, moderate analysis
# =============================================================================

BALANCED_TEMPLATES = [
    # Code writing
    "Write a function to {task}",
    "Create a Python function that {description}",
    "Implement {feature} in {language}",
    "Write a {data_structure} class",
    "Create a utility function for {purpose}",
    "Write tests for {component}",
    "Implement error handling for {function}",
    "Add validation to {endpoint}",
    "Create a helper function to {task}",
    "Write a migration script to {task}",

    # Debugging
    "Fix this error: {error_message}",
    "Why is {component} throwing {error}?",
    "Debug this issue: {description}",
    "Help me fix this bug in {file}",
    "This test is failing: {test_name}",
    "Find the bug in this code: {code_snippet}",
    "Why is {variable} undefined?",
    "The {endpoint} returns 500, help me debug",
    "TypeError in {function}, what's wrong?",

    # Git operations
    "Commit these changes with a good message",
    "Create a PR for this feature",
    "Merge {branch} into {target_branch}",
    "Resolve the merge conflict in {file}",
    "Cherry-pick commit {hash} to {branch}",
    "Rebase my branch on main",
    "Squash the last {n} commits",
    "Create a branch for {feature}",

    # Explanations
    "Explain how {component} works",
    "What does this code do: {code}",
    "Explain the difference between {a} and {b}",
    "How does {feature} handle {scenario}?",
    "Walk me through the {process}",
    "Why do we use {pattern} here?",
    "What's the purpose of {module}?",
    "Explain this error: {error}",

    # API and database
    "Create an endpoint for {resource}",
    "Write a SQL query to {task}",
    "Add a new field to the {model} model",
    "Implement pagination for {endpoint}",
    "Add authentication to {route}",
    "Create a database migration for {change}",
    "Query {table} where {condition}",
    "Join {table1} with {table2} on {field}",

    # Configuration
    "Add {setting} to the config",
    "Update the {config} file to {change}",
    "Configure {service} for {environment}",
    "Set up environment variables for {feature}",
    "Add a new route for {path}",

    # Refactoring (moderate)
    "Rename {old_name} to {new_name}",
    "Extract this into a separate function",
    "Move {component} to {location}",
    "Split this file into smaller modules",
    "Add type hints to {function}",
    "Convert this callback to async/await",

    # Documentation
    "Add docstrings to {module}",
    "Document the {api} endpoint",
    "Write a README for {project}",
    "Add comments explaining {complex_section}",

    # Testing
    "Write unit tests for {function}",
    "Add integration tests for {endpoint}",
    "Create a test fixture for {model}",
    "Mock {dependency} in the tests",
    "Fix the flaky test in {test_file}",

    # Infrastructure (moderate)
    "Deploy to {environment}",
    "Restart the {service} service",
    "Check the logs for {container}",
    "Scale {service} to {n} instances",
    "Update the Docker image for {service}",
    "Add a health check to {container}",

    # Memory and learning
    "/remember {fact}",
    "What do you remember about {topic}?",
    "Search memory for {query}",
    "Save this as a pattern: {pattern}",

    # Plan operations
    "/plan list",
    "/plan view {plan_id}",
    "Show me the current plan",
    "What's the next step in the plan?",
    "Update the plan to include {step}",
    "Mark step {n} as complete",
]

# =============================================================================
# POWERFUL TIER - Complex tasks requiring Opus
# Architecture design, complex refactoring, multi-step analysis, system design
# =============================================================================

POWERFUL_TEMPLATES = [
    # Architecture design
    "Design the architecture for {system}",
    "How should I structure {complex_feature}?",
    "Design a scalable solution for {problem}",
    "What's the best architecture for {use_case}?",
    "Design a microservices architecture for {application}",
    "How should I handle {complex_requirement} at scale?",
    "Design the data flow for {pipeline}",
    "Create an architecture diagram for {system}",
    "Design a distributed {component} that handles {constraint}",
    "What's the best way to architect {feature} with {requirements}?",

    # Complex refactoring
    "Refactor {module} to be more maintainable",
    "Modernize the {legacy_component}",
    "Convert the monolith to microservices",
    "Redesign the {system} for better performance",
    "Refactor {codebase} to use {pattern}",
    "Migrate from {old_tech} to {new_tech}",
    "Restructure the entire {module} module",
    "Optimize the {critical_path} for performance",
    "Refactor with backward compatibility for {api}",

    # Multi-step planning
    "Create a plan to implement {feature}",
    "How should I approach {complex_task}?",
    "Break down the implementation of {system}",
    "Plan the migration from {source} to {target}",
    "Create a roadmap for {project}",
    "What's the step-by-step plan for {goal}?",
    "Design an implementation strategy for {feature}",
    "Plan the rollout of {change} with zero downtime",

    # Complex analysis
    "Analyze the tradeoffs between {option_a} and {option_b}",
    "Review this architecture for potential issues: {description}",
    "What are the security implications of {approach}?",
    "Evaluate the performance of {system}",
    "Identify bottlenecks in {pipeline}",
    "Analyze the cost implications of {decision}",
    "What could go wrong with {approach}?",
    "Review the design and identify improvements",

    # System design
    "Design a {type} system that handles {scale} requests",
    "How would you build {complex_system}?",
    "Design the backend for {application}",
    "Create a schema for {complex_domain}",
    "Design an event-driven architecture for {use_case}",
    "How should I implement {feature} with high availability?",
    "Design a caching strategy for {workload}",
    "Create a monitoring strategy for {distributed_system}",

    # Complex debugging/investigation
    "The system is slow, analyze and fix it",
    "Investigate why {service} keeps crashing",
    "Debug the intermittent failure in {component}",
    "Find the root cause of {complex_issue}",
    "Why is memory usage growing in {service}?",
    "Diagnose the performance regression in {module}",

    # Code review (complex)
    "Review this PR for architectural issues",
    "Audit the security of {codebase}",
    "Review the API design for {service}",
    "Evaluate the test coverage for {module}",
    "Review the database schema for scalability",

    # Strategy and decisions
    "Should we use {tech_a} or {tech_b} for {use_case}?",
    "What's the best approach for {ambiguous_requirement}?",
    "How do we balance {tradeoff_a} vs {tradeoff_b}?",
    "Design a versioning strategy for {api}",
    "What's the best testing strategy for {system}?",

    # Infrastructure (complex)
    "Set up a complete CI/CD pipeline for {project}",
    "Design the Kubernetes deployment for {application}",
    "Implement blue-green deployment for {service}",
    "Set up observability for the entire stack",
    "Design disaster recovery for {critical_system}",
    "Implement auto-scaling for {workload}",

    # Creative problem solving
    "How can I achieve {goal} given {constraints}?",
    "Find a creative solution for {unusual_problem}",
    "We need to {goal} but {limitation}, what are our options?",
    "Design a solution that balances {competing_needs}",
]

# =============================================================================
# Placeholder values for template filling
# =============================================================================

PLACEHOLDER_VALUES = {
    # Agents and services
    "agent": ["code-agent", "data-agent", "infra-agent", "research-agent", "qa-agent", "wyld"],
    "service": ["api", "supervisor", "redis", "postgres", "nginx", "docker", "the web server", "the database"],
    "component": ["memory system", "router", "task queue", "websocket handler", "auth service", "cache layer"],
    "resource": ["agents", "tasks", "memory", "connections", "containers", "processes"],

    # Files and paths
    "file": ["config.yaml", "main.py", ".env", "package.json", "docker-compose.yml", "requirements.txt"],
    "filename": ["app.py", "index.ts", "schema.sql", "Dockerfile", "nginx.conf"],
    "directory": ["src", "config", "tests", "scripts", "docs"],
    "path": ["/app/src", "/home/wyld-core/config", "./services", "./packages"],
    "config_file": ["agents.yaml", "settings.py", ".env.local", "prometheus.yml"],

    # Code concepts
    "term": ["API", "middleware", "ORM", "decorator", "context manager", "generator"],
    "acronym": ["REST", "gRPC", "JWT", "OAuth", "CORS", "CSRF", "XSS"],
    "concept": ["dependency injection", "event sourcing", "CQRS", "saga pattern", "circuit breaker"],
    "pattern": ["factory", "singleton", "observer", "strategy", "adapter", "decorator"],

    # Git and version control
    "branch": ["main", "develop", "feature/auth", "fix/memory-leak", "release/v2.0"],
    "target_branch": ["main", "develop", "staging"],
    "hash": ["abc123", "def456", "HEAD~1", "origin/main"],
    "n": ["2", "3", "5", "10"],

    # Technical terms
    "feature": ["authentication", "caching", "rate limiting", "logging", "monitoring", "pagination"],
    "capability": ["async", "streaming", "batching", "retry", "timeout"],
    "setting": ["timeout", "max_retries", "batch_size", "cache_ttl", "log_level"],
    "version": ["Python 3.12", "Node 20", "PostgreSQL 16", "Redis 7"],
    "package": ["numpy", "pandas", "fastapi", "sqlalchemy", "pydantic"],

    # Languages and tech
    "language": ["Python", "TypeScript", "Go", "Rust", "SQL"],
    "data_structure": ["queue", "stack", "linked list", "hash map", "tree"],

    # Tasks and descriptions
    "task": ["parse JSON", "validate input", "retry failed requests", "cache results", "format dates"],
    "description": ["handles user authentication", "processes webhooks", "validates schemas", "manages sessions"],
    "purpose": ["error handling", "logging", "caching", "validation", "formatting"],

    # Errors
    "error": ["NullPointerException", "TypeError", "ConnectionError", "TimeoutError", "ValidationError"],
    "error_message": ["Cannot read property of undefined", "Connection refused", "Invalid JSON", "Timeout exceeded"],
    "test_name": ["test_user_login", "test_api_response", "test_database_connection"],

    # Database
    "table": ["users", "orders", "sessions", "logs", "tasks"],
    "table1": ["users", "orders"],
    "table2": ["orders", "products"],
    "field": ["user_id", "created_at", "status", "email"],
    "model": ["User", "Order", "Task", "Session", "Memory"],
    "condition": ["status = 'active'", "created_at > now() - interval '1 day'"],
    "change": ["add index on user_id", "add status column", "rename email to email_address"],

    # API and endpoints
    "endpoint": ["/api/users", "/api/tasks", "/api/memories", "/api/agents"],
    "resource": ["users", "tasks", "memories", "sessions", "agents"],
    "route": ["/login", "/webhook", "/api/v2", "/health"],
    "api": ["REST API", "GraphQL", "WebSocket API", "gRPC service"],

    # Infrastructure
    "environment": ["production", "staging", "development", "testing"],
    "container": ["api", "worker", "redis", "postgres", "nginx"],

    # Complex terms
    "system": ["task orchestration system", "memory management system", "agent coordination system"],
    "complex_feature": ["real-time collaboration", "distributed caching", "event-driven workflows"],
    "problem": ["handling 10k concurrent users", "processing large file uploads", "real-time notifications"],
    "use_case": ["e-commerce checkout", "real-time chat", "data pipeline", "ML inference"],
    "application": ["web dashboard", "API gateway", "background workers"],
    "complex_requirement": ["exactly-once delivery", "strong consistency", "sub-100ms latency"],
    "pipeline": ["data ingestion pipeline", "ML training pipeline", "CI/CD pipeline"],
    "constraint": ["high availability", "low latency", "cost efficiency"],
    "requirements": ["horizontal scaling", "zero downtime deployment", "audit logging"],

    # Refactoring terms
    "module": ["auth", "api", "core", "utils", "services"],
    "legacy_component": ["old API", "monolithic service", "legacy database layer"],
    "old_tech": ["callbacks", "REST", "SQL", "monolith"],
    "new_tech": ["async/await", "GraphQL", "NoSQL", "microservices"],
    "codebase": ["backend", "frontend", "shared libraries"],
    "critical_path": ["request handling", "database queries", "authentication flow"],

    # Analysis terms
    "option_a": ["SQL", "REST", "monolith", "sync processing"],
    "option_b": ["NoSQL", "GraphQL", "microservices", "async processing"],
    "approach": ["caching strategy", "database sharding", "event sourcing"],
    "decision": ["using JWT tokens", "microservices architecture", "PostgreSQL over MySQL"],

    # Scale and numbers
    "scale": ["1000", "10000", "100000", "1 million"],
    "type": ["event-driven", "request-response", "batch processing"],

    # Planning
    "goal": ["improve performance", "reduce costs", "increase reliability"],
    "source": ["v1 API", "legacy system", "on-premise"],
    "target": ["v2 API", "cloud", "Kubernetes"],
    "project": ["authentication rewrite", "API v2", "infrastructure migration"],

    # Tradeoffs
    "tradeoff_a": ["consistency", "latency", "cost"],
    "tradeoff_b": ["availability", "throughput", "complexity"],
    "competing_needs": ["speed and accuracy", "cost and quality", "flexibility and simplicity"],
    "limitation": ["limited budget", "tight deadline", "legacy constraints"],
    "unusual_problem": ["intermittent network failures", "memory leaks in production", "race conditions"],

    # Infrastructure complex
    "workload": ["API traffic", "batch jobs", "ML inference"],
    "critical_system": ["payment processing", "user authentication", "data storage"],
    "distributed_system": ["microservices cluster", "Kubernetes deployment", "multi-region setup"],

    # Misc
    "old_name": ["processData", "handleRequest", "doSomething"],
    "new_name": ["processUserData", "handleApiRequest", "executeTask"],
    "location": ["utils/", "shared/", "lib/"],
    "complex_section": ["the routing logic", "the caching layer", "the auth flow"],
    "function": ["process_request", "handle_webhook", "validate_input"],
    "variable": ["user", "response", "config"],
    "dependency": ["database", "redis", "external API"],
    "test_file": ["test_api.py", "test_auth.py", "test_integration.py"],

    # Memory and plans
    "fact": ["the API uses JWT tokens", "deploy on Fridays is disabled", "max file size is 10MB"],
    "topic": ["authentication", "deployment process", "database schema"],
    "query": ["recent deployments", "authentication issues", "performance optimizations"],
    "plan_id": ["plan-123", "plan-456"],
    "step": ["add error handling", "write tests", "update documentation"],

    # Values
    "value": ["100", "1024", "3.14"],
    "from_unit": ["MB", "seconds", "Celsius"],
    "to_unit": ["GB", "minutes", "Fahrenheit"],
    "num1": ["5", "42", "100"],
    "num2": ["3", "8", "25"],
    "percent": ["10", "25", "50"],
    "number": ["100", "1000", "500"],
    "unit": ["bytes", "seconds", "requests"],
    "larger_unit": ["kilobytes", "minutes", "batch"],

    # Code snippets (keep short for templates)
    "code": ["async function fetch() {}", "def process(x): return x * 2", "const data = await api.get()"],
    "code_snippet": ["if (user) { return user.name }", "for item in items: process(item)"],

    # Ambiguous
    "ambiguous_requirement": ["make it faster", "improve the UX", "make it more reliable"],
    "tech_a": ["PostgreSQL", "REST API", "Docker Compose"],
    "tech_b": ["MongoDB", "GraphQL", "Kubernetes"],
}


def fill_template(template: str) -> str:
    """Fill a template with random placeholder values."""
    result = template
    import re
    placeholders = re.findall(r"\{(\w+)\}", template)

    for placeholder in placeholders:
        if placeholder in PLACEHOLDER_VALUES:
            value = random.choice(PLACEHOLDER_VALUES[placeholder])
            result = result.replace(f"{{{placeholder}}}", value, 1)

    return result


def generate_sample(tier: str, embedding_id: int) -> TrainingSample:
    """Generate a single training sample for the given tier."""
    templates = {
        "fast": FAST_TEMPLATES,
        "balanced": BALANCED_TEMPLATES,
        "powerful": POWERFUL_TEMPLATES,
    }

    template = random.choice(templates[tier])
    query = fill_template(template)

    # Simulate performance scores - the correct tier should have highest performance
    if tier == "fast":
        performance = random.uniform(0.88, 0.98)
    elif tier == "balanced":
        performance = random.uniform(0.85, 0.95)
    else:  # powerful
        performance = random.uniform(0.82, 0.92)

    return TrainingSample(
        query=query,
        model_name=tier,
        performance=performance,
        embedding_id=embedding_id,
    )


def generate_training_data(
    num_samples: int = 10000,
    tier_distribution: dict[str, float] | None = None,
    output_path: str | Path | None = None,
    seed: int | None = None,
) -> list[dict]:
    """
    Generate synthetic training data for MFRouter.

    The training data format matches LLMRouter's expected format:
    - query: The input text
    - model_name: Target tier ("fast", "balanced", "powerful")
    - performance: Performance score (0.0-1.0)
    - embedding_id: Index for precomputed embeddings

    Args:
        num_samples: Total number of samples to generate
        tier_distribution: Distribution of samples across tiers
            Default: {"fast": 0.35, "balanced": 0.40, "powerful": 0.25}
        output_path: Path to write JSONL output (optional)
        seed: Random seed for reproducibility

    Returns:
        List of training sample dictionaries
    """
    if seed is not None:
        random.seed(seed)

    # Realistic distribution: most requests are moderate complexity
    if tier_distribution is None:
        tier_distribution = {
            "fast": 0.35,      # Simple status checks, quick questions
            "balanced": 0.40,  # Most coding tasks
            "powerful": 0.25,  # Architecture, complex refactoring
        }

    samples = []
    embedding_id = 0

    for tier, ratio in tier_distribution.items():
        tier_count = int(num_samples * ratio)
        for _ in range(tier_count):
            sample = generate_sample(tier, embedding_id)
            samples.append({
                "query": sample.query,
                "model_name": sample.model_name,
                "performance": round(sample.performance, 4),
                "embedding_id": sample.embedding_id,
            })
            embedding_id += 1

    # Shuffle samples
    random.shuffle(samples)

    # Write to file if path provided
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            for sample in samples:
                f.write(json.dumps(sample) + "\n")
        print(f"Wrote {len(samples)} samples to {output_path}")

    return samples


def generate_pairwise_data(
    num_queries: int = 5000,
    output_path: str | Path | None = None,
    seed: int | None = None,
) -> list[dict]:
    """
    Generate pairwise training data where each query has performance
    scores for all three tiers.

    This format is better for MFRouter as it learns relative preferences.

    Args:
        num_queries: Number of unique queries to generate
        output_path: Path to write JSONL output
        seed: Random seed for reproducibility

    Returns:
        List of training samples (3 per query, one for each tier)
    """
    if seed is not None:
        random.seed(seed)

    samples = []
    embedding_id = 0

    # Generate queries with a ground-truth best tier
    tier_distribution = {
        "fast": 0.35,
        "balanced": 0.40,
        "powerful": 0.25,
    }

    templates = {
        "fast": FAST_TEMPLATES,
        "balanced": BALANCED_TEMPLATES,
        "powerful": POWERFUL_TEMPLATES,
    }

    for best_tier, ratio in tier_distribution.items():
        tier_count = int(num_queries * ratio)

        for _ in range(tier_count):
            template = random.choice(templates[best_tier])
            query = fill_template(template)

            # Generate performance for all tiers
            # The "best" tier should have highest performance
            for tier in ["fast", "balanced", "powerful"]:
                if tier == best_tier:
                    # Best tier gets high performance
                    perf = random.uniform(0.85, 0.98)
                elif tier == "balanced":
                    # Balanced is a reasonable fallback
                    perf = random.uniform(0.70, 0.85)
                else:
                    # Wrong tier gets lower performance
                    perf = random.uniform(0.50, 0.75)

                samples.append({
                    "query": query,
                    "model_name": tier,
                    "performance": round(perf, 4),
                    "embedding_id": embedding_id,
                })

            embedding_id += 1

    # Write to file if path provided
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            for sample in samples:
                f.write(json.dumps(sample) + "\n")
        print(f"Wrote {len(samples)} samples to {output_path}")

    return samples


if __name__ == "__main__":
    # Generate sample data for testing
    print("Generating sample training data...")
    samples = generate_training_data(num_samples=30, seed=42)

    print("\nSample queries by tier:")
    for tier in ["fast", "balanced", "powerful"]:
        print(f"\n{tier.upper()}:")
        tier_samples = [s for s in samples if s["model_name"] == tier][:3]
        for s in tier_samples:
            print(f"  - {s['query'][:70]}...")
