# /split-docx — Split a .docx requirements file into per-module markdown

Split a `.docx` file into individual markdown files by document module, preserving images and fixing formatting. Supports downloading directly from Feishu/Lark online documents. Output goes to `docs/split/`.

## Arguments

- `$ARGUMENTS` — Optional: Feishu URL, filename, or partial match of a .docx file. If omitted, ask user to choose the source.

## Execution Steps

### 0. Choose source — Feishu online or local file

Ask the user: **"Do you want to download from a Feishu online document, or use a local .docx file?"**

Options:
- **Feishu online** → Go to Step 1A (Feishu download flow)
- **Local file** → Go to Step 1B (local file selection)

If `$ARGUMENTS` starts with `http` and contains `feishu.cn` or `larkoffice.com` or `larksuite.com`, automatically choose Feishu flow.

### 1A. Feishu download flow

#### 1A.1 Check Feishu config

Look for saved config at `~/.claude/jp-config.json`:

```json
{"app_id": "cli_xxx", "app_secret": "yyy"}
```

- If config exists: show the saved `app_id` (masked) and ask if user wants to use it
- If config does NOT exist: ask the user to provide their Feishu App ID and App Secret, then save to `~/.claude/jp-config.json` for future use

#### 1A.2 Download from Feishu

Run the download script:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/feishu-export.py "<feishu_url>" --output-dir docs/req --config ~/.claude/jp-config.json
```

If `--app-id` and `--app-secret` were provided by user (first time), pass them:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/feishu-export.py "<feishu_url>" --output-dir docs/req --app-id "<id>" --app-secret "<secret>" --config ~/.claude/jp-config.json
```

The script automatically handles file versioning:
- If a file with the same name exists, it appends `.V.1`, `.V.2`, etc.
- Example: `需求.docx` → `需求.V.1.docx` → `需求.V.2.docx`

Use the downloaded file path as the input for Step 2.

### 1B. Local file selection

If `$ARGUMENTS` is provided, match it against files in `docs/req/*.docx`:
- Exact match: use that file
- Partial match: use the best match
- No match: list available files and ask user to choose

If `$ARGUMENTS` is empty, list all `.docx` files in `docs/req/` and ask the user which one to split.

### 2. Confirm and run the split

Show the user:
- Input file path (downloaded or local)
- Output directory (`docs/split/`)
- Whether `--clean` will be used (default: yes)
- Whether strikethrough content will be removed (default: yes)

Ask for confirmation, then run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/split-docx.py "<selected-file>" --output-dir docs/split --clean
```

If the script detects strikethrough content, it will report it. The default is to REMOVE strikethrough text (deleted requirements). If the user wants to keep it, use `--keep-strikethrough`.

Review the output for:
- Number of sections detected
- Any WARNING messages about missing headings
- Number of images extracted
- Strikethrough content detected and removed

### 3. Post-process and verify

After the script completes:

1. **Read the generated README.md** to verify the module index looks correct
2. **Spot-check 2-3 files** for formatting quality:
   - Are headings properly formatted with `#`/`##`/`###`?
   - Are image paths relative (`media/xxx.png`)?
   - Are prompt templates in code blocks (not HTML tables)?
   - Are tables rendered correctly?
   - No stray HTML entities or escaped characters?
3. **Check for remaining issues** and fix them:
   - Escaped brackets: `\[text\]` → `[text]`
   - Remaining bold-as-heading patterns not caught by the script
   - Empty or near-empty files (< 5 lines) that might indicate a split issue

### 4. Report results

Output a summary:
- Source: Feishu URL or local file
- Number of files created
- Total images extracted
- Strikethrough content: how many items removed (if any)
- Any files that might need manual review (very short or very long)
- Link to the README.md for the full index

## Customization

### Module Slug Mapping

The `split-docx.py` script contains a `MODULE_SLUGS` dictionary that maps Chinese module names to English slugs. If your project uses different module names, edit `${CLAUDE_PLUGIN_ROOT}/scripts/split-docx.py` and update the `MODULE_SLUGS` dict.

### Section Expansion

The `EXPAND_SECTIONS` dict in the script controls which top-level sections are further split into sub-sections. Customize this for your document structure.

## Notes

- **Dependencies**: `pandoc`, `python-docx`, `requests` (for Feishu download)
- **Section detection** is based on font size + bold formatting (not heading styles), since many Chinese requirement docs use formatting instead of Word heading styles
- **Strikethrough content** (删除线) is automatically removed — it represents deleted/deprecated requirements. Use `--keep-strikethrough` to preserve it
- **Single-cell tables** (used as code containers in Chinese docs) are automatically converted to markdown code blocks
- The `--level 1` flag can be used for a coarser split (top-level sections only, ~5 files)
- Images are extracted to `docs/split/media/` and referenced with relative paths
- Feishu config is saved at `~/.claude/jp-config.json` — **do NOT commit this file** (contains app_secret)
