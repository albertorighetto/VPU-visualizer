#!/usr/bin/env python3
"""
Enum Extraction Script
Downloads the official web UI's JS bundle straight from the device and
extracts the full VAR_ENUMS table it ships with - a complete, authoritative
list of every enum the device firmware defines (not just the subset this
app currently parses).

The device serves its web UI at http://<ip>:3000/ ; that page references a
content-hashed app.<hash>.js bundle which embeds a `const VAR_ENUMS={...}`
object (one entry per enum: key, items, order). This script fetches the
index page to find the current bundle filename (so it keeps working across
firmware/app rebuilds), downloads the bundle, and parses that object out.

Usage:
    python fetch_enums.py [IP] [--json OUT.json]

    Defaults: IP=127.0.0.1 (web UI on port 3000)
"""

import json
import re
import sys
import urllib.request
from typing import Dict, List, Tuple


def fetch(url: str, timeout: float = 30.0) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.read().decode('utf-8', errors='replace')


def find_bundle_url(ip: str) -> str:
    """Fetch the device's web UI index page and pull out the current app.<hash>.js path."""
    base = f"http://{ip}:3000"
    index_html = fetch(f"{base}/")
    match = re.search(r'src="(/app\.[a-f0-9]+\.js)"', index_html)
    if not match:
        raise RuntimeError("Could not find the app.<hash>.js bundle reference on the index page")
    return base + match.group(1)


def extract_var_enums_block(js_source: str) -> str:
    """Extract the raw `{...}` object literal assigned to `const VAR_ENUMS=`."""
    marker = "const VAR_ENUMS={"
    start = js_source.find(marker)
    if start == -1:
        raise RuntimeError("VAR_ENUMS declaration not found in bundle")

    # Brace-count from the opening '{' (right after "const VAR_ENUMS=") to find
    # the matching close, skipping over braces that appear inside string literals.
    pos = start + len(marker) - 1  # index of the opening '{'
    depth = 0
    in_string = False
    quote_char = ''
    i = pos
    while i < len(js_source):
        ch = js_source[i]
        if in_string:
            if ch == '\\':
                i += 1  # skip escaped character
            elif ch == quote_char:
                in_string = False
        elif ch in ("'", '"'):
            in_string = True
            quote_char = ch
        elif ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return js_source[pos:i + 1]
        i += 1

    raise RuntimeError("Unbalanced braces while scanning VAR_ENUMS block")


ENUM_PATTERN = re.compile(r"(\w+):\{key:'\1',items:\{(.*?)\},order:\[(.*?)\]\}", re.DOTALL)
ITEM_PATTERN = re.compile(r"(?:'((?:[^'\\]|\\.)*)'|(\w+)):'((?:[^'\\]|\\.)*)'")


def parse_enums(block: str) -> "dict[str, List[str]]":
    """Parse the VAR_ENUMS object literal into {enum_name: [values in declared order]}."""
    enums = {}
    for name, items_body, order_body in ENUM_PATTERN.findall(block):
        values_by_key = {}
        for quoted_key, bare_key, value in ITEM_PATTERN.findall(items_body):
            key = quoted_key if quoted_key else bare_key
            values_by_key[key] = value

        order = re.findall(r"'((?:[^'\\]|\\.)*)'", order_body)
        # Preserve declared order; fall back to items dict order for any stragglers.
        ordered_values = [values_by_key[k] for k in order if k in values_by_key]
        ordered_values += [v for k, v in values_by_key.items() if k not in order]

        enums[name] = ordered_values
    return enums


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    ip = args[0] if args else "127.0.0.1"

    json_out = None
    if "--json" in sys.argv:
        json_out = sys.argv[sys.argv.index("--json") + 1]

    print(f"[INFO] Locating app bundle on {ip}:3000...")
    bundle_url = find_bundle_url(ip)
    print(f"[INFO] Bundle: {bundle_url}")

    print("[INFO] Downloading bundle (this is a multi-MB file, may take a moment)...")
    js_source = fetch(bundle_url)
    print(f"[INFO] Downloaded {len(js_source):,} characters")

    print("[INFO] Extracting VAR_ENUMS block...")
    block = extract_var_enums_block(js_source)

    print("[INFO] Parsing enums...")
    enums = parse_enums(block)

    print()
    print("=" * 78)
    print(f" {len(enums)} ENUMS FOUND")
    print("=" * 78)
    for name in sorted(enums):
        values = enums[name]
        preview = ", ".join(values[:8]) + (", ..." if len(values) > 8 else "")
        print(f"  {name:<28} ({len(values):>3} values): {preview}")

    if json_out:
        with open(json_out, "w", encoding="utf-8") as f:
            json.dump(enums, f, indent=2, sort_keys=True)
        print(f"\n[INFO] Full enum list written to {json_out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
