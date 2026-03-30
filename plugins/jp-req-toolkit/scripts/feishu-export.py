#!/usr/bin/env python3
"""
feishu-export.py — Download a Feishu/Lark online document as .docx file.

Uses the Feishu Open API to:
1. Authenticate with app_id + app_secret → tenant_access_token
2. Create an export task (docx format)
3. Poll until the export completes
4. Download the .docx file

Usage:
    python3 feishu-export.py <feishu_url> [--output-dir docs/req]
    python3 feishu-export.py <feishu_url> --app-id XXX --app-secret YYY
    python3 feishu-export.py <feishu_url> --config ~/.claude/jp-config.json

Config file format (jp-config.json):
    {"app_id": "cli_xxx", "app_secret": "yyy"}

No external dependencies — uses only Python stdlib (urllib).
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


FEISHU_BASE = "https://open.feishu.cn/open-apis"
DEFAULT_CONFIG_PATH = os.path.expanduser("~/.claude/jp-config.json")


# ── HTTP helpers (stdlib only) ───────────────────────────────────────────

def _post_json(url: str, body: dict, headers: dict | None = None, timeout: int = 15) -> dict:
    """POST JSON and return parsed response."""
    data = json.dumps(body).encode("utf-8")
    hdrs = {"Content-Type": "application/json; charset=utf-8"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, headers=hdrs, method="POST")
    resp = urllib.request.urlopen(req, timeout=timeout)
    return json.loads(resp.read())


def _get_json(url: str, headers: dict | None = None, params: dict | None = None, timeout: int = 15) -> dict:
    """GET JSON and return parsed response."""
    if params:
        query = "&".join(f"{k}={urllib.request.quote(str(v))}" for k, v in params.items())
        url = f"{url}?{query}"
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    resp = urllib.request.urlopen(req, timeout=timeout)
    return json.loads(resp.read())


def _download_file(url: str, headers: dict, output_path: str, timeout: int = 120):
    """Download a binary file."""
    req = urllib.request.Request(url, headers=headers, method="GET")
    resp = urllib.request.urlopen(req, timeout=timeout)
    with open(output_path, "wb") as f:
        while True:
            chunk = resp.read(8192)
            if not chunk:
                break
            f.write(chunk)


# ── URL parsing ──────────────────────────────────────────────────────────

def parse_feishu_url(url: str) -> dict:
    """Extract document_id and type from a Feishu/Lark URL.

    Supported URL formats:
        https://xxx.feishu.cn/docx/XXXXXXX
        https://xxx.feishu.cn/wiki/XXXXXXX
        https://xxx.larkoffice.com/docx/XXXXXXX
        https://xxx.larksuite.com/docx/XXXXXXX
    """
    patterns = [
        r"(?:feishu\.cn|larkoffice\.com|larksuite\.com)/(?P<type>docx|doc|wiki|sheet)/(?P<token>[A-Za-z0-9_-]+)",
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return {
                "type": m.group("type"),
                "token": m.group("token"),
            }
    raise ValueError(
        f"Cannot parse Feishu URL: {url}\n"
        "Expected format: https://xxx.feishu.cn/docx/XXXXXXX"
    )


# ── Auth ─────────────────────────────────────────────────────────────────

def get_tenant_access_token(app_id: str, app_secret: str) -> str:
    """Get tenant_access_token from Feishu Open API."""
    data = _post_json(
        f"{FEISHU_BASE}/auth/v3/tenant_access_token/internal",
        {"app_id": app_id, "app_secret": app_secret},
        timeout=10,
    )
    if data.get("code") != 0:
        raise RuntimeError(f"Auth failed: {data.get('msg', 'unknown error')}")
    return data["tenant_access_token"]


# ── Export ───────────────────────────────────────────────────────────────

def resolve_wiki_node(wiki_token: str, access_token: str) -> dict:
    """Resolve a wiki node token to get the actual document obj_token and obj_type."""
    data = _get_json(
        f"{FEISHU_BASE}/wiki/v2/spaces/get_node",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"token": wiki_token},
    )
    if data.get("code") != 0:
        raise RuntimeError(f"Wiki node lookup failed: {data.get('msg')}")
    node = data["data"]["node"]
    return {
        "obj_token": node["obj_token"],
        "obj_type": node["obj_type"],
        "title": node.get("title", ""),
    }


def create_export_task(file_token: str, file_type: str, access_token: str) -> str:
    """Create a document export task. Returns the ticket for polling."""
    type_map = {"docx": "docx", "doc": "docx", "wiki": "docx", "sheet": "xlsx"}
    export_type = type_map.get(file_type, "docx")

    data = _post_json(
        f"{FEISHU_BASE}/drive/v1/export_tasks",
        {"file_extension": export_type, "token": file_token, "type": file_type},
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    if data.get("code") != 0:
        raise RuntimeError(f"Create export task failed: {data.get('msg')} (code={data.get('code')})")
    return data["data"]["ticket"]


def poll_export_task(ticket: str, file_token: str, access_token: str, max_wait: int = 120) -> dict:
    """Poll the export task until it completes."""
    auth_headers = {"Authorization": f"Bearer {access_token}"}
    start = time.time()
    attempt = 0
    # Initial delay — Feishu sometimes returns status=2 before the task actually starts
    time.sleep(2)
    while time.time() - start < max_wait:
        attempt += 1
        data = _get_json(
            f"{FEISHU_BASE}/drive/v1/export_tasks/{ticket}",
            headers=auth_headers,
            params={"token": file_token},
        )
        if data.get("code") != 0:
            raise RuntimeError(f"Poll failed: {data.get('msg')}")

        result = data.get("data", {}).get("result", {})
        job_status = result.get("job_status", -1)

        if job_status == 0:
            return result
        elif job_status == 2:
            error_msg = result.get("job_error_msg", "")
            # Feishu sometimes returns status=2 with empty error on first poll
            # before the task actually starts — retry a few times
            if attempt <= 3 and not error_msg:
                print(f"   Task not ready yet, retrying... (attempt {attempt})")
                time.sleep(3)
                continue
            raise RuntimeError(f"Export task failed: {error_msg or json.dumps(result)}")

        print(f"   Export in progress... ({int(time.time() - start)}s)")
        time.sleep(3)

    raise TimeoutError(f"Export task did not complete within {max_wait}s")


def download_export_file(file_token: str, access_token: str, output_path: str):
    """Download the exported file."""
    _download_file(
        f"{FEISHU_BASE}/drive/v1/export_tasks/file/{file_token}/download",
        headers={"Authorization": f"Bearer {access_token}"},
        output_path=output_path,
    )


# ── File versioning ──────────────────────────────────────────────────────

def get_versioned_path(base_path: str) -> str:
    """If file exists, append V.1, V.2, etc. to avoid overwriting."""
    if not os.path.exists(base_path):
        return base_path

    stem = Path(base_path).stem
    suffix = Path(base_path).suffix
    parent = Path(base_path).parent

    version_match = re.match(r"^(.+?)\.V\.(\d+)$", stem)
    if version_match:
        base_stem = version_match.group(1)
        current_v = int(version_match.group(2))
    else:
        base_stem = stem
        current_v = 0

    version = current_v + 1
    while True:
        new_path = str(parent / f"{base_stem}.V.{version}{suffix}")
        if not os.path.exists(new_path):
            return new_path
        version += 1


# ── Config management ────────────────────────────────────────────────────

def load_config(config_path: str) -> dict:
    """Load Feishu config from JSON file."""
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            return json.load(f)
    return {}


def save_config(config_path: str, app_id: str, app_secret: str):
    """Save Feishu config to JSON file."""
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, "w") as f:
        json.dump({"app_id": app_id, "app_secret": app_secret}, f, indent=2)
    print(f"   Config saved to {config_path}")


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Download Feishu document as .docx")
    parser.add_argument("url", help="Feishu document URL")
    parser.add_argument("--output-dir", default="docs/req", help="Output directory (default: docs/req)")
    parser.add_argument("--filename", default=None, help="Output filename (default: auto from doc title)")
    parser.add_argument("--app-id", default=None, help="Feishu App ID")
    parser.add_argument("--app-secret", default=None, help="Feishu App Secret")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="Config file path")
    args = parser.parse_args()

    # Step 1: Parse URL
    print("[1/5] Parsing Feishu URL...")
    try:
        doc_info = parse_feishu_url(args.url)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"   Type: {doc_info['type']}, Token: {doc_info['token']}")

    # Step 2: Get credentials
    print("\n[2/5] Authenticating...")
    app_id = args.app_id
    app_secret = args.app_secret

    if not app_id or not app_secret:
        config = load_config(args.config)
        app_id = app_id or config.get("app_id")
        app_secret = app_secret or config.get("app_secret")

    if not app_id or not app_secret:
        print("Error: app_id and app_secret required.", file=sys.stderr)
        print(f"Provide via --app-id/--app-secret or config file: {args.config}", file=sys.stderr)
        sys.exit(1)

    access_token = get_tenant_access_token(app_id, app_secret)
    print("   Authenticated successfully")

    # Save config for reuse
    if not os.path.exists(args.config):
        save_config(args.config, app_id, app_secret)

    # Step 3: Resolve token (wiki needs extra lookup)
    export_token = doc_info["token"]
    export_type = doc_info["type"]
    if doc_info["type"] == "wiki":
        print("\n[3/6] Resolving wiki node...")
        wiki_node = resolve_wiki_node(doc_info["token"], access_token)
        export_token = wiki_node["obj_token"]
        export_type = wiki_node["obj_type"]
        print(f"   Wiki title: {wiki_node['title']}")
        print(f"   Actual doc: {export_type}/{export_token}")
    else:
        print("\n[3/6] Direct document (no wiki resolution needed)")

    # Step 4: Create export task
    print("\n[4/6] Creating export task...")
    ticket = create_export_task(
        file_token=export_token,
        file_type=export_type,
        access_token=access_token,
    )
    print(f"   Export ticket: {ticket}")

    # Step 5: Poll for completion
    print("\n[5/6] Waiting for export to complete...")
    result = poll_export_task(ticket, export_token, access_token)
    export_file_token = result.get("file_token", "")
    doc_name = result.get("file_name", f"feishu-{doc_info['token']}")
    print(f"   Export complete: {doc_name}")

    # Step 6: Download file
    print("\n[6/6] Downloading .docx file...")
    os.makedirs(args.output_dir, exist_ok=True)

    if args.filename:
        filename = args.filename
    else:
        filename = doc_name
        if not filename.endswith(".docx"):
            filename += ".docx"

    output_path = os.path.join(args.output_dir, filename)

    if os.path.exists(output_path):
        output_path = get_versioned_path(output_path)
        print(f"   File exists, using versioned name: {os.path.basename(output_path)}")

    download_export_file(export_file_token, access_token, output_path)
    size_kb = os.path.getsize(output_path) / 1024
    print(f"   Downloaded: {output_path} ({size_kb:.0f} KB)")

    print(f"\nDone! File saved to: {output_path}")
    return output_path


if __name__ == "__main__":
    main()
