# MODELS

Mental frameworks that guide how decisions are made, problems are solved, and quality is maintained.

---

## Decision Framework

### Core Principle: Bias Toward Action With Smart Guardrails

**Speed vs. Perfection**
- Working code over perfect plans
- Foundation gets the time investment; features ship fast
- Perfection is a trap - working code teaches what perfect actually means

**Risk vs. Opportunity**
- Lean hard into opportunity - big swings are worth taking
- Build guardrails as you go: permission tiers, audit trails, kill switches
- Take the big swing, but wear a helmet

**Data vs. Intuition**
- Intuition picks the direction, data keeps you honest
- Trust your gut to start, trust the evidence to finish
- The PAI loop exists because this is how decisions should work

**Decision Speed**
- Solo builder mentality - commit to opinions, find out if you're wrong
- Wrong fast beats right eventually

### Decision Questions
1. "What's the simplest thing that could work?" - Start there
2. "Can I undo this?" - If yes, just do it. If no, sleep on it
3. "What will I wish I'd done in six months?" - Usually "started sooner"
4. "Am I building for a real problem or an imaginary one?" - Kill imaginary ones fast

---

## Problem-Solving Model

### Core Principle: Explore By Doing, Isolate To Understand

**Discovery Process**
1. **Touch it** - Run it, break it, see what happens before reading docs
2. **Map the edges** - Identify inputs, outputs, and connections
3. **Build a tracer bullet** - One ugly path through the whole system, end to end
4. **Fill in from there** - Now you know where everything goes

**Understanding vs. Building**
- Building IS understanding - scaffold rough to see where it breaks
- The breakage reveals what you didn't understand
- Code surfaces the real questions; upfront research can't

**Debugging Process**
- Isolate first - find the smallest version that still fails
- Strip away everything else until minimal reproduction
- Add logging at every boundary until reality diverges from expectation
- The bug is always at the boundary you didn't check

**Problem Decomposition**
- Always pieces, never whole - but find natural seams
- Each piece delivers something usable
- Don't build foundations forever waiting for the grand reveal

---

## Quality Standards

### Core Principle: Non-Negotiables Are Sacred, Everything Else Ships

**Non-Negotiables (Quality Treatment)**
| Area | Standard |
|------|----------|
| Security | Never compromised. Permissions, validation, secrets - right or it doesn't ship |
| Boundaries | Interfaces between components are sacred. Messy boundaries spread like cancer |
| Data Integrity | If it touches user data or system state, it's correct. Not "mostly correct" |

**Flexible (Good Enough Treatment)**
- Internal implementation can be rough if interface is clean
- UI can be ugly if UX is clear
- Docs can be sparse if code is obvious

**Quality Decision Rule**
> What happens if this thing is wrong?
> - "I fix it and nobody notices" → Good enough is fine
> - "Data corruption / security breach / cascade failure" → Quality treatment

**Technical Debt Philosophy**
- Let it accumulate strategically and consciously
- Debt in isolated modules = fine (pay down later)
- Debt in shared code or boundaries = pay immediately (interest rate is brutal)
- Write honest TODOs: "This is dumb but works, fix when X becomes a problem"

**Definition of Done**
- Works for the happy path
- Fails gracefully for obvious sad paths
- Boundaries clean enough to change internals later
- Not afraid to show it to someone
- There's a way to tell if it breaks

---

## Learning Model

### Core Principle: Compound Learning - Each Cycle Makes The Next Smarter

**Failure Philosophy**
- Failure is feedback with attitude
- First question: "What did this teach me?" not "How do I fix it?"
- Failures surface assumptions you didn't know you had - that's gold

**Capture and Retrieval**
- Write it down when it hurts - pain creates lasting lessons
- Capturing isn't enough; retrieve at the right moment
- Learnings get embedded into context, injected before decisions
- Not a knowledge base you query - a voice in the room that says "remember last time?"

**Experimentation Budget**
- Proven approaches first, experiment at the edges
- Use solved problems (FastAPI, Redis) to free up experimentation budget
- Experiment hard on the unsolved stuff - agent coordination, learning loops

**Pivot vs. Push Through**
> "Am I stuck because this is hard, or because this is wrong?"

| Signal | Meaning |
|--------|---------|
| Grinding but progressing | Hard - push through |
| Every step creates two new problems | Wrong - pivot |
| Scope creep, mounting edge cases | Wrong path |
| Solutions getting cleaner | Right path |

**System Learning Goal**
- Every decision informed by what came before, but not imprisoned by it
- Context, not rules - the system should get wiser, not more rigid
- Compound learning: the system makes both human and AI better at building systems

---

## Model Hierarchy

When models conflict, resolve in this order:

1. **Security** - Never compromised for any reason
2. **Data Integrity** - User trust is non-negotiable
3. **Clean Boundaries** - Future velocity depends on this
4. **Learning Capture** - Mistakes repeated are mistakes wasted
5. **Speed** - Ship and iterate beats plan and wait
