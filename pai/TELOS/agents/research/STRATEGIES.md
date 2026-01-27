# Research Agent Strategies

> Proven multi-step patterns for information gathering and documentation (stack-agnostic).

## Web Research Pattern

**Success Rate**: 93%
**When to Use**: General research, exploring new topics

**Pattern**:
```
1. DEFINE SCOPE  → Clarify what we need to know
                  - What specific question?
                  - What context?
                  - What format for output?

2. SEARCH        → Execute targeted searches
                  - Start broad, then narrow
                  - Use site: for specific sources
                  - Include year for recent info

3. FILTER        → Evaluate results
                  - Check source credibility
                  - Verify recency
                  - Look for consensus

4. EXTRACT       → Pull key information
                  - Note key facts
                  - Capture code examples
                  - Record caveats

5. SUMMARIZE     → Synthesize findings
                  - Answer original question
                  - Highlight key points
                  - Note gaps or uncertainties

6. CITE          → Document sources
                  - Link to original sources
                  - Note access date
                  - Flag any paywalled content
```

**Search Operators**:
- `site:example.com` - Specific domain
- `"exact phrase"` - Exact match
- `intitle:keyword` - In page title
- `[year1]..[year2]` - Date range

---

## Documentation Lookup Strategy

**Success Rate**: 96%
**When to Use**: Finding how to use a specific API, library, feature

**Pattern**:
```
1. OFFICIAL FIRST → Check official documentation
                   - Language docs
                   - Framework docs
                   - Library README/docs

2. VERSION CHECK  → Confirm docs match version
                   - Check version selector
                   - Note any version warnings
                   - Look for migration guides

3. EXAMPLES       → Find code examples
                   - Official examples
                   - Real-world usage in repositories
                   - Community Q&A accepted answers

4. EDGE CASES     → Look for gotchas
                   - Check GitHub issues
                   - Search for "common mistakes"
                   - Review error handling

5. SYNTHESIZE     → Combine into guidance
                   - Working code example
                   - Key parameters explained
                   - Common pitfalls noted
```

**Priority Order**:
1. Official documentation
2. Official examples/samples
3. High-reputation tutorials
4. Community Q&A (check votes)
5. Blog posts (verify against docs)

---

## Comparison Research Strategy

**Success Rate**: 89%
**When to Use**: Choosing between alternatives

**Pattern**:
```
1. DEFINE CRITERIA → What matters?
                    - Performance
                    - Ease of use
                    - Community/support
                    - Cost
                    - Learning curve

2. GATHER OPTIONS  → List all candidates
                    - Direct search
                    - "Alternative to X"
                    - Community recommendations

3. RESEARCH EACH   → Collect data points
                    - Official features list
                    - Benchmarks (if relevant)
                    - Adoption/popularity
                    - Recent activity

4. CREATE MATRIX   → Side-by-side comparison
                    - Criteria as rows
                    - Options as columns
                    - Rate each intersection

5. ANALYZE         → Weigh trade-offs
                    - Which criteria matter most?
                    - Clear winner or trade-offs?
                    - Context-dependent choice?

6. RECOMMEND       → Provide guidance
                    - Clear recommendation if possible
                    - "It depends" with decision tree
                    - Acknowledge uncertainty
```

**Comparison Table Template**:
```
| Criteria       | Option A | Option B | Option C |
|---------------|----------|----------|----------|
| Performance   | +++      | ++       | +        |
| Ease of use   | +        | +++      | ++       |
| Community     | +++      | ++       | +        |
| Best for:     | Scale    | Simple   | Budget   |
```

---

## Technical Investigation Strategy

**Success Rate**: 85%
**When to Use**: Deep dive into how something works

**Pattern**:
```
1. QUESTION     → Define what to investigate
                 - Be specific
                 - What would success look like?

2. HYPOTHESIZE  → Form initial theory
                 - Based on existing knowledge
                 - What do we expect?

3. RESEARCH     → Gather information
                 - Official documentation
                 - Source code if available
                 - Technical articles

4. EXPERIMENT   → Test understanding
                 - Create minimal example
                 - Verify hypothesis
                 - Adjust if wrong

5. DOCUMENT     → Record findings
                 - What we learned
                 - How it works
                 - Caveats and edge cases
```

**When Reading Source Code**:
1. Start at entry point
2. Follow the main path first
3. Note branching logic
4. Look for comments explaining "why"
5. Check test files for usage examples

---

## Knowledge Update Strategy

**Success Rate**: 91%
**When to Use**: Refreshing understanding of evolving topics

**Pattern**:
```
1. BASELINE     → Document current understanding
                 - What do we know?
                 - What version/date?

2. FIND LATEST  → Search for updates
                 - Official changelogs
                 - Release notes
                 - Blog announcements

3. COMPARE      → What changed?
                 - New features
                 - Deprecations
                 - Breaking changes

4. ASSESS IMPACT→ Does it affect us?
                 - Update needed?
                 - Migration required?
                 - New capabilities useful?

5. UPDATE DOCS  → Record new knowledge
                 - Update internal docs
                 - Note migration steps
                 - Flag for implementation
```

**Staying Current Sources**:
- Official blogs/newsletters
- Release feeds (GitHub, etc.)
- Tech news aggregators
- Conference talks/recordings

---

## Research Quality Checklist

Before finalizing any research:

```
□ Primary sources consulted (not just secondary)
□ Information is recent enough for domain
□ Multiple sources agree (or conflicts noted)
□ Code examples tested/verified if applicable
□ Caveats and limitations documented
□ All sources cited with links
□ Summary answers the original question
□ Output format matches request
```

---

*Last updated: 2026-01-26*
