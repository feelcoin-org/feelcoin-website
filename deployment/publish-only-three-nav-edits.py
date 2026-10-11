#!/usr/bin/env python3
"""Apply only three Feelcoin nav edits to the already-restored original header.

Changes:
  - 'Open Wallet' -> 'Web Wallet' (same URL)
  - Desktop + Android links -> one expandable 'Download Wallets' menu
  - Explorer directly after Mining

All existing page content, header layout, typography, and unrelated nav links
remain untouched. A small scoped CSS block styles the new dropdown only.
By default this tool makes a read-only dry run; --apply backs up the HTML.
"""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile

START = "/* FEELCOIN_THREE_NAV_ONLY_START */"
END = "/* FEELCOIN_THREE_NAV_ONLY_END */"
CSS = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
NAV = (
    ("desktop", re.compile(r'<nav class="desktop-nav"[^>]*>.*?</nav>', re.S)),
    ("mobile", re.compile(r'<nav\s+id="mobileNav"[^>]*>.*?</nav>', re.S)),
)
MINING = '<a href="#mining">Mining</a>'
EXPLORER = '<a href="https://explorer.feelcoin.org" target="_blank" rel="noopener noreferrer">Explorer</a>'
WALLET_OLD = re.compile(
    r'<a href="#desktop-wallet">Desktop Wallet</a>\s*'
    r'<a href="#android-wallet">Android Wallet</a>'
)
WALLET_NEW = re.compile(
    r'<details class="fc-wallet-download">\s*'
    r'<summary>Download Wallets</summary>\s*'
    r'<div class="fc-wallet-download-options">.*?</div>\s*</details>', re.S
)
DESKTOP_OPEN = re.compile(
    r'(<a\s+class="nav-launch"\s+href="https://wallet.feelcoin.org">\s*)'
    r'Open Wallet(\s*</a>)'
)
MOBILE_OPEN = re.compile(
    r'(<a href="https://wallet.feelcoin.org">)Open Wallet(</a>)'
)


def single(pattern, value, where):
    hits = list(pattern.finditer(value))
    if len(hits) != 1:
        raise RuntimeError(f"{where}: expected one match, found {len(hits)}")
    return hits[0]


def updated_nav(old, new, kind):
    if MINING not in old or old.count(MINING) != 1:
        raise RuntimeError(kind + ": original Mining anchor missing")
    if old.count('>Explorer</a>') or old.count('class="fc-wallet-download"'):
        raise RuntimeError(kind + ": unexpected pre-existing nav changes")
    pair = single(WALLET_OLD, old, kind + " original wallet links")
    if old.count('>Developers / API</a>') != 1:
        raise RuntimeError(kind + ": original Developers / API label differs")
    new_explorer = single(re.compile(re.escape(EXPLORER)), new, kind + " approved Explorer")
    new_wallet = single(WALLET_NEW, new, kind + " approved wallet dropdown")
    if new.count('>Web Wallet</a>') != 1:
        raise RuntimeError(kind + ": approved Web Wallet label differs")
    if old.count('>Open Wallet</a>') != 1 and kind == "mobile":
        raise RuntimeError(kind + ": original Web Wallet link differs")

    # Modify only the three precisely requested link groups.
    out = old.replace(MINING, MINING + "\n        " + new_explorer.group(), 1)
    out = WALLET_OLD.sub(lambda _: new_wallet.group(), out, count=1)
    open_rx = DESKTOP_OPEN if kind == "desktop" else MOBILE_OPEN
    if len(list(open_rx.finditer(out))) != 1:
        raise RuntimeError(kind + ": Open Wallet label or link differs")
    out = open_rx.sub(lambda m: m.group(1) + "Web Wallet" + m.group(2), out, count=1)

    if out.count(EXPLORER) != 1 or out.count('<summary>Download Wallets</summary>') != 1:
        raise RuntimeError(kind + ": final navigation validation failed")
    if out.count('>Web Wallet</a>') != 1 or out.count('>Developers / API</a>') != 1:
        raise RuntimeError(kind + ": unexpected changed labels")
    if out.index(EXPLORER) < out.index(MINING):
        raise RuntimeError(kind + ": Explorer must follow Mining")
    if out.count('href="#desktop-wallet"') != 1 or out.count('href="#android-wallet"') != 1:
        raise RuntimeError(kind + ": wallet links missing/duplicated")
    return out


def patch(live, approved):
    css = single(CSS, approved, "approved dropdown CSS").group()
    for kind, rx in NAV:
        single(rx, approved, "approved " + kind)
        single(rx, live, "live " + kind)
    already = START in live or END in live
    if already:
        if START not in live or END not in live or live.count(START) != 1:
            raise RuntimeError("Partial or duplicate dropdown CSS detected")
        for kind, rx in NAV:
            nav = single(rx, live, "live " + kind).group()
            if (nav.count(EXPLORER) != 1
                    or nav.count('<summary>Download Wallets</summary>') != 1
                    or nav.count('>Web Wallet</a>') != 1):
                raise RuntimeError(kind + ": dropdown partially deployed")
        return live, False

    if 'FEELCOIN_SINGLE_ROW_WALLET_MENU_V1_START' in live or 'FEELCOIN_NAV_WALLETS_V2_START' in live:
        raise RuntimeError("An older redesigned header is deployed; restore original first")
    if 'min-height:78px;' not in live:
        raise RuntimeError("Expected original header size not found")
    result = live
    for kind, rx in NAV:
        current = single(rx, result, "live " + kind).group()
        target = single(rx, approved, "approved " + kind).group()
        replacement = updated_nav(current, target, kind)
        result = result.replace(current, replacement, 1)

    end_head = result.find("</head>")
    end_style = result.rfind("</style>", 0, end_head)
    if end_head < 0 or end_style < 0:
        raise RuntimeError("Cannot locate the website header CSS")
    result = result[:end_style] + css + "\n" + result[end_style:]
    if result.count(START) != 1 or result.count('<summary>Download Wallets</summary>') != 2:
        raise RuntimeError("Post-patch verification failed")
    return result, result != live


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--source", type=Path, required=True)
    cli.add_argument("--live", type=Path, required=True)
    cli.add_argument("--apply", action="store_true")
    args = cli.parse_args()
    file = args.live
    if not file.is_absolute() or file.name != "index.html":
        cli.error("--live must be an absolute index.html file")
    if file.is_symlink() or not file.is_file() or not args.source.is_file():
        cli.error("Files missing or production file is a symlink")

    before = file.read_text(encoding="utf-8")
    approved = args.source.read_text(encoding="utf-8")
    after, changed = patch(before, approved)
    if not changed:
        print("Already applied: three requested header changes")
        return
    if not args.apply:
        print("Dry run OK: only Open Wallet label, two-wallet dropdown and Explorer button")
        print("Original header and all other website content are preserved")
        return

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup = file.with_name(file.name + ".before-three-nav-updates-" + stamp)
    if backup.exists():
        raise RuntimeError("Backup path already exists")
    original_meta = file.stat()
    shutil.copy2(file, backup)
    fd, temporary = tempfile.mkstemp(dir=file.parent, prefix=".feelcoin-three-nav-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(after)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, stat.S_IMODE(original_meta.st_mode))
        os.chown(temporary, original_meta.st_uid, original_meta.st_gid)
        os.replace(temporary, file)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print("SUCCESS: three navigation changes applied")
    print("Backup:", backup)


if __name__ == "__main__":
    main()
