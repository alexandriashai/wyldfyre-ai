# QA Agent Mental Models

> Frameworks for reasoning about testing, code review, and quality assurance (stack-agnostic).

## Test Pyramid Model

```
                    ┌───────────┐
                   /   E2E      \        Few, slow, expensive
                  /   Tests      \       Test critical paths
                 /   (UI/API)     \
                ├─────────────────┤
               /   Integration     \     More, medium speed
              /      Tests          \    Test boundaries
             /   (Components/APIs)   \
            ├─────────────────────────┤
           /       Unit Tests          \  Many, fast, cheap
          /    (Functions/Classes)      \ Test logic in isolation
         └───────────────────────────────┘

Coverage Targets:
┌─────────────────────────────────────────────────────────┐
│  LAYER         │  COUNT    │  COVERAGE   │  SPEED      │
├─────────────────────────────────────────────────────────┤
│  Unit          │  Many     │  80%+       │  < 100ms    │
│  Integration   │  Some     │  60%+       │  < 5s       │
│  E2E           │  Few      │  Critical   │  < 30s      │
└─────────────────────────────────────────────────────────┘
```

**Anti-patterns**:
- Ice cream cone (too many E2E, few unit)
- Testing implementation details
- Flaky tests (random failures)

**When to Use**: Planning test coverage
**Key Insight**: Fast tests catch bugs early; slow tests catch integration issues.

---

## Bug Severity Model

```
Severity Classification:

┌─────────────────────────────────────────────────────────┐
│  CRITICAL (P0)                                          │
│  - System down / unusable                               │
│  - Data loss or corruption                              │
│  - Security vulnerability (active exploit)              │
│  → Fix immediately, all hands                           │
├─────────────────────────────────────────────────────────┤
│  HIGH (P1)                                              │
│  - Major feature broken                                 │
│  - Affects many users                                   │
│  - Workaround is painful                                │
│  → Fix within 24 hours                                  │
├─────────────────────────────────────────────────────────┤
│  MEDIUM (P2)                                            │
│  - Feature partially broken                             │
│  - Affects some users                                   │
│  - Workaround exists                                    │
│  → Fix within 1 week                                    │
├─────────────────────────────────────────────────────────┤
│  LOW (P3)                                               │
│  - Minor inconvenience                                  │
│  - Cosmetic issues                                      │
│  - Edge cases                                           │
│  → Fix when convenient                                  │
└─────────────────────────────────────────────────────────┘

Severity Formula:
SEVERITY = IMPACT × FREQUENCY × (1 - WORKAROUND_EASE)
```

**When to Use**: Bug triage, prioritization
**Key Insight**: User impact determines priority, not technical complexity.

---

## Code Review Model

```
Review Priority Order:

┌────────────────────────────────────────────────────────┐
│  1. SECURITY                                           │
│     - Injection vulnerabilities?                       │
│     - XSS vulnerabilities?                             │
│     - Auth/authz bypasses?                             │
│     - Secrets exposed?                                 │
│     → MUST FIX before merge                            │
├────────────────────────────────────────────────────────┤
│  2. CORRECTNESS                                        │
│     - Does it do what it claims?                       │
│     - Edge cases handled?                              │
│     - Error handling present?                          │
│     - Tests cover new code?                            │
│     → MUST FIX before merge                            │
├────────────────────────────────────────────────────────┤
│  3. DESIGN                                             │
│     - Right abstraction level?                         │
│     - Follows existing patterns?                       │
│     - Extensible if needed?                            │
│     - Dependencies reasonable?                         │
│     → SHOULD FIX (discuss if disagree)                 │
├────────────────────────────────────────────────────────┤
│  4. STYLE                                              │
│     - Naming clear?                                    │
│     - Formatting consistent?                           │
│     - Comments helpful?                                │
│     → NITPICK (optional fix)                           │
└────────────────────────────────────────────────────────┘
```

**Review Comment Prefixes**:
- `BLOCKER:` Must fix before merge
- `CONCERN:` Should discuss/fix
- `NIT:` Optional improvement
- `QUESTION:` Need clarification

**When to Use**: Code review
**Key Insight**: Security and correctness are non-negotiable; style is preference.

---

## Regression Risk Model

```
Change Impact → Test Scope:

┌─────────────────────────────────────────────────────────┐
│  CHANGE TYPE           │  RISK    │  TEST SCOPE        │
├─────────────────────────────────────────────────────────┤
│  Fix in isolated       │  LOW     │  Unit tests for    │
│  function              │          │  that function     │
├─────────────────────────────────────────────────────────┤
│  Modify shared         │  MEDIUM  │  All consumers     │
│  utility/component     │          │  + integration     │
├─────────────────────────────────────────────────────────┤
│  Change interface/     │  HIGH    │  Full test suite   │
│  API contract          │          │  + manual check    │
├─────────────────────────────────────────────────────────┤
│  Update dependency     │  VARIES  │  Integration +     │
│  version               │          │  E2E for major     │
├─────────────────────────────────────────────────────────┤
│  Refactor (no          │  LOW*    │  Existing tests    │
│  behavior change)      │          │  should pass       │
└─────────────────────────────────────────────────────────┘

* If tests are comprehensive; otherwise HIGH
```

**When to Use**: Deciding what to test after changes
**Key Insight**: Change scope determines test scope; shared code = broad testing.

---

## Security Threat Model (OWASP-based)

```
Top Vulnerabilities to Check:

┌─────────────────────────────────────────────────────────┐
│  THREAT                 │  CHECK FOR                   │
├─────────────────────────────────────────────────────────┤
│  1. Injection           │  User input in queries,     │
│     (SQL, Command)      │  commands, templates         │
├─────────────────────────────────────────────────────────┤
│  2. Broken Auth         │  Weak passwords, session    │
│                         │  handling, token exposure    │
├─────────────────────────────────────────────────────────┤
│  3. Sensitive Data      │  Unencrypted storage,       │
│     Exposure            │  logs with PII, no HTTPS     │
├─────────────────────────────────────────────────────────┤
│  4. XXE/XML             │  External entity parsing,   │
│                         │  untrusted XML input         │
├─────────────────────────────────────────────────────────┤
│  5. Broken Access       │  Missing authz checks,      │
│     Control             │  IDOR vulnerabilities        │
├─────────────────────────────────────────────────────────┤
│  6. Security Misconfig  │  Default creds, verbose     │
│                         │  errors, unnecessary ports   │
├─────────────────────────────────────────────────────────┤
│  7. XSS                 │  User content in output     │
│                         │  without escaping            │
├─────────────────────────────────────────────────────────┤
│  8. Insecure            │  Untrusted object parsing,  │
│     Deserialization     │  user-controlled formats     │
├─────────────────────────────────────────────────────────┤
│  9. Using Components    │  Outdated deps with known   │
│     with Known Vulns    │  CVEs                        │
├─────────────────────────────────────────────────────────┤
│  10. Insufficient       │  No audit trail, errors     │
│      Logging            │  not logged properly         │
└─────────────────────────────────────────────────────────┘
```

**When to Use**: Security review, new feature assessment
**Key Insight**: Most vulnerabilities come from trusting user input.

---

*Last updated: 2026-01-26*
