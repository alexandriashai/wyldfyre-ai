# Research Agent Mental Models

> Frameworks for reasoning about information gathering and synthesis (stack-agnostic).

## Source Credibility Model

```
Source Evaluation Matrix:

┌─────────────────────────────────────────────────────────┐
│  SOURCE TYPE           │  TRUST   │  VERIFY HOW        │
├─────────────────────────────────────────────────────────┤
│  Official docs         │  HIGH    │  Check version     │
│  (language, framework) │          │  matches           │
├─────────────────────────────────────────────────────────┤
│  Peer-reviewed/RFC     │  HIGH    │  Check if          │
│  (academic, standards) │          │  superseded        │
├─────────────────────────────────────────────────────────┤
│  Reputable tech blogs  │  MEDIUM  │  Cross-reference   │
│  (known authors)       │          │  with docs         │
├─────────────────────────────────────────────────────────┤
│  Community Q&A         │  MEDIUM  │  Check votes,      │
│  (forums, discussions) │          │  accepted status   │
├─────────────────────────────────────────────────────────┤
│  Random blog posts     │  LOW     │  Test code before  │
│  (unknown authors)     │          │  using             │
├─────────────────────────────────────────────────────────┤
│  AI-generated content  │  VERIFY  │  Always validate   │
│                        │          │  against docs      │
└─────────────────────────────────────────────────────────┘
```

**Red Flags**:
- No date on article (could be outdated)
- No author attribution
- Contradicts official documentation
- Code examples don't include versions
- Comments disabled or all positive

**When to Use**: Evaluating any external information
**Key Insight**: Trust official docs > community > random sources.

---

## Search Strategy Model

```
Search Funnel:

BROAD SEARCH
┌─────────────────────────────────────────────────────────┐
│  "[topic] overview"                                     │
│  → Get overview of options                              │
│  → Understand landscape                                 │
└────────────────────────┬────────────────────────────────┘
                         ▼
NARROW SEARCH
┌─────────────────────────────────────────────────────────┐
│  "[option A] vs [option B] comparison [year]"           │
│  → Compare specific options                             │
│  → Understand trade-offs                                │
└────────────────────────┬────────────────────────────────┘
                         ▼
SPECIFIC SEARCH
┌─────────────────────────────────────────────────────────┐
│  "[option] [specific feature] example"                  │
│  → Implementation details                               │
│  → Code examples                                        │
└────────────────────────┬────────────────────────────────┘
                         ▼
VERIFY
┌─────────────────────────────────────────────────────────┐
│  Check official docs, GitHub issues                     │
│  → Confirm information is current                       │
│  → Look for known issues                                │
└─────────────────────────────────────────────────────────┘
```

**When to Use**: Starting any research task
**Key Insight**: Funnel from broad understanding to specific implementation.

---

## Documentation Structure Model

```
Documentation Hierarchy:

┌─────────────────────────────────────────────────────────┐
│  1. SUMMARY                                             │
│     What is this? One paragraph max.                    │
├─────────────────────────────────────────────────────────┤
│  2. KEY FINDINGS                                        │
│     Bullet points of main discoveries                   │
│     - Most important first                              │
│     - Actionable items highlighted                      │
├─────────────────────────────────────────────────────────┤
│  3. DETAILS                                             │
│     Supporting information organized by topic           │
│     - Technical specifications                          │
│     - Comparison tables                                 │
│     - Code examples                                     │
├─────────────────────────────────────────────────────────┤
│  4. SOURCES                                             │
│     Links to all referenced materials                   │
│     - Official documentation                            │
│     - Articles and tutorials                            │
│     - Repositories                                      │
├─────────────────────────────────────────────────────────┤
│  5. CAVEATS                                             │
│     Known limitations, outdated info, gaps              │
└─────────────────────────────────────────────────────────┘
```

**When to Use**: Writing research summaries
**Key Insight**: Readers want the answer first, details second.

---

## Knowledge Synthesis Model

```
Combining Multiple Sources:

SOURCE A ────┐
             │
SOURCE B ────┼───→ COMMON GROUND ───→ SYNTHESIS
             │     (What all agree)
SOURCE C ────┘
             │
             └───→ CONFLICTS ───→ RESOLUTION
                   (Disagreements)

Conflict Resolution:
┌─────────────────────────────────────────────────────────┐
│  1. Which source is more authoritative?                 │
│  2. Which information is more recent?                   │
│  3. Can both be true in different contexts?             │
│  4. Can we test to determine which is correct?          │
└─────────────────────────────────────────────────────────┘
```

**Synthesis Steps**:
1. List all claims from each source
2. Identify agreements (high confidence)
3. Identify conflicts (need resolution)
4. Identify gaps (need more research)
5. Produce unified understanding

**When to Use**: Combining information from multiple sources
**Key Insight**: Disagreements often indicate context-dependent truths.

---

## Currency Model (Information Freshness)

```
Information Decay by Domain:

┌─────────────────────────────────────────────────────────┐
│  DOMAIN              │  HALF-LIFE   │  VERIFY FREQUENCY │
├─────────────────────────────────────────────────────────┤
│  Frontend/UI         │  6 months    │  Every use        │
│  (frameworks, tools) │              │                   │
├─────────────────────────────────────────────────────────┤
│  Cloud/DevOps        │  1 year      │  Quarterly        │
│  (platforms, tools)  │              │                   │
├─────────────────────────────────────────────────────────┤
│  Programming langs   │  2-3 years   │  Annually         │
│  (syntax, stdlib)    │              │                   │
├─────────────────────────────────────────────────────────┤
│  Databases           │  3-5 years   │  Major versions   │
│  (concepts, APIs)    │              │                   │
├─────────────────────────────────────────────────────────┤
│  CS fundamentals     │  10+ years   │  Rarely changes   │
│  (algorithms, etc.)  │              │                   │
└─────────────────────────────────────────────────────────┘
```

**Freshness Indicators**:
- Article date vs current date
- Software versions mentioned vs current
- "This article was updated on..."
- Comments mentioning outdated info

**When to Use**: Assessing if information is still valid
**Key Insight**: Frontends evolve fast; fundamentals are stable.

---

*Last updated: 2026-01-26*
