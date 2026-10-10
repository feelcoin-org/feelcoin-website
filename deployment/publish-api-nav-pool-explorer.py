#!/usr/bin/env python3
"""Safely add the official Feelcoin API Docs link to Pool/Explorer navigation.

Default is read-only dry run. This intentionally patches existing deployed
files in place to preserve unrelated live UI changes.
"""
import argparse
import ast
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import stat
import tempfile

API_URL = "https://api.feelcoin.org/docs"
POOL_ANCHOR = ('<a href="https://explorer.feelcoin.org"\n'
               'target="_blank"\n'
               'rel="noopener noreferrer">\n'
               'Explorer\n'
               '</a>')
POOL_LINK = ('<a href="' + API_URL + '"\n'
             'target="_blank"\n'
             'rel="noopener noreferrer">\n'
             'API Docs\n'
             '</a>')
EXPLORER_ANCHOR = ('<a href="https://pool.feelcoin.org" '
                   'target="_blank" rel="noopener noreferrer">Mining Pool</a>')
EXPLORER_LINK = ('<a href="' + API_URL + '" target="_blank" '
                 'rel="noopener noreferrer" '
                 'aria-label="Feelcoin Public API Documentation">API Docs</a>')


def patch(source: str, kind: str):
    existing = source.count(API_URL)
    if existing:
        if existing == 2 and source.count(">API Docs</a>") == 2:
            return source, False
        raise RuntimeError(f"Partial or unexpected API links ({existing}); refusing edit")

    anchor, insertion = (
        (POOL_ANCHOR, POOL_LINK) if kind == "pool"
        else (EXPLORER_ANCHOR, EXPLORER_LINK)
    )
    count = source.count(anchor)
    if count != 2:
        raise RuntimeError(
            f"Expected exact desktop + mobile {kind} navigation anchors (2); "
            f"found {count}. No changes made."
        )
    result = source.replace(anchor, anchor + "\n" + insertion)
    if result.count(API_URL) != 2:
        raise RuntimeError("Link validation failed; no changes made")
    if kind == "explorer":
        ast.parse(result)  # The Explorer embeds its HTML in Python source.
    return result, True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=("pool", "explorer"), required=True)
    parser.add_argument("--apply", action="store_true",
                        help="Back up and update this file (default: dry run)")
    parser.add_argument("file", type=Path,
                        help="Absolute path of existing index.html/explorer.py")
    args = parser.parse_args()
    requested = args.file
    valid_name = "index.html" if args.kind == "pool" else "explorer.py"
    if not requested.is_absolute() or requested.name != valid_name:
        parser.error(f"Provide an absolute path ending in {valid_name}")
    if requested.is_symlink():
        parser.error("Refusing a symlink; specify the real target path explicitly")
    if not requested.is_file():
        parser.error("File not found")

    original = requested.read_text(encoding="utf-8")
    new, changed = patch(original, args.kind)
    if not changed:
        print(f"Already present: {requested} (two API links)")
        return
    if not args.apply:
        print(f"Dry run OK: can safely update {requested} (two API links)")
        return

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup = requested.with_name(requested.name + ".before-api-nav-" + stamp)
    if backup.exists():
        raise RuntimeError(f"Backup already exists: {backup}")
    original_stat = requested.stat()
    shutil.copy2(requested, backup)
    fd, temporary = tempfile.mkstemp(dir=requested.parent, prefix=".feelcoin-api-nav-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(new)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, stat.S_IMODE(original_stat.st_mode))
        os.chown(temporary, original_stat.st_uid, original_stat.st_gid)
        os.replace(temporary, requested)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print(f"Updated {requested} with two API navigation links")
    print(f"Backup: {backup}")


if __name__ == "__main__":
    main()
