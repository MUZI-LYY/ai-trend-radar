#!/usr/bin/env python3
"""Restore canonical working files from tracked verified data on clean checkouts."""
from pack_history import SOURCE as HISTORY, restore as restore_history
from pack_latest import LATEST, restore as restore_latest


if __name__ == '__main__':
    if not LATEST.exists():
        restore_latest()
    if not HISTORY.exists():
        restore_history()
