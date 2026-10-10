#!/usr/bin/env python3
"""Update Feelcoin homepage navigation: keep Ecosystem, remove About and Miner.

Supports live homepage before or after the prior About/Ecosystem cleanup.
Dry run by default, --apply backs up and atomically replaces only homepage HTML.
"""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile

DESKTOP = '<nav class="desktop-nav" aria-label="Main navigation">'
MOBILE = '<nav\n      id="mobileNav"'
MINER_BLOCK = re.compile(
    r'^[ \t]*<!-- FEELCOIN MINER NAV -->[ \t]*\r?\n'
    r'[ \t]*<a[ \t]*\r?\n'
    r'[ \t]*href="https://github\.com/feelcoin-org/feelcoin-miner/releases/latest"[ \t]*\r?\n'
    r'[ \t]*target="_blank"[ \t]*\r?\n'
    r'[ \t]*rel="noopener noreferrer">[ \t]*\r?\n'
    r'[ \t]*Miner[ \t]*\r?\n'
    r'[ \t]*</a>[ \t]*\r?\n',
    re.MULTILINE,
)


def update(html):
    original = html
    for name, opener in (("desktop", DESKTOP), ("mobile", MOBILE)):
        if html.count(opener) != 1:
            raise RuntimeError(f"Unexpected {name} navigation; aborting")
        start = html.index(opener)
        end = html.find("</nav>", start)
        if end < 0:
            raise RuntimeError(f"{name} navigation not closed")
        nav = html[start:end]
        nav = re.sub(
            r'^[ \t]*<a href="#about">About</a>[ \t]*\r?\n', '',
            nav, flags=re.MULTILINE,
        )
        if nav.count('<a href="#mining">Mining</a>') != 1:
            raise RuntimeError(f"{name} Mining button changed; aborting")
        ec = '<a href="#ecosystem">Ecosystem</a>'
        if nav.count(ec) == 0:
            nav = re.sub(
                r'^([ \t]*)(<a href="#mining">Mining</a>)',
                lambda m: m.group(1) + ec + '\n' + m.group(1) + m.group(2),
                nav, count=1, flags=re.MULTILINE,
            )
        elif nav.count(ec) != 1:
            raise RuntimeError(f"{name} duplicate Ecosystem buttons")

        nav, removed = MINER_BLOCK.subn('', nav)
        if removed > 1:
            raise RuntimeError(f"{name} unexpected duplicate Miner buttons")
        if removed == 0 and ('FEELCOIN MINER NAV' in nav or re.search(
                r'<a\b[^>]*>\s*Miner\s*</a>', nav, re.DOTALL)):
            raise RuntimeError(f"{name} Miner markup differs; aborting")

        if nav.count(ec) != 1 or '<a href="#about">' in nav:
            raise RuntimeError(f"{name} navigation validation failed")
        html = html[:start] + nav + html[end:]
    if '<section id="ecosystem"' not in html or 'id="about"' not in html:
        raise RuntimeError("Main page sections unexpectedly missing")
    return html, (html != original)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('index_html', type=Path)
    p.add_argument('--apply', action='store_true')
    args = p.parse_args()
    path = args.index_html
    if not path.is_absolute() or path.name != "index.html":
        p.error("Provide the absolute path of the homepage index.html")
    if not path.is_file() or path.is_symlink():
        p.error("Expected a regular non-symlink file")
    original = path.read_text(encoding="utf-8")
    updated, changed = update(original)
    if not changed:
        print("Already correct: Ecosystem retained, About and Miner hidden in navigation")
        return
    if not args.apply:
        print("Dry run OK: Ecosystem stays; About and Miner removed from both menus")
        return

    backup = path.with_name(
        path.name + ".before-nav-ecosystem-no-miner-"
        + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    )
    if backup.exists():
        raise RuntimeError("Backup path exists: " + str(backup))
    meta = path.stat()
    shutil.copy2(path, backup)
    fd, tmp = tempfile.mkstemp(prefix=".feelcoin-nav-", dir=path.parent)
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
    print("SUCCESS: updated both desktop and mobile navigation")
    print("Backup:", backup)


if __name__ == "__main__":
    main()
