# jp-req-toolkit

A Claude Code plugin for requirements-driven development. Split `.docx` requirement docs into modules, diff requirements against your codebase, and generate E2E test cases from gaps.

## Features

| Command | Description |
|---------|-------------|
| `/split-docx` | Split a `.docx` file into per-module markdown files. Supports Feishu/Lark online docs. |
| `/req-diff` | Compare requirement docs against codebase implementation. Generates diff reports per module. |
| `/gen-e2e` | Generate Playwright E2E test cases from requirement gaps. Strict assertions, no soft pass. |

## Install

```bash
# Step 1: Add the marketplace
claude plugin marketplace add amosjp/jp-req-toolkit

# Step 2: Install the plugin
claude plugin install jp-req-toolkit@jp-req-toolkit
```

## Prerequisites

- **pandoc** — `brew install pandoc` (macOS) or `apt install pandoc` (Linux)
- **python-docx** — `pip install python-docx`
- **Python 3.10+**

## Setup

### Feishu/Lark Integration (optional)

If you want to download requirement docs directly from Feishu:

1. Copy the example config:
   ```bash
   cp ~/.claude/plugins/*/jp-req-toolkit/.jp-config.example.json ~/.claude/jp-config.json
   ```

2. Edit `~/.claude/jp-config.json` with your Feishu app credentials:
   ```json
   {
     "app_id": "cli_your_app_id",
     "app_secret": "your_app_secret"
   }
   ```

   Or skip this step — the plugin will prompt you on first use and save the config automatically.

### Project Directory Convention

The plugin expects this directory structure in your project:

```
your-project/
├── docs/
│   ├── req/          # .docx requirement files
│   ├── split/        # Split markdown output (generated)
│   ├── diff/         # Diff reports (generated)
│   └── report/e2e/   # Test reports (generated)
└── e2e/              # E2E tests (for gen-e2e)
```

Directories are created automatically as needed.

## Usage

### 1. Split a requirements document

```
/split-docx                          # Interactive: choose source
/split-docx docs/req/requirements.docx   # Local file
/split-docx https://xxx.feishu.cn/docx/xxx  # Feishu online doc
```

### 2. Generate diff reports

```
/req-diff           # All modules
/req-diff 08        # Single module by number
/req-diff geo-audit # Single module by name
```

### 3. Generate E2E tests

```
/gen-e2e              # All modules
/gen-e2e 08           # Single module
/gen-e2e 03-05        # Range of modules
```

## Customization

### Module Slug Mapping

The `scripts/split-docx.py` script contains a `MODULE_SLUGS` dictionary that maps Chinese module names to English filename slugs. Edit this dict if your project uses different naming.

### Section Expansion

The `EXPAND_SECTIONS` dict controls which top-level sections get split into sub-sections. Customize for your document's heading structure.

## How It Works

1. **split-docx**: Uses `python-docx` to detect section headings by font size/bold formatting (not Word heading styles), converts to GFM markdown via `pandoc`, splits at detected boundaries, and post-processes for clean output.

2. **req-diff**: Launches parallel sub-agents that each read a requirement module and search your codebase for implementations. Categorizes each requirement as implemented, missing, partial, or beyond-spec.

3. **gen-e2e**: Reads requirement docs and existing coverage reports, then generates Playwright test files with strict assertions, test user isolation, and `@smoke`/`@slow`/fast classification.

## License

MIT
