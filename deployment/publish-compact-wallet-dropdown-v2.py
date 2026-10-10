#!/usr/bin/env python3
"""Safely install Feelcoin's compact 3-wallet menu from approved GitHub HTML.

Supports both the old single-row and the previously deployed two-row navbar.
This updates only desktop/mobile nav groups and the clearly marked nav CSS.
Dry-run by default; --apply creates a backup and replaces the live file atomically.
"""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile

NEW_START = "/* FEELCOIN_SINGLE_ROW_WALLET_MENU_V1_START */"
NEW_END = "/* FEELCOIN_SINGLE_ROW_WALLET_MENU_V1_END */"
OLD_START = "/* FEELCOIN_NAV_WALLETS_V2_START"
OLD_END = "/* FEELCOIN_NAV_WALLETS_V2_END */"

NAV = {
    "desktop": re.compile(r'<nav class="desktop-nav"[^>]*>.*?</nav>', re.S),
    "mobile": re.compile(r'<nav\s+id="mobileNav"[^>]*>.*?</nav>', re.S),
}
TAIL = {
    "desktop": re.compile(r'<a\s+href="https://github\.com/feelcoin-org"'),
    "mobile": re.compile(r'<a\s+href="https://x\.com/feelcoin_org"'),
}
ECOSYSTEM = '<a href="#ecosystem">Ecosystem</a>'
NEW_STYLE = re.compile(re.escape(NEW_START) + r'.*?' + re.escape(NEW_END), re.S)
OLD_STYLE = re.compile(re.escape(OLD_START) + r'.*?' + re.escape(OLD_END) + r'\s*', re.S)


def single(rx, value, what):
    matches = list(rx.finditer(value))
    if len(matches) != 1:
        raise RuntimeError(f"{what}: expected exactly one match, found {len(matches)}")
    return matches[0]


def section(nav, name):
    if nav.count(ECOSYSTEM) != 1:
        raise RuntimeError(f"{name}: Ecosystem button is missing or duplicated")
    start = nav.index(ECOSYSTEM)
    tail = single(TAIL[name], nav, name + " social-nav boundary")
    if tail.start() <= start:
        raise RuntimeError(name + ": unexpected nav order")
    return start, tail.start()


def validate_new(nav, name):
    for href in (
        'href="#ecosystem"',
        'href="#mining"',
        'href="https://explorer.feelcoin.org"',
        'href="#desktop-wallet"',
        'href="#android-wallet"',
        'href="https://paper.feelcoin.org"',
        'href="https://api.feelcoin.org/docs"',
    ):
        if nav.count(href) != 1:
            raise RuntimeError(f"{name}: expected one {href}")
    if nav.count('<summary>Wallets ') != 1:
        raise RuntimeError(name + ": Wallets menu missing")
    for old in ('>Desktop Wallet</a>', '>Android Wallet</a>',
                '<summary>Download Wallets'):
        if old in nav:
            raise RuntimeError(name + ": old wallet links still present")
    if nav.count('>API Docs</a>') != 1:
        raise RuntimeError(name + ": API Docs label missing")


def version_of(nav, name):
    new = '<summary>Wallets ' in nav
    old_one = ('<a href="#desktop-wallet">Desktop Wallet</a>' in nav
               and '<a href="#android-wallet">Android Wallet</a>' in nav)
    old_two = ('<summary>Download Wallets</summary>' in nav
               and 'fc-wallets-menu' in nav)
    if sum(bool(v) for v in (new, old_one, old_two)) != 1:
        raise RuntimeError(name + ": unknown/mixed navigation; refusing to guess")
    if new:
        validate_new(nav, name)
        return "already-new"
    if nav.count(ECOSYSTEM) != 1:
        raise RuntimeError(name + ": Ecosystem button missing")
    if old_one:
        # Explorer may not exist yet in the deployed single-row header.
        for link in ('href="#mining"', 'href="#desktop-wallet"',
                     'href="#android-wallet"', 'href="#docs"',
                     'href="https://api.feelcoin.org/docs"'):
            if nav.count(link) != 1:
                raise RuntimeError(
                    f"{name}: expected one {link}; found {nav.count(link)}"
                )
        if nav.count('href="https://explorer.feelcoin.org"') > 1:
            raise RuntimeError(name + ": duplicate legacy Explorer links")
        return "original"
    for s in ('href="https://pool.feelcoin.org"',
              'href="https://paper.feelcoin.org"',
              'href="https://explorer.feelcoin.org"'):
        if nav.count(s) != 1:
            raise RuntimeError(name + ": legacy two-row links changed")
    return "two-row"


def patch(live, approved):
    css = single(NEW_STYLE, approved, "approved wallet CSS").group()
    existing_new_css = NEW_START in live or NEW_END in live
    if existing_new_css:
        if NEW_START not in live or NEW_END not in live:
            raise RuntimeError("Partial compact wallet CSS detected")
        for name, rx in NAV.items():
            validate_new(single(rx, live, name).group(), name)
        if OLD_START in live or OLD_END in live:
            raise RuntimeError("Conflicting old two-row CSS detected")
        return live, False, "already-new"

    updated = live
    versions = []
    for name, rx in NAV.items():
        current = single(rx, updated, "live " + name).group()
        desired = single(rx, approved, "GitHub " + name).group()
        v = version_of(current, name)
        if v == "already-new":
            raise RuntimeError("New wallet menu exists without approved CSS")
        versions.append(f"{name}={v}")
        validate_new(desired, name)

        old_start, old_end = section(current, name)
        new_start, new_end = section(desired, name)

        # Only remove a legacy About link if it appears before Ecosystem.
        prefix = current[:old_start]
        prefix = re.sub(
            r'^[ \t]*<a href="#about">About</a>[ \t]*\r?\n',
            '', prefix, flags=re.M,
        )
        # Preserve legacy secondary anchors (such as Economics) that
        # precede Ecosystem on production mobile navigation.
        # The prefix necessarily starts with the opening <nav> tag.
        # Reject nested nav/menu markup, not the normal outer <nav>.
        if '<details' in prefix or prefix.count('<nav') != 1:
            raise RuntimeError(name + ": unexpected prefix structure")

        # Reject unfamiliar links within the group that is replaced.
        known_links = {
            "#ecosystem", "#mining", "#desktop-wallet", "#android-wallet",
            "#docs", "https://api.feelcoin.org/docs",
            "https://explorer.feelcoin.org", "https://pool.feelcoin.org",
            "https://paper.feelcoin.org",
        }
        old_group = current[old_start:old_end]
        hrefs = re.findall(r'<a\b[^>]*\bhref="([^"]+)"', old_group)
        extra = sorted(set(hrefs) - known_links)
        if extra:
            raise RuntimeError(f"{name}: unfamiliar links within primary nav: {extra}")

        next_nav = (
            prefix + desired[new_start:new_end]
            + current[old_end:]
        )
        validate_new(next_nav, name)
        updated = updated.replace(current, next_nav, 1)

    if OLD_START in updated or OLD_END in updated:
        old_css = single(OLD_STYLE, updated, "original two-row CSS")
        updated = updated[:old_css.start()] + updated[old_css.end():]
    head = updated.find("</head>")
    pos = updated.rfind("</style>", 0, head)
    if head < 0 or pos < 0:
        raise RuntimeError("Unable to safely locate site header stylesheet")
    updated = updated[:pos] + css + "\n" + updated[pos:]

    for name, rx in NAV.items():
        validate_new(single(rx, updated, name).group(), name)
    if updated.count(NEW_START) != 1 or OLD_START in updated:
        raise RuntimeError("Final CSS verification failed")
    if 'min-height:78px;' not in updated:
        raise RuntimeError("Expected original header height not found")
    return updated, True, ", ".join(versions)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--live", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.live.is_absolute() or args.live.name != "index.html":
        parser.error("--live must be absolute index.html")
    if not args.live.is_file() or args.live.is_symlink() or not args.source.is_file():
        parser.error("Source and live files must exist; no live symlinks")

    original = args.live.read_text(encoding="utf-8")
    approved = args.source.read_text(encoding="utf-8")
    result, changed, found = patch(original, approved)
    if not changed:
        print("Already deployed: compact Wallets menu on desktop and mobile")
        return
    if not args.apply:
        print("Dry run OK — current navigation: " + found)
        print("Ready to publish compact one-row header; homepage content preserved")
        return

    backup = args.live.with_name(
        args.live.name + ".before-compact-wallets-"
        + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    )
    if backup.exists():
        raise RuntimeError("Backup already exists: " + str(backup))
    metadata = args.live.stat()
    shutil.copy2(args.live, backup)
    fd, tmp = tempfile.mkstemp(dir=args.live.parent, prefix=".feelcoin-nav-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(result)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(tmp, stat.S_IMODE(metadata.st_mode))
        os.chown(tmp, metadata.st_uid, metadata.st_gid)
        os.replace(tmp, args.live)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    print("SUCCESS — compact Wallets dropdown published on desktop and mobile")
    print("Previous homepage backup: " + str(backup))


if __name__ == "__main__":
    main()
