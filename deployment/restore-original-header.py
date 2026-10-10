#!/usr/bin/env python3
"""Restore the original Feelcoin homepage header from approved GitHub index.html.

Only replaces desktop/mobile header <nav> blocks and removes the two CSS
overrides from the rejected wallet dropdown redesign. Dry run by default.
"""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile

NAVS = (
    ("desktop", re.compile(r'<nav class="desktop-nav"[^>]*>.*?</nav>', re.S)),
    ("mobile", re.compile(r'<nav\s+id="mobileNav"[^>]*>.*?</nav>', re.S)),
)
REMOVABLE_STYLES = (
    ("/* FEELCOIN_CENTER_NAV_ARROW_V1_START */",
     "/* FEELCOIN_CENTER_NAV_ARROW_V1_END */"),
    ("/* FEELCOIN_SINGLE_ROW_WALLET_MENU_V1_START */",
     "/* FEELCOIN_SINGLE_ROW_WALLET_MENU_V1_END */"),
    ("/* FEELCOIN_NAV_WALLETS_V2_START",
     "/* FEELCOIN_NAV_WALLETS_V2_END */"),
)


def only_one(pattern, html, label):
    matches = list(pattern.finditer(html))
    if len(matches) != 1:
        raise RuntimeError(f"{label}: expected 1 navigation block; found {len(matches)}")
    return matches[0]


def validate_original(nav, label):
    required = (
        '<a href="#ecosystem">Ecosystem</a>',
        '<a href="#mining">Mining</a>',
        '<a href="#desktop-wallet">Desktop Wallet</a>',
        '<a href="#android-wallet">Android Wallet</a>',
        '>Documentation</a>',
        '>Developers / API</a>',
    )
    for item in required:
        if nav.count(item) != 1:
            raise RuntimeError(f"Approved {label}: invalid original link {item}")
    for forbidden in ('fc-nav-wallets', 'fc-wallets-menu',
                      '>Explorer</a>', '<summary>Wallets ',
                      '<summary>Download Wallets'):
        if forbidden in nav:
            raise RuntimeError(f"Approved {label}: unexpected newer feature {forbidden}")


def restore(live, approved):
    result = live
    for name, rx in NAVS:
        baseline = only_one(rx, approved, "GitHub " + name).group()
        original = only_one(rx, result, "Production " + name).group()
        validate_original(baseline, name)
        # Check only that the live block is indeed a Feelcoin header;
        # don't depend on its current wallet/explorer link arrangement.
        if ('href="#ecosystem"' not in original or
            'href="https://wallet.feelcoin.org"' not in result or
            'href="#docs"' not in original):
            raise RuntimeError("Unexpected live " + name + " navigation")
        result = result.replace(original, baseline, 1)
    for start, end in REMOVABLE_STYLES:
        first, last = result.count(start), result.count(end)
        if first != last or first > 1:
            raise RuntimeError(f"Partial or duplicate CSS marker: {start}")
        if first:
            left = result.index(start)
            right = result.index(end)
            if right < left:
                raise RuntimeError("CSS markers out of order")
            right += len(end)
            result = result[:left] + result[right:]
    if "min-height:78px;" not in result:
        raise RuntimeError("Original header height missing; no modifications")
    for name, rx in NAVS:
        validate_original(only_one(rx, result, name).group(), name)
    return result, result != live


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--live", type=Path, required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    live_path = args.live
    if not live_path.is_absolute() or live_path.name != "index.html":
        ap.error("--live must be the absolute path of index.html")
    if live_path.is_symlink() or not live_path.is_file() or not args.source.is_file():
        ap.error("Missing source/live file or live path is symlink")
    current = live_path.read_text(encoding="utf-8")
    approved = args.source.read_text(encoding="utf-8")
    updated, changed = restore(current, approved)
    if not changed:
        print("Already restored: original Feelcoin single-row header")
        return
    if not args.apply:
        print("Dry run OK: original header ready; all other website content preserved")
        return
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup = live_path.with_name(live_path.name + ".before-original-header-" + stamp)
    if backup.exists():
        raise RuntimeError(f"Backup already exists: {backup}")
    perms = live_path.stat()
    shutil.copy2(live_path, backup)
    fd, path = tempfile.mkstemp(dir=live_path.parent, prefix=".feelcoin-original-header-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            out.write(updated)
            out.flush()
            os.fsync(out.fileno())
        os.chmod(path, stat.S_IMODE(perms.st_mode))
        os.chown(path, perms.st_uid, perms.st_gid)
        os.replace(path, live_path)
    finally:
        if os.path.exists(path):
            os.unlink(path)
    print("SUCCESS: restored original single-row header")
    print(f"Backup: {backup}")


if __name__ == "__main__":
    main()
