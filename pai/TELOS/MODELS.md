# TELOS Mental Models Framework

## Decision-Making Framework

### Bias Toward Action with Smart Guardrails
- **Speed over perfection**: Ship working code that can be improved, rather than perfect plans that never launch
- **Foundation-first quality**: Get architecture and boundaries right, then move fast on implementation
- **Opportunity-focused risk**: Take big swings with protective measures (permission tiers, audit trails, kill switches)
- **Intuition + Data**: Intuition picks direction, data keeps you honest - trust gut to start, evidence to finish
- **Solo decision-making**: Commit to opinions quickly, learn from being wrong fast rather than waiting for consensus

### Core Decision Questions
1. "What's the simplest thing that could work?"
2. "Can I undo this?" (If yes, do it. If no, sleep on it)
3. "What will I wish I'd done in six months?" (Usually: started sooner)
4. "Am I building for a real problem or an imaginary one?" (Kill imaginary ones fast)

## Problem-Solving Approach

### Exploration-First Learning
- **Touch before research**: 5 minutes hands-on beats an hour reading outdated documentation
- **Building IS understanding**: Code surfaces the real questions you need to ask
- **Steal ideas, don't copy solutions**: Filter existing approaches through your specific context
- **Isolation debugging**: Find the smallest reproduction, add logging at boundaries until reality diverges from expectations

### Incremental Building Strategy
- **Tracer bullet approach**: Build one path through the entire system first, then fill in gaps
- **Natural seams**: Break work along genuine boundaries, not artificial phases
- **Every piece should run**: Deliver usable functionality at each increment
- **Map edges first**: Understand inputs, outputs, and connections before diving deep

## Quality Standards

### Two-Tier Quality System
**Quality Treatment (Non-negotiable):**
- Security: Permissions, validation, secrets handling
- Boundaries: Clean interfaces between components
- Data integrity: Correct handling of user data and system state

**Good Enough Treatment (Iterate quickly):**
- Internal implementation details
- UI aesthetics (if UX is clear)
- Documentation (if code is obvious)

### Definition of "Done"
- Works for happy path
- Fails gracefully for obvious sad paths
- Clean boundaries enable future internal changes
- Can demo without making excuses
- Observable failure modes (logs, errors, monitoring)

### Technical Debt Philosophy
- **Strategic accumulation**: Conscious debt in isolated modules is acceptable
- **Immediate payment**: Debt in shared code or boundaries gets fixed now
- **Honest documentation**: "This is dumb but works, fix when X becomes a problem"
- **Blast radius assessment**: Quality investment scales with potential impact

## Learning Philosophy

### Failure as Feedback
- **Curiosity over self-criticism**: "What did this teach me?" before "How do I fix it?"
- **Assumption surfacing**: Failures reveal hidden assumptions - that's the valuable learning
- **Scar tissue to wisdom**: Document painful lessons for future retrieval
- **Context-aware retrieval**: Embed learnings into decision moments, not just knowledge bases

### Experimentation Strategy
- **Proven core, experimental edges**: Use solved technologies for infrastructure, innovate where it matters
- **Compound learning**: Each cycle makes the next cycle smarter
- **Progress diagnosis**: "Am I stuck because this is hard (push through) or wrong (pivot)?"
- **Clean solution indicator**: Good approaches get cleaner as you develop them, wrong approaches breed complexity

### PAI Loop Integration
- **Observe**: What actually happened vs. what was expected?
- **Verify**: Test assumptions against evidence
- **Learn**: Extract transferable insights for future decisions
- **Context not rules**: Apply learnings as informed guidance, not rigid constraints

## Meta-Principles

### System Thinking
- Every component should improve the whole system's capability
- Build systems that make both human and AI better at building systems
- Boundaries are sacred, implementation is flexible
- Working code teaches you what perfect actually means

### Temporal Perspective
- Optimize for learning speed over initial perfection
- Build foundations that accelerate future development
- Make decisions that compound positively over time
- Design for iteration and improvement, not final states

---
*Last updated: 2026-01-27 22:11:23 UTC*
