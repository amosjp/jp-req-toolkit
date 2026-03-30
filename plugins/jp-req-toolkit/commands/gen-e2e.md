# /gen-e2e — Generate E2E test cases from split requirement documents

Read requirement documents from `docs/split/`, compare against existing tests and diff reports, then generate Playwright E2E test cases via parallel sub-agents. Tests follow strict assertion rules, minimize mocking, and are classified by execution performance.

## Arguments

- `$ARGUMENTS` — Optional: module filter (e.g., `08`, `geo-audit`, `03-05`). If omitted, show module list and ask user to choose.

## Core Principles

These rules are **non-negotiable** and must be embedded in every sub-agent prompt:

1. **NO soft pass** — Every assertion must be explicit and strict. Never use `.toBeTruthy()` on response objects, never skip verification, never assume success. Use `toBeVisible()`, `toHaveText()`, `toHaveValue()`, `toContainText()` with exact expected values.
2. **NO unnecessary mocking** — Use real backend APIs wherever possible. Only mock when:
   - Testing specific frontend input validation (before API call)
   - Testing error states that cannot be reliably reproduced
   - Testing specific response formatting (when real results vary)
   - Always add a comment explaining WHY the mock is necessary
3. **Use test user isolation** — Create random isolated test users per test suite instead of using shared accounts. This prevents scenario contamination across parallel tests. Clean up in `afterAll`.
4. **Strict tag-based classification**:
   - `@smoke` — Comprehensive coverage of the module's full functionality. Runs serially. Uses real APIs. Covers every major feature described in the requirement doc.
   - `@slow` — Tests that take >10s (real API calls, polling, multi-step flows). Runs serially, never concurrent.
   - No tag — Fast tests (<5s). Parallel-safe. Can use mocks for speed.
5. **Compare with existing tests** — Before generating, check `docs/diff/{module}-e2e-coverage.md` for gap analysis. Focus on uncovered requirements, don't duplicate existing test coverage.

## Execution Steps

### 1. Discover and select modules

List all `.md` files in `docs/split/` (excluding `README.md`):

```bash
ls docs/split/*.md | grep -v README
```

If `$ARGUMENTS` is provided:
- Number match: filter by prefix (e.g., `08` matches `08-xxx.md`)
- Name match: filter by slug (e.g., `geo-audit`)
- Range: `03-05` matches modules 03, 04, 05

Show the filtered list with module numbers and names. Ask the user to confirm before proceeding.

### 2. Detect test infrastructure

Before generating tests, scan the project's existing test setup:

1. **Test framework**: Check `package.json` or config files for Playwright, Cypress, Jest, etc.
2. **Test fixtures**: Look for `fixtures/` directory, helper files, shared setup
3. **Test patterns**: Read 1-2 existing test files to understand import paths, assertion styles, setup/teardown patterns
4. **API helpers**: Look for API client helpers, seed utilities, cleanup functions
5. **Test config**: Read playwright.config.ts or equivalent for project definitions

Summarize the detected infrastructure for sub-agent prompts.

### 3. Analyze existing coverage for each module

For each selected module, gather context:

#### 3a. Read the requirement document
Read `docs/split/{module_filename}` to understand all requirements.

#### 3b. Check for existing diff/coverage report
Look for `docs/diff/{module_base}-e2e-coverage.md`. If it exists, read the uncovered requirements section to identify gaps.

Also check `docs/diff/{module_base}-diff.md` for implementation status — skip requirements marked as not yet implemented in code.

#### 3c. Find existing test files
Search the e2e/test directory for files related to this module. Read existing test files to understand current coverage and code patterns.

### 4. Present generation plan to user

Before launching sub-agents, show a summary table:

```markdown
| Module | Requirement Points | Existing Tests | Covered | Gaps | Plan |
|--------|-------------------|----------------|---------|------|------|
| 08-geo-audit | 42 | 45 | 38 | 4 | Generate 6 new tests (4 gap + 2 smoke) |
```

Ask user to confirm the plan. User can:
- Approve all
- Select specific modules
- Adjust scope (e.g., "only smoke tests")

### 5. Launch parallel sub-agents for test generation

For each approved module, launch a sub-agent (using the Agent tool) with the following prompt template. **Launch ALL sub-agents in a single message for maximum parallelism.**

---

**Sub-agent prompt template:**

```
You are an E2E test case generator. Generate Playwright test cases that are strict, reliable, and well-classified.

## Input Context

### Requirement Document
{PASTE full content of docs/split/{module}.md}

### Existing Coverage Gaps (from diff report)
{PASTE uncovered requirements from docs/diff/{module}-e2e-coverage.md, or "No existing coverage report" if absent}

### Implementation Status
{PASTE key findings from docs/diff/{module}-diff.md, or "No diff report available"}

### Existing Test Files
{LIST existing test files and their test count for this module}

### Test Infrastructure Reference
{PASTE detected test infrastructure from Step 2 — imports, fixtures, helpers, patterns}

## Generation Rules

### STRICT ASSERTIONS — NO SOFT PASS
- NEVER: `expect(response).toBeTruthy()`, `expect(result).toBeDefined()`
- ALWAYS: `expect(response.status()).toBe(200)`, `await expect(locator).toHaveText('exact text')`
- Every test must have at least ONE hard assertion that would FAIL if the feature is broken
- For visibility checks: `toBeVisible()` is OK, but also verify content with `toHaveText()`/`toContainText()`

### MINIMAL MOCKING
- Default: use real backend APIs
- Only mock when you add a comment: `// Mock required: {reason}`
- Frontend input validation tests may mock the API endpoint to verify the validation fires BEFORE the API call

### TEST USER ISOLATION
- Each `test.describe` block that needs authentication MUST create its own isolated user
- Use the project's seed/factory utilities detected in Step 2
- Clean up after tests in `afterAll`
- Generate unique identifiers to prevent cross-test contamination

### TEST CLASSIFICATION (tags in test title)

**@smoke tests** — One comprehensive test per module that exercises the FULL happy path:
- Covers ALL major features described in the requirement doc
- Uses real APIs (no mocks)
- May take 30-60s
- Format: `test('SMOKE-{NN}: {Module} full feature walkthrough @smoke', ...)`

**@slow tests** — Individual tests that take >10s:
- Real API calls with polling/waiting
- Multi-step user flows
- Format: `test('{TC-ID}: {description} @slow', ...)`

**Fast tests (no tag)** — Tests that complete in <5s:
- Frontend validation, UI state, component behavior
- Can use mocks for speed
- Format: `test('{TC-ID}: {description}', ...)`

### OUTPUT

Generate a SINGLE `.spec.ts` file for this module with:
1. A file header comment explaining what requirements are covered
2. One `@smoke` test that covers the module's full feature set
3. Individual tests for each uncovered gap, classified as `@slow` or fast
4. Clean teardown of test users

Write the file following the project's existing test directory structure.

Name new files descriptively:
- `{feature}-coverage.spec.ts` — For gap-filling tests
- `{feature}-smoke.spec.ts` — For smoke tests
- `{feature}-validation.spec.ts` — For input validation tests

CRITICAL: Do NOT duplicate tests that already exist. Check existing files first.
```

---

### 6. Review generated tests

After all sub-agents complete, compile a summary:

```markdown
## Generated E2E Tests Summary

| Module | File | Tests | Smoke | Slow | Fast | New Coverage |
|--------|------|-------|-------|------|------|-------------|
| 08-geo-audit | audit-coverage.spec.ts | 8 | 1 | 2 | 5 | +15% |

### Files Created/Modified
- `e2e/tests/specs/tc-03-geo-audit/audit-coverage.spec.ts` (NEW, 8 tests)

### Coverage Improvement
- Before: 38/42 requirements covered (90%)
- After: 42/42 requirements covered (100%)
```

Show the summary and ask if the user wants to review any specific generated file.

### 7. Optional: Execute tests

Ask the user:

> **Tests generated. Would you like to run them now?**
> 1. Run all generated tests (fast + slow)
> 2. Run only fast tests
> 3. Run only smoke tests
> 4. Skip execution

If the user chooses to execute, run the tests using the project's test runner.

### 8. Generate test report

After execution completes (or if skipped, generate a "generation-only" report), create a report at:

```
docs/report/e2e/YYYY-MM-DD-HHmmss-{scope}.md
```

**Report format:**

```markdown
# E2E Test Report — {scope}

> Generated: {YYYY-MM-DD HH:mm:ss}
> Execution: {Yes/No}
> Duration: {total_time}

## Summary

| Metric | Value |
|--------|-------|
| Total tests generated | {N} |
| Smoke tests | {N} |
| Slow tests | {N} |
| Fast tests | {N} |
| Tests passed | {N} |
| Tests failed | {N} |

## Module Breakdown

| Module | Generated | Passed | Failed | Duration |
|--------|-----------|--------|--------|----------|
| {module} | {N} | {N} | {N} | {time} |

## Failed Tests (if any)

### {test_name}
- **File**: `{file_path}`
- **Error**: {error message}
- **Expected**: {expected}
- **Actual**: {actual}

## Generated Files

| File | Tests | Tags | Status |
|------|-------|------|--------|
| `{path}` | {N} | @smoke, @slow | {PASS/FAIL/NOT_RUN} |

## Requirement Traceability

| Requirement | Test Case | Status |
|-------------|-----------|--------|
| {req description} | {TC-ID} | {PASS/FAIL/NOT_RUN} |
```

## Notes

- **Sub-agent model**: Use default model (needs to read requirements and generate code)
- **Parallelism**: ALL module sub-agents launch in a single message
- **Existing tests**: NEVER overwrite existing spec files. Create new files with descriptive names
- **Report directory**: `docs/report/e2e/` — create if it doesn't exist
- **Cleanup**: Every test suite MUST clean up its test users in `afterAll`
- **No hardcoded waits**: Use `page.waitForResponse()`, `expect().toBeVisible()`, or polling helpers instead of `page.waitForTimeout()`
