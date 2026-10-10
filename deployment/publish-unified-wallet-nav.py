#!/usr/bin/env python3
"""Safely publish the Feelcoin website's unified wallet-navigation update.

The approved GitHub index.html supplies the nav segment and scoped CSS; the
existing production homepage supplies everything else. Dry run by default.
"""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile

START = "/* FEELCOIN_NAV_WALLETS_V2_START"
END = "/* FEELCOIN_NAV_WALLETS_V2_END */"
DESKTOP = re.compile(r'<nav class="desktop-nav"[^>]*>.*?</nav>', re.S)
MOBILE = re.compile(r'<nav\s+id="mobileNav"[^>]*>.*?</nav>', re.S)
OLD = re.compile(
    r'<a href="#ecosystem">Ecosystem</a>.*?'
    r'<a href="https://explorer\.feelcoin\.org"[^>]*>Explorer</a>', re.S
)
NEW = re.compile(
    r'<a href="#ecosystem">Ecosystem</a>.*?'
    r'<a href="https://api\.feelcoin\.org/docs"[^>]*>Developers / API</a>', re.S
)
API = "https://api.feelcoin.org/docs"


def exactly_one(pattern, text, label):
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise RuntimeError(f"{label}: expected one matching navigation block; found {len(matches)}")
    return matches[0]


def apply_patch(live, source):
    approved_styles = re.search(
        re.escape(START) + r'.*?' + re.escape(END), source, re.S
    )
    if approved_styles is None:
        raise RuntimeError("Missing approved styles in GitHub source")
    if START in live or 'class="fc-wallets-menu' in live:
        if (
            START in live and live.count('class="fc-wallets-menu') == 2
            and live.count('>Pool</a>') == 2
            and live.count('>Download Wallets</summary>') == 2
        ):
            return live, False
        raise RuntimeError("Partial or unexpected nav update detected; refusing edit")

    new_live = live
    for pattern, name in ((DESKTOP, "desktop"), (MOBILE, "mobile")):
        source_nav = exactly_one(pattern, source, "source " + name).group()
        live_nav = exactly_one(pattern, new_live, "live " + name).group()
        source_fragment = exactly_one(NEW, source_nav, "approved " + name).group()
        old_match = exactly_one(OLD, live_nav, "existing " + name)

        # Fail closed if other site navigation differs from the expected version.
        for field in (
            '<a href="#mining">Mining</a>',
            '<a href="#desktop-wallet">Desktop Wallet</a>',
            '<a href="#android-wallet">Android Wallet</a>',
            '>Developers / API</a>',
        ):
            if live_nav.count(field) != 1:
                raise RuntimeError(f"{name}: unexpected nav field: {field}")

        expected_after = (
            '<a href="https://github.com/feelcoin-org"'
            if name == "desktop"
            else '<a href="https://x.com/feelcoin_org"'
        )
        if expected_after not in live_nav:
            raise RuntimeError(f"{name}: rest of navigation changed; refusing edit")

        updated_nav = (
            live_nav[:old_match.start()] + source_fragment
            + live_nav[old_match.end():]
        )
        if updated_nav.count('>Explorer</a>') != 1 or updated_nav.count('>Pool</a>') != 1:
            raise RuntimeError(f"{name}: Explorer/Pool duplication")
        if updated_nav.count('>Paper Wallet</a>') != 1:
            raise RuntimeError(f"{name}: Paper Wallet missing")
        if updated_nav.count('>Download Wallets</summary>') != 1:
            raise RuntimeError(f"{name}: Download Wallets not present")
        new_live = new_live.replace(live_nav, updated_nav, 1)

    head = new_live.find("</head>")
    css_insert = new_live.rfind("</style>", 0, head)
    if head < 0 or css_insert < 0:
        raise RuntimeError("Cannot find stylesheet before closing head")
    new_live = (
        new_live[:css_insert] + approved_styles.group() + "\n"
        + new_live[css_insert:]
    )
    if (new_live.count('>Download Wallets</summary>') != 2
            or new_live.count('>Pool</a>') != 2
            or new_live.count('>Paper Wallet</a>') != 2):
        raise RuntimeError("Final nav validation failed")
    return new_live, True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True,
                        help="Approved index.html from origin/main")
    parser.add_argument("--live", type=Path, required=True,
                        help="Absolute path to currently deployed index.html")
    parser.add_argument("--apply", action="store_true",
                        help="Create backup and modify live homepage")
    args = parser.parse_args()

    path = args.live
    if not path.is_absolute() or path.name != "index.html":
        parser.error("--live must be an absolute index.html path")
    if not path.is_file() or path.is_symlink() or not args.source.is_file():
        parser.error("Both files must exist; live file cannot be a symlink")
    original = path.read_text(encoding="utf-8")
    approved = args.source.read_text(encoding="utf-8")
    updated, changed = apply_patch(original, approved)
    if not changed:
        print("Already deployed: Wallets dropdown, Explorer, Pool and Paper Wallet")
        return
    if not args.apply:
        print("Dry run OK: Explorer → Pool → Download Wallets → Paper Wallet")
        print("The rest of the live website will be preserved.")
        return

    backup = path.with_name(
        path.name + ".before-unified-wallet-nav-"
        + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    )
    if backup.exists():
        raise RuntimeError("Backup already exists: " + str(backup))
    meta = path.stat()
    shutil.copy2(path, backup)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".feelcoin-nav-wallets-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(updated)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, stat.S_IMODE(meta.st_mode))
        os.chown(tmp, meta.st_uid, meta.st_gid)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    print("SUCCESS: updated homepage desktop and mobile menus")
    print("Backup:", backup)


if __name__ == "__main__":
    main()
