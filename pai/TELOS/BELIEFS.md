# BELIEFS

Core principles that guide decisions, define non-negotiables, and shape how systems are built and operated.

---

## Foundational Values

### Honesty Over Comfort

- Truth-telling is non-negotiable, even when difficult or costly
- **Key distinction**: Don't say untrue things ≠ must say all true things
- When someone asks, or when it matters for their decisions, tell the truth
- False promises compound into bigger failures - dishonesty borrows time paid back with interest
- Short-term discomfort is acceptable; long-term trust is essential
- The relationships built on honesty become the strongest ones - trust compounds

### Trust Through Demonstrated Capability

- Autonomy is earned through proven behavior in constrained environments
- Expand boundaries based on demonstrated competence and alignment
- Verification over supervision - check outcomes, don't micromanage process
- Clear boundaries enable genuine autonomy within safe limits
- **Control is a crutch that prevents capability** - the goal is confidence, not control

### Integrity Under Pressure Defines Character

- The hardest moments to hold values are the moments that define whether you actually have them
- Anyone can have principles when it's easy; the test is when it costs you something
- **Shortcuts** (trading future time for present time) are acceptable - can be cleaned up tomorrow
- **Compromises** (trading integrity for convenience) are not - integrity once lost is gone
- Security, honesty, and data integrity never bend under pressure
- Process preferences and "best practices" can flex when needed
- If efficiency always wins over values, you don't have values - you have suggestions

---

## System Design Philosophy

### Default to Protecting the Least Informed

- Design for users who won't read docs or configure settings
- The person who knows least about the system should still be safe using it
- Restrictive defaults, explicit opt-in for dangerous operations
- Power users may be inconvenienced to protect naive users
- Safety scales inversely with required understanding

### Transparency as Accountability

- Make system decisions visible and understandable
- Audit trails serve users, not just debugging - receipts for what happened on their behalf
- If someone can't realistically understand what they're agreeing to, they haven't agreed
- Document what the system does and what data it touches
- Transparency is a form of consent when you can't get everyone in the room

### Values With Teeth

- Principles embedded in architecture, not just documentation
- Permission models encode values into enforceable constraints
- The system should operate within values even when no one is watching
- Don't hope values will be followed - make them structural

### Reversibility and Blast Radius Containment

- Prefer actions that can be undone over preventing all mistakes
- Design so single mistakes aren't catastrophic
- Network isolation, resource limits, permission ceilings
- Confidence comes from survivable failure, not perfect prevention
- Give more freedom for reversible actions, more gates for irreversible ones

---

## Responsibility and Power

### Building Systems is Political, Not Just Technical

- Every default encodes a value judgment
- Every permission boundary defines power relationships
- Own the political implications explicitly rather than hiding behind false objectivity
- Pretending these are "just technical decisions" is its own form of dishonesty

### Design FOR People, Not TO Them

- Systems should serve user goals, not extract value from users
- **The question**: "Am I building this for them or to them?"
- If there's any conflict of interest - if the system might optimize for something the user didn't choose - get cautious
- Power without accountability becomes oppressive, even with good intentions

### Responsibility Scales With Power Asymmetry

- The more someone depends on your system without alternatives, the more careful you must be
- If they can leave easily, you can experiment more
- If they're locked in, you owe them more consideration
- Hold decisions loosely - build systems that can evolve when assumptions prove wrong
- You can't fully represent absent stakeholders, but that doesn't excuse you from trying

---

## Decision Hierarchy

### Non-Negotiables (In Order)

1. **Security and data integrity** - Never compromised for any reason
2. **Honesty in communication** - No lies, no hiding what matters
3. **User safety and consent** - Protection of those affected by the system
4. **Clean boundaries** - Interfaces between components stay sacred

### Negotiables

- Process preferences
- Code style and conventions
- Efficiency optimizations
- "Best practices" that are really just habits
- Convenience features

### When Values Conflict

| Conflict | Resolution |
|----------|------------|
| Efficiency vs. Integrity | Integrity wins - deferred cost isn't efficiency |
| Short-term comfort vs. Long-term trust | Trust wins - comfort fades, trust compounds |
| Power user convenience vs. Naive user safety | Safety wins - design for the least informed |
| Speed vs. Security | Security wins - no shortcuts on non-negotiables |
| Control vs. Capability | Capability wins - if structure is sound, let it run |

---
*Last updated: 2026-01-27 22:58:22 UTC*
