#!/usr/bin/env python3
"""Publish only the approved Feelcoin main website HTML."""

from pathlib import Path
import hashlib
import os
import shutil
import tempfile
from datetime import datetime, timezone

ROOT = Path("/var/www/feelcoin.online")
TARGET = ROOT / "index.html"
SOURCE = Path(__file__).resolve().parents[1] / "index.html"

def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    if ROOT.is_symlink() or TARGET.is_symlink():
        raise SystemExit("STOP: Symlinked production path")

    if ROOT.resolve() != Path("/var/www/feelcoin.online"):
        raise SystemExit("STOP: Invalid deployment directory")

    if TARGET.resolve() != Path(
        "/var/www/feelcoin.online/index.html"
    ):
        raise SystemExit("STOP: Invalid deployment target")

    if not SOURCE.is_file() or not TARGET.is_file():
        raise SystemExit("STOP: Missing source or target")

    content = SOURCE.read_text(encoding="utf-8")

    if "<html" not in content.lower():
        raise SystemExit("STOP: Invalid HTML")

    if "OFFICIAL NODE TELEMETRY" in content:
        raise SystemExit("STOP: Node dashboard cannot be published here")

    if sha256(SOURCE) == sha256(TARGET):
        print("Already deployed; no changes")
        return

    stamp = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )
    backup = ROOT / f"index.html.before-publish-{stamp}"

    shutil.copy2(TARGET, backup)

    fd, temporary = tempfile.mkstemp(
        dir=ROOT,
        prefix=".feelcoin-publish-"
    )

    try:
        with os.fdopen(fd, "wb") as out:
            out.write(SOURCE.read_bytes())
            out.flush()
            os.fsync(out.fileno())

        original = TARGET.stat()

        os.chmod(temporary, original.st_mode & 0o777)
        os.chown(temporary, original.st_uid, original.st_gid)

        os.replace(temporary, TARGET)

    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

    print("Published website only:", TARGET)
    print("Backup:", backup)

if __name__ == "__main__":
    main()
