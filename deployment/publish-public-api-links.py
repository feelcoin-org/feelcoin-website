#!/usr/bin/env python3
"""Apply public API discovery links to the *live* Feelcoin homepage only.

Intentionally does not copy the entire website repository index.html: the
production file may contain independent edits. Fails closed if anchors change.
"""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import stat
import tempfile


API_DOCS = "https://api.feelcoin.org/docs"


def replace_checked(html, needle, replacement, required=1):
    actual = html.count(needle)
    if actual != required:
        raise RuntimeError(
            f"Expected {required} occurrence(s) of {needle[:75]!r}; found {actual}. "
            "Live homepage has changed; no modifications made."
        )
    return html.replace(needle, replacement)


def add_links(html):
    if API_DOCS in html:
        required = (
            "OFFICIAL FEELCOIN PUBLIC API",
            "Feelcoin Public API",
            "Developer API · v1",
            "Developer API",
            "Developers / API",
        )
        # Do not touch a partially updated homepage.
        if all(x in html for x in required) and html.count(API_DOCS) == 5:
            return html, False
        raise RuntimeError("Some API links already exist; no changes made.")

    nav = '<a href="#docs">Documentation</a>'
    html = replace_checked(
        html, nav,
        nav + '\n        <a href="' + API_DOCS
        + '" target="_blank" rel="noopener noreferrer" '
        + 'aria-label="Developer API documentation">Developers / API</a>',
        required=2,
    )

    eco = '      <a class="eco-card"\n         href="https://github.com/feelcoin-org"'
    eco_card = '''      <!-- OFFICIAL FEELCOIN PUBLIC API -->
      <a class="eco-card"
         href="https://api.feelcoin.org/docs"
         target="_blank"
         rel="noopener noreferrer">

        <div class="eco-index">PUBLIC / DEVELOPERS</div>

        <h3>Feelcoin Public API</h3>

        <p>
          Read-only blockchain, emission and mining statistics
          for exchanges, mining directories and developers.
        </p>

        <div class="eco-link">
          api.feelcoin.org/docs →
        </div>

      </a>

'''
    html = replace_checked(html, eco, eco_card + eco)

    docs = '      <div class="doc-stack">'
    docs_card = '''
        <a class="glass doc-small"
           href="https://api.feelcoin.org/docs"
           target="_blank"
           rel="noopener noreferrer">

          <strong>Developer API · v1</strong>

          <span>
            Public JSON endpoints, OpenAPI schema and integration reference
            for exchanges, mining directories and applications.
          </span>

        </a>
'''
    html = replace_checked(html, docs, docs + '\n' + docs_card)

    footer = '      <nav class="footer-links">'
    footer_link = '''
        <a href="https://api.feelcoin.org/docs" target="_blank" rel="noopener noreferrer">
          Developer API
        </a>
'''
    html = replace_checked(html, footer, footer + '\n' + footer_link)

    if html.count(API_DOCS) != 5:
        raise RuntimeError("Internal validation failed; no changes made.")
    return html, True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("index_html", type=Path, help="Absolute path of live index.html")
    parser.add_argument("--apply", action="store_true", help="Back up and modify live file")
    args = parser.parse_args()
    target = args.index_html
    if not target.is_absolute() or target.name != "index.html" or not target.is_file():
        parser.error("Supply an existing absolute index.html path")
    original = target.read_text(encoding="utf-8")
    updated, changed = add_links(original)
    if not changed:
        print("Already installed: all five API links present; no changes.")
        return
    if not args.apply:
        print("Dry run OK: five API links can be added safely without replacing other content.")
        print("Repeat with --apply to make a timestamped backup and update the homepage.")
        return

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup = target.with_name(f"{target.name}.before-public-api-{timestamp}")
    if backup.exists():
        raise RuntimeError(f"Backup already exists: {backup}")
    metadata = target.stat()
    shutil.copy2(target, backup)
    fd, temporary = tempfile.mkstemp(prefix=".feelcoin-public-api-", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(updated)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temporary, stat.S_IMODE(metadata.st_mode))
        os.chown(temporary, metadata.st_uid, metadata.st_gid)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print("Updated live homepage with five API documentation links.")
    print(f"Backup: {backup}")
    print("Verify the HTTPS homepage before considering the task complete.")


if __name__ == "__main__":
    main()
