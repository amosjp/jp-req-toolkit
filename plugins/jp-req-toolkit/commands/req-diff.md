# /req-diff — Generate requirement vs implementation diff reports

Read each markdown file from `docs/split/`, compare the requirements against the current codebase implementation, and generate a diff report per module. Reports are saved to `docs/diff/`.

## Arguments

- `$ARGUMENTS` — Optional: filter by module number or name (e.g., `08` or `geo-audit`). If omitted, process all modules.

## Execution Steps

### 1. Discover modules to analyze

List all `.md` files in `docs/split/` (excluding `README.md`):

```bash
ls docs/split/*.md | grep -v README
```

If `$ARGUMENTS` is provided, filter to matching files only.

Show the list and ask for confirmation before proceeding.

### 2. Detect project tech stack

Before launching sub-agents, scan the project to determine the tech stack:

1. Check for `package.json` → Node.js/React/Vue frontend
2. Check for `pom.xml` or `build.gradle` → Java backend
3. Check for `requirements.txt` or `pyproject.toml` → Python backend
4. Check for `go.mod` → Go backend
5. Check for `Cargo.toml` → Rust
6. Look at directory structure for frontend/backend/service separation
7. Check for i18n files (locales, translations)

Summarize the detected stack for sub-agent prompts.

### 3. Launch parallel SubAgents for diff analysis

For each module file, launch a SubAgent (using the Agent tool) in parallel. **Maximize parallelism** — launch all independent SubAgents in a single message.

Each SubAgent receives the following prompt:

---

**SubAgent prompt template:**

```
You are a requirements-vs-implementation diff analyzer.

## Your Task

Read the requirements document at: `docs/split/{filename}`
Then search the codebase to determine what has been implemented and what hasn't.

## Project Tech Stack
{DETECTED_TECH_STACK from Step 2}

## Analysis Instructions

1. **Read the full requirements document** — understand every requirement point, UI element, validation rule, error message, and flow described
2. **Search the codebase** for corresponding implementations:
   - Use Grep to find relevant components, services, controllers
   - Read the actual implementation files to verify behavior
   - Check i18n files for text/copy requirements
   - Check both frontend AND backend code
3. **Compare** each requirement against the code and categorize

## Output Format

Generate a markdown report in EXACTLY this format:

```markdown
# Module {NN}: {模块名} — 需求 vs 实现差异分析

## 需求概要
{2-3 sentence summary of what this module requires}

## 已实现 ✅
{List each implemented requirement with file:line references}
- **{Feature name}**: `{file}` (L{line}) {brief description of how it's implemented}

## 未实现 / 差异 ❌

### D1. {差异标题}
- **需求**: {what the requirement says}
- **代码**: {what the code actually does, or "未找到对应实现"}
- **决策**: {suggested fix or decision needed}
- **影响文件**: `{file path}` ({specific location})

### D2. ...

## 不适用 N/A
{Requirements that can't be implemented due to platform constraints}

## 部分实现 ⚠️
{Requirements that are partially done}

## 实现超出需求 ➕
{Features in the code that go beyond the requirements}
```

## CRITICAL Rules:
- Include SPECIFIC file paths and line numbers (e.g., `GeoAuditPage.tsx` L209-247)
- For each "已实现" item, you MUST verify the code actually exists — don't assume
- For "未实现" items, search thoroughly before concluding something is missing
- Check BOTH source language and target language text requirements against i18n files
- Compare UI element specifications (buttons, labels, placeholders) against actual rendered text
- Number all diff items as D1, D2, D3, etc.
- Keep the report factual — no opinions, just facts and references

Save the report to: `docs/diff/{filename-without-ext}-diff.md`
```

---

### 4. E2E test coverage analysis (if tests exist)

Check if an `e2e/` or `tests/e2e/` directory exists. If it does, launch a **second wave of parallel SubAgents** to analyze E2E test coverage against the split requirements.

The user should provide a module-to-test-directory mapping if the test directory structure is non-obvious. If not provided, the sub-agent should infer the mapping from directory names and test file contents.

#### SubAgent prompt for E2E coverage analysis

For each module, launch a SubAgent with:

```
You are an E2E test coverage analyzer.

## Your Task
1. Read the requirements document at: `docs/split/{split_filename}`
2. Find and read test files that correspond to this module
3. Determine which requirements have E2E test coverage and which don't

## Analysis Instructions
- Extract every testable requirement from the split doc (UI elements, flows, validations, error messages, i18n text)
- For each test file, read the test blocks to understand what is being tested
- Map each test case to the requirement(s) it covers
- Identify requirements with NO test coverage

## Output Format
Generate a report and WRITE it to `docs/diff/{split_filename_base}-e2e-coverage.md`:

```markdown
# Module {NN}: {模块名} — E2E 测试覆盖率分析

## 测试文件
- `{test_file_1}` ({N} test cases)
- `{test_file_2}` ({N} test cases)

## 已覆盖需求 ✅
| # | Requirement | Test Case | File |
|---|-------------|-----------|------|
| 1 | {requirement description} | {test name} | `{file}` |

## 未覆盖需求 ❌
| # | Requirement | Priority | Reason |
|---|-------------|----------|--------|
| 1 | {requirement description} | P0/P1/P2 | {why it matters} |

## 覆盖率统计
- Total testable requirements: {N}
- Covered by E2E: {N} ({%})
- Not covered: {N} ({%})
- Coverage assessment: {GOOD/MODERATE/LOW}
```

CRITICAL: Read the actual test code, not just file names. Match test assertions to specific requirements.
```

#### Parallelism
Launch ALL E2E coverage SubAgents in a single message. They are independent of each other and independent of the Step 3 agents.

### 5. Collect results

After all SubAgents complete, read the generated reports and compile TWO summary tables:

**Table 1: Implementation Diff**
```markdown
| Module | File | ✅ Implemented | ❌ Gaps | ⚠️ Partial | ➕ Extra |
|--------|------|---------------|---------|-----------|---------|
| 01 | common-rules | 12 | 3 | 1 | 2 |
```

**Table 2: E2E Test Coverage** (only if Step 4 was run)
```markdown
| Module | Test Files | Test Cases | Covered Reqs | Uncovered Reqs | Coverage % |
|--------|-----------|------------|-------------|---------------|-----------|
| 01 | 2 | 8 | 10 | 3 | 77% |
```

### 6. Report results

Output:
- Total modules analyzed
- Implementation diff summary table
- E2E coverage summary table (if applicable)
- Top priority gaps (D items across all modules that are most critical)
- Top priority untested requirements (high-risk items with no E2E coverage)
- Link to `docs/diff/` directory

## Notes

- **Parallelism**: Launch ALL SubAgents in a single tool call for maximum speed. Each module is independent.
- **Existing reports**: If `docs/diff/` already has reports, they will be overwritten with fresh analysis.
- **Skip small modules**: Modules with < 10 lines can be skipped or given minimal analysis.
- **SubAgent model**: Use the default model for SubAgents (they need to read code and reason about requirements).
