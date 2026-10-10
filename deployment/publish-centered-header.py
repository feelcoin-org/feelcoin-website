#!/usr/bin/env python3
"""Deploy only the Feelcoin centered navigation styling, keeping the original header.

Reads approved CSS from the website GitHub index.html. Read-only by default.
--apply creates a timestamped backup and atomically edits the production file.
"""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile

START = "/* FEELCOIN_CENTER_NAV_ARROW_V1_START */"
END = "/* FEELCOIN_CENTER_NAV_ARROW_V1_END */"
REGION = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)


def exactly_one(source, what):
    hits = list(REGION.finditer(source))
    if len(hits) != 1:
        raise RuntimeError(f"{what}: expected one centered-nav CSS section; found {len(hits)}")
    return hits[0]


def patch(live, source):
    approved = exactly_one(source, "Approved GitHub HTML").group()
    for label, html in (("GitHub", source), ("Production", live)):
        if html.count("<summary>Wallets ") != 2:
            raise RuntimeError(f"{label}: expected 2 Wallets menus, desktop and mobile")
        if "FEELCOIN_SINGLE_ROW_WALLET_MENU_V1_START" not in html:
            raise RuntimeError(f"{label}: compact one-row wallet CSS not found")
        if "FEELCOIN_NAV_WALLETS_V2_START" in html:
            raise RuntimeError(f"{label}: obsolete two-row header detected")
        if "min-height:78px;" not in html:
            raise RuntimeError(f"{label}: 78px original header size missing")
    if "font-size:13px;" not in approved:
        raise RuntimeError("Approved CSS missing original 13px font size")

    count_start, count_end = live.count(START), live.count(END)
    if count_start != count_end or count_start > 1:
        raise RuntimeError("Partial or duplicated centered-nav CSS; no change")

    if count_start == 1:
        current = exactly_one(live, "Production HTML")
        updated = live[:current.start()] + approved + live[current.end():]
    else:
        closing_head = live.find("</head>")
        style_end = live.rfind("</style>", 0, closing_head)
        if closing_head < 0 or style_end < 0:
            raise RuntimeError("Unable to locate the website header stylesheet")
        updated = live[:style_end] + approved + "\n\n" + live[style_end:]
    if updated.count(START) != 1 or updated.count(END) != 1:
        raise RuntimeError("Final CSS count validation failed")
    return updated, updated != live


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--live", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    live_file = args.live
    if not live_file.is_absolute() or live_file.name != "index.html":
        parser.error("--live must be an absolute index.html path")
    if not live_file.is_file() or live_file.is_symlink() or not args.source.is_file():
        parser.error("Files missing or production path is a symlink")
    original = live_file.read_text(encoding="utf-8")
    source = args.source.read_text(encoding="utf-8")
    updated, changed = patch(original, source)
    if not changed:
        print("Already deployed: centered 13px navigation and aligned Wallets arrow")
        return
    if not args.apply:
        print("Dry run OK: center links, restore 13px text, align Wallets caret")
        print("Original 78px single-row header and all page content preserved")
        return

    backup = live_file.with_name(
        live_file.name + ".before-centered-header-"
        + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    )
    if backup.exists():
        raise RuntimeError("Refusing to overwrite existing backup " + str(backup))
    file_info = live_file.stat()
    shutil.copy2(live_file, backup)
    fd, temporary = tempfile.mkstemp(
        dir=live_file.parent, prefix=".feelcoin-center-header-"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(updated)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, stat.S_IMODE(file_info.st_mode))
        os.chown(temporary, file_info.st_uid, file_info.st_gid)
        os.replace(temporary, live_file)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print("SUCCESS: centered, original-size header text and Wallets arrow aligned")
    print("Backup:", backup)


if __name__ == "__main__":
    main()
