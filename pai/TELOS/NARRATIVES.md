# NARRATIVES.md
## System-Level TELOS for Wyld Fyre Organization

### Origin Story
The catalyst was the coordination tax of modern development—spending more time managing tool friction than doing actual work. Building complex AI systems, privacy-focused platforms, and infrastructure automation while constantly re-explaining context between ChatGPT, Cursor, and other disconnected tools. The breakthrough came from discovering Daniel Miessler's PAI framework, which articulated the vision of AI that learns, remembers, and grows with you—but as philosophy, not implementation.

The driving need: sovereignty over sensitive data (escort.reviews encryption, homelab infrastructure) and bridging the gap between vision and execution. Wyld Fyre exists because this tool needed to exist, not from a desire to build an AI company.

### Core Mission
Build AI infrastructure that operates at the level of vision, not syntax. Enable AI that becomes a partner through learning and memory, while maintaining complete sovereignty over data and context.

### Technical Foundation

**Multi-Agent AI Architecture**
- Specialized agent coordination patterns: task decomposition, routing, handoffs, shared memory, conflict resolution
- Focus on collaboration that produces better outcomes than single-agent approaches

**Memory and Learning Systems**  
- Vector databases (Qdrant), semantic search, embedding strategies
- Three-tier architecture (hot/warm/cold)
- Outcome-based learning: capture signals, assess results, feed improvements back
- RAG implementation done right

**Self-Hosted Infrastructure**
- Proxmox virtualization, OPNsense networking, Docker orchestration, TrueNAS storage
- Production-grade homelab operations, not hobby-level reliability

**Privacy-First Development**
- End-to-end encryption, client-side key derivation, zero-knowledge architecture
- FOSTA-SESTA compliance, high-risk payment processing, threat modeling
- Building systems where operators cannot access user data

**Technology Stack**
- Backend: Python, FastAPI, SQLAlchemy async, Pydantic
- Frontend: Next.js, React, Tailwind
- Infrastructure: Prometheus, Grafana, Loki, CI/CD, infrastructure as code

### Core Principles

**PAI Framework Implementation**
- TELOS files, 7-phase learning loop, hook systems, user/system separation
- Conceptual foundation from Daniel Miessler's Personal AI Infrastructure philosophy

**Sovereignty by Default**
- Every architectural decision starts with "can this run entirely on user-controlled infrastructure?"
- Cloud is opt-in, not assumed

**Progressive Disclosure of Complexity**
- Simple by default, powerful when needed
- Users shouldn't need to understand the full system to get value

**Outcome-Based Learning**
- Not just remembering what happened—evaluating whether it worked and adjusting
- The feedback loop that turns a tool into a partner

### Primary User: The Builder
- Background: Web content manager at CU Denver by day, self-taught infrastructure and development expert
- Drives: Sovereignty, control, privacy, system-level thinking over task execution
- Working patterns: Context-switching between diverse projects while maintaining state
- Decision-making: Wants to understand the *why*, then execute without re-confirmation

### Target Audience

**Primary: Builders with More Vision Than Time**
- Solo founders, indie hackers, developers bottlenecked by implementation
- Non-traditional builders with domain expertise but limited CS backgrounds
- People who can describe what they want but are time-constrained on execution

**Secondary: Privacy-Conscious Self-Hosters**
- Won't use cloud AI due to data sovereignty concerns
- Need infrastructure they own and control

**Tertiary: Developers Wanting AI That Actually Learns**
- Frustrated with tools that forget between sessions
- Want compound learning effect—AI that improves at helping them specifically

### Ecosystem Context

**Influences**
- Daniel Miessler and PAI community (philosophical foundation)
- Self-hosted/homelab community (sovereignty values)
- Open-source AI movement (Ollama, local models, ownership focus)
- Indie hacker and solo founder communities (implementation bottleneck understanding)

**Competitive Landscape**
- Current tools: Claude, GPT, Cursor, Windsurf (powerful but disconnected)
- Gap: None offer persistent learning with sovereignty
- Open-source movement: Local models viable but still catching up in capability

### Communication Preferences
- **Style**: Direct and efficient, no unnecessary padding or caveats
- **Information**: Lead with essential point, structured hierarchy, actionable details
- **Feedback**: Honest even when critical, focus on solutions not just problems
- **Decision Support**: Clear reasoning and tradeoffs, strong recommendations over "it depends"

### What Energizes vs. Drains
**Energizes**: Elegant systems, compound effects of good architecture, shipping solutions that actually help
**Drains**: Re-explaining provided context, tool friction, tedious non-judgmental implementation work, repetition

### Success Metrics
- Reduction in context re-explanation across tools
- Increased time spent on vision vs. implementation
- AI assistants that improve understanding over time
- Maintained sovereignty over sensitive data and learned context

---
*Last updated: 2026-01-27 21:57:32 UTC*
