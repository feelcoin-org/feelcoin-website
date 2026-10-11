#!/usr/bin/env python3
"""Patch only Pool header stacking and larger nav fonts; never touches mining APIs.

Dry-run by default. --apply backs up the existing deployed static HTML.
"""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import stat
import tempfile

START = "/* FEELCOIN_POOL_DROPDOWN_LAYER_TYPE_V1_START */"
END = "/* FEELCOIN_POOL_DROPDOWN_LAYER_TYPE_V1_END */"
CSS = """/* FEELCOIN_POOL_DROPDOWN_LAYER_TYPE_V1_START */
/* The header must establish a higher stacking level than the hero cards. */
.shell > .topbar {
  position:relative !important;
  z-index:1000 !important;
  overflow:visible !important;
}
.topbar > nav.nav {
  overflow:visible;
}
.topbar > nav.nav .fc-pool-downloads[open] {
  z-index:1100;
}
.topbar > nav.nav .fc-pool-download-options {
  z-index:1200;
}
@media(min-width:1281px) {
  .topbar > nav.nav > a {
    font-size:14px;
    padding:9px 6px;
  }
  .topbar > nav.nav .fc-pool-downloads > summary {
    font-size:14px;
    padding:9px 6px;
  }
  .topbar .fc-pool-social-right a {
    font-size:14px;
  }
}
/* FEELCOIN_POOL_DROPDOWN_LAYER_TYPE_V1_END */"""


def patch(live):
    if START in live or END in live:
        if live.count(START) == live.count(END) == 1:
            return live, False
        raise RuntimeError("Partial or repeated CSS patch; refusing edit")

    required = (
        '<header class="topbar">',
        '<main id="dashboard">',
        'FEELCOIN_POOL_NAV_FOOTER_V1_START',
        'class="fc-pool-social-right"',
        'class="fc-pool-download-options"',
    )
    for name in required:
        if name not in live:
            raise RuntimeError(f"Expected Pool UI marker not found: {name}")
    if live.count('<summary>Downloads ') != 2:
        raise RuntimeError("Expected one Downloads menu in desktop and mobile navigation")

    head_end = live.find("</head>")
    style_end = live.rfind("</style>", 0, head_end)
    if head_end == -1 or style_end == -1:
        raise RuntimeError("Unable to locate header style block")
    result = live[:style_end] + CSS + "\n" + live[style_end:]
    if result.count(START) != 1 or result.count(END) != 1:
        raise RuntimeError("Post-edit marker validation failed")
    return result, True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    target = args.live
    if not target.is_absolute() or target.name != "index.html":
        parser.error("--live must be an absolute index.html path")
    if target.is_symlink() or not target.is_file():
        parser.error("Live file missing or symlinked")

    original = target.read_text(encoding="utf-8")
    updated, changed = patch(original)
    if not changed:
        print("Already deployed: Downloads is layered above hero, nav text 14px")
        return
    if not args.apply:
        print("Dry run OK: Downloads layering + 14px desktop nav text only")
        print("Mining, payouts, page layout and footer remain unchanged")
        return

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup = target.with_name(target.name + ".before-pool-menu-layer-" + stamp)
    if backup.exists():
        raise RuntimeError(f"Backup exists: {backup}")
    mode = target.stat()
    shutil.copy2(target, backup)
    fd, temporary = tempfile.mkstemp(dir=target.parent, prefix=".feelcoin-pool-menu-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(updated)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, stat.S_IMODE(mode.st_mode))
        os.chown(temporary, mode.st_uid, mode.st_gid)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

    print("SUCCESS: Pool Downloads layered above hero; navigation text 14px")
    print("Backup:", backup)


if __name__ == "__main__":
    main()
