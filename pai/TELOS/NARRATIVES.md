# Narratives & Context

> The story of why we built this system and important context for AI agents.

## Our Story

This PAI (Personal AI) infrastructure was built to solve a fundamental challenge:
how do we create AI systems that truly understand and adapt to individual and
organizational workflows without losing the human element?

We believe that the best AI systems are those that:
- Learn from their interactions
- Remember what works and what doesn't
- Respect boundaries and permissions
- Grow alongside the humans they work with

## System Context

### Architecture Overview
- **3-Tier Memory**: HOT (Redis) → WARM (Qdrant) → COLD (Files)
- **7-Phase Learning Loop**: OBSERVE → THINK → PLAN → BUILD → EXECUTE → VERIFY → LEARN
- **Multi-Agent Collaboration**: Specialized agents with permission hierarchies
- **TELOS Goal System**: Dynamic goal tracking with learning integration

### Key Components
- **PAI Memory**: Stores learnings, task traces, and patterns
- **Phase Memory Manager**: Retrieves context appropriate to each phase
- **Learning Extractor**: Automatically extracts learnings from task results
- **TELOS Manager**: Tracks goals, strategies, and organizational context

## Important Context

### When Making Decisions
- Check TELOS goals for alignment with current objectives
- Consult LEARNED.md for relevant past experiences
- Review STRATEGIES.md for proven patterns
- Consider CHALLENGES.md for known pitfalls

### When Learning
- Assign appropriate scope (GLOBAL, PROJECT, DOMAIN)
- Set realistic confidence levels
- Include metadata for future retrieval
- Avoid storing sensitive information

---
*Last updated: 2026-01-26 00:00:00 UTC*
