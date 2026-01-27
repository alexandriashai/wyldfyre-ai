# QA Agent Strategies

> Proven multi-step patterns for testing and quality assurance (stack-agnostic).

## Test Suite Execution Strategy

**Success Rate**: 97%
**When to Use**: Running tests before merge, CI/CD

**Pattern**:
```
1. LINT        → Run static analysis
               - Syntax errors
               - Style violations
               - Potential bugs

2. TYPE CHECK  → Run type checker (if applicable)
               - Catch type mismatches
               - Verify interfaces

3. UNIT        → Run unit tests
               - Fast feedback
               - Isolated failures

4. INTEGRATION → Run integration tests
               - Component interactions
               - Database operations
               - External services (mocked)

5. E2E         → Run end-to-end tests
               - Critical user paths
               - Full stack validation

6. REPORT      → Generate coverage report
               - Coverage percentage
               - Uncovered lines
               - Test duration
```

**CI Pipeline Order**:
```
lint → type-check → unit → integration → e2e → deploy
(fast)                                         (slow)
```

**Fail Fast**: Stop pipeline on first failure to save time.

---

## Bug Investigation Strategy

**Success Rate**: 92%
**When to Use**: Investigating reported bugs

**Pattern**:
```
1. REPRODUCE   → Confirm the bug exists
               - Follow exact steps reported
               - Note environment (OS, browser, version)
               - Document actual vs expected

2. ISOLATE     → Find minimal reproduction
               - Remove unrelated factors
               - Simplify inputs
               - Identify exact conditions

3. LOCATE      → Find the failing code
               - Add logging/breakpoints
               - Trace execution path
               - Check recent changes (git blame)

4. ROOT CAUSE  → Understand WHY it fails
               - Not just WHERE, but WHY
               - Could be multiple causes
               - Consider edge cases

5. DOCUMENT    → Write up findings
               - Root cause explanation
               - Affected scenarios
               - Suggested fix approach

6. VERIFY FIX  → Confirm fix works
               - Bug no longer reproduces
               - Add regression test
               - Check for side effects
```

**Bug Report Template**:
```markdown
## Bug: [Title]

### Steps to Reproduce
1. ...
2. ...
3. ...

### Expected Behavior
...

### Actual Behavior
...

### Root Cause
...

### Fix
...
```

---

## Security Scan Strategy

**Success Rate**: 94%
**When to Use**: Security audit, before release

**Pattern**:
```
1. STATIC ANALYSIS → Scan code for vulnerabilities
                    - SAST tools
                    - Check for OWASP Top 10
                    - Review flagged issues

2. DEPENDENCY CHECK→ Scan dependencies
                    - Check for known CVEs
                    - Identify outdated packages

3. SECRETS SCAN   → Check for exposed secrets
                    - API keys in code?
                    - Credentials in config?
                    - Env files committed?

4. CONFIGURATION  → Review security config
                    - HTTPS enforced?
                    - CORS properly set?
                    - Headers configured?

5. MANUAL REVIEW  → Check high-risk areas
                    - Authentication flows
                    - Authorization checks
                    - Input validation

6. REPORT         → Document findings
                    - Severity classification
                    - Remediation steps
                    - Timeline for fixes
```

**Security Review Checklist**:
```
□ No hardcoded secrets
□ Input validation on all endpoints
□ Output encoding for XSS prevention
□ Parameterized queries (no injection)
□ Authentication on sensitive endpoints
□ Authorization checks for data access
□ HTTPS enforced
□ Security headers configured
□ Dependencies up to date
□ Error messages don't leak info
```

---

## Code Review Flow Strategy

**Success Rate**: 90%
**When to Use**: Reviewing pull requests

**Pattern**:
```
1. UNDERSTAND   → Read PR description
                - What problem does it solve?
                - What approach was taken?
                - Any concerns noted?

2. BIG PICTURE  → Review architecture
                - Does design make sense?
                - Right level of abstraction?
                - Fits existing patterns?

3. SECURITY     → Check for vulnerabilities
                - Input validation?
                - Auth/authz correct?
                - Secrets handling?

4. CORRECTNESS  → Verify logic
                - Does code do what it claims?
                - Edge cases handled?
                - Error handling present?

5. TESTS        → Check test coverage
                - New code tested?
                - Edge cases covered?
                - Tests actually test something?

6. STYLE        → Check readability
                - Naming clear?
                - Logic understandable?
                - Comments where needed?

7. FEEDBACK     → Write constructive review
                - Prefix with severity
                - Explain the why
                - Suggest improvements
```

**Review Feedback Format**:
```
[SEVERITY]: [CATEGORY]
[Clear explanation of the issue]
[Suggested fix or question]

Example:
BLOCKER: Security
User input is used directly in query without validation.
Use parameterized queries to prevent injection.
```

---

## Regression Testing Strategy

**Success Rate**: 93%
**When to Use**: After changes, before release

**Pattern**:
```
1. IDENTIFY     → Determine affected areas
                - What code changed?
                - What depends on it?
                - What could break?

2. PRIORITIZE   → Order tests by risk
                - Critical paths first
                - Affected components
                - Recently buggy areas

3. SELECT       → Choose test scope
                - Changed: Always run
                - Dependent: Run if time
                - Unrelated: Skip unless full

4. EXECUTE      → Run selected tests
                - Unit tests (fast)
                - Integration tests
                - E2E for critical paths

5. ANALYZE      → Review failures
                - Real regression?
                - Flaky test?
                - Test needs update?

6. EXPAND       → If issues found
                - Widen test scope
                - Add missing tests
                - Manual verification
```

**Risk-Based Selection**:
```
HIGH RISK (always test):
- Payment/billing
- Authentication
- Data mutations
- API contracts

MEDIUM RISK (test if time):
- UI components
- Reporting
- Non-critical features

LOW RISK (skip unless full):
- Cosmetic changes
- Documentation
- Dev tools
```

---

## Test Writing Strategy

**Success Rate**: 88%
**When to Use**: Writing new tests

**Pattern**:
```
1. IDENTIFY     → What needs testing?
                - New functionality
                - Bug fix (regression test)
                - Edge cases

2. PLAN         → Determine test types
                - Unit: Logic, pure functions
                - Integration: Boundaries
                - E2E: User flows

3. ARRANGE      → Set up test data
                - Clear, minimal fixtures
                - Independent of other tests
                - Deterministic (no randomness)

4. ACT          → Execute the code
                - Single action per test
                - Clear what's being tested

5. ASSERT       → Verify results
                - One assertion per test (ideally)
                - Test behavior, not implementation
                - Clear failure messages

6. CLEANUP      → Reset state
                - No side effects
                - Tests can run in any order
```

**Good Test Qualities**:
```
□ Fast (< 100ms for unit)
□ Isolated (no dependencies between tests)
□ Repeatable (same result every time)
□ Self-validating (clear pass/fail)
□ Timely (written with the code)
```

---

*Last updated: 2026-01-26*
