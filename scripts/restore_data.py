#!/usr/bin/env python3
"""Restore canonical working files from tracked verified data on clean checkouts."""
import json

from pack_history import MANIFEST as HISTORY_MANIFEST, digest as history_digest
from pack_history import SOURCE as HISTORY, restore as restore_history
from pack_latest import LATEST, SHARDS_DIR, restore as restore_latest, sha256


if __name__ == '__main__':
    latest_sha = json.loads((SHARDS_DIR / 'manifest.json').read_text())['sourceSha256']
    history_sha = json.loads(HISTORY_MANIFEST.read_text())['sourceSha256']
    if not LATEST.exists() or sha256(LATEST) != latest_sha:
        restore_latest()
    if not HISTORY.exists() or history_digest(HISTORY.read_bytes()) != history_sha:
        restore_history()
