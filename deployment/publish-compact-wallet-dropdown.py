#!/usr/bin/env python3
"""Install compact Feelcoin Wallets dropdown without changing the one-row header.

Use the approved index.html from GitHub as the source for nav markup and CSS.
The current production page is patched in place after a guarded dry run.
"""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile

CSS_START = "/* FEELCOIN_SINGLE_ROW_WALLET_MENU_V1_START */"
CSS_END = "/* FEELCOIN_SINGLE_ROW_WALLET_MENU_V1_END */"

DESKTOP = re.compile(r'<nav class="desktop-nav"[^>]*>.*?</nav>', re.S)
MOBILE = re.compile(r'<nav\s+id="mobileNav"[^>]*>.*?</nav>', re.S)
OLD = re.compile(
    r'<a href="#desktop-wallet">Desktop Wallet</a>\s*'
    r'<a href="#android-wallet">Android Wallet</a>\s*'
    r'<a href="#docs">Documentation</a>\s*'
    r'<a href="https://api\.feelcoin\.org/docs"[^>]*>'
    r'(?:API Docs|Developers / API)</a>\s*'
    r'<a href="https://explorer\.feelcoin\.org"[^>]*>Explorer</a>',
    re.S,
)
APPROVED = re.compile(
    r'<a href="https://explorer\.feelcoin\.org"[^>]*>Explorer</a>\s*'
    r'<details class="fc-nav-wallets[^"]*">\s*'
    r'<summary>Wallets .*?</summary>\s*'
    r'<div class="fc-nav-wallet-options">.*?</div>\s*</details>\s*'
    r'<a href="#docs">Documentation</a>\s*'
    r'<a href="https://api\.feelcoin\.org/docs"[^>]*>API Docs</a>',
    re.S,
)


def one(pattern, text, what):
    hits = list(pattern.finditer(text))
    if len(hits) != 1:
        raise RuntimeError(
            f"{what}: expected exactly one matching block, found {len(hits)}"
        )
    return hits[0]


def verify_nav(nav, name):
    if nav.count('<a href="https://explorer.feelcoin.org"') != 1:
        raise RuntimeError(f"{name}: Explorer link must appear once")
    if nav.count('<summary>Wallets ') != 1:
        raise RuntimeError(f"{name}: Wallets toggle must appear once")
    for link in ('href="#desktop-wallet"', 'href="#android-wallet"',
                 'href="https://paper.feelcoin.org"'):
        if nav.count(link) != 1:
            raise RuntimeError(f"{name}: expected one {link}")
    if '<a href="#mining">Mining</a>' not in nav:
        raise RuntimeError(f"{name}: original Mining nav unexpectedly missing")
    if nav.count('>API Docs</a>') != 1:
        raise RuntimeError(f"{name}: API Docs link missing")


def prepare(live, approved):
    if CSS_START in live:
        if CSS_END in live and live.count('<summary>Wallets ') == 2:
            for name, rx in (("desktop", DESKTOP), ("mobile", MOBILE)):
                verify_nav(one(rx, live, name).group(), name)
            return live, False
        raise RuntimeError("Partial existing dropdown deployment; refusing changes")
    if 'fc-nav-wallets' in live or 'FEELCOIN_NAV_WALLETS_V2_START' in live:
        raise RuntimeError("Unexpected or earlier two-row menu detected")

    css_match = re.search(
        re.escape(CSS_START) + r'.*?' + re.escape(CSS_END),
        approved, re.S,
    )
    if css_match is None:
        raise RuntimeError("Approved GitHub CSS not found")

    patched = live
    for name, rx in (("desktop", DESKTOP), ("mobile", MOBILE)):
        live_nav = one(rx, patched, "live " + name).group()
        approved_nav = one(rx, approved, "source " + name).group()
        old = one(OLD, live_nav, "legacy " + name)
        new = one(APPROVED, approved_nav, "approved " + name)
        if live_nav.count('<a href="#ecosystem">Ecosystem</a>') != 1:
            raise RuntimeError(name + ": ecosystem link missing")
        if live_nav.count('<a href="#mining">Mining</a>') != 1:
            raise RuntimeError(name + ": Mining link missing")
        replacement = live_nav[:old.start()] + new.group() + live_nav[old.end():]
        verify_nav(replacement, name)
        patched = patched.replace(live_nav, replacement, 1)

    head_end = patched.find('</head>')
    insertion = patched.rfind('</style>', 0, head_end)
    if head_end == -1 or insertion == -1:
        raise RuntimeError("Can't safely locate head stylesheet")
    patched = (
        patched[:insertion] + css_match.group() + '\n'
        + patched[insertion:]
    )
    if patched.count('<summary>Wallets ') != 2:
        raise RuntimeError("Dropdown count mismatch")
    if 'min-height:78px' not in patched:
        raise RuntimeError("Original header dimensions changed unexpectedly")
    return patched, True


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--live", type=Path, required=True)
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()

    if not args.live.is_absolute() or args.live.name != "index.html":
        p.error("--live must point to absolute index.html")
    if not args.live.is_file() or args.live.is_symlink():
        p.error("Live homepage not found or points to a symlink")
    if not args.source.is_file():
        p.error("Approved GitHub source missing")

    previous = args.live.read_text(encoding="utf-8")
    approved = args.source.read_text(encoding="utf-8")
    result, changed = prepare(previous, approved)
    if not changed:
        print("Already deployed: compact Wallets dropdown and Explorer button")
        return
    if not args.apply:
        print("Dry run OK: one-row header preserved; three-wallet menu ready")
        return

    backup = args.live.with_name(
        args.live.name + ".before-wallets-dropdown-"
        + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    )
    if backup.exists():
        raise RuntimeError("Backup already exists: " + str(backup))
    attrs = args.live.stat()
    shutil.copy2(args.live, backup)

    fd, temp_path = tempfile.mkstemp(
        dir=args.live.parent, prefix=".feelcoin-wallets-dropdown-"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            out.write(result)
            out.flush()
            os.fsync(out.fileno())
        os.chmod(temp_path, stat.S_IMODE(attrs.st_mode))
        os.chown(temp_path, attrs.st_uid, attrs.st_gid)
        os.replace(temp_path, args.live)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    print("SUCCESS: compact Wallets dropdown deployed (desktop + mobile)")
    print("Backup:", backup)


if __name__ == "__main__":
    main()
