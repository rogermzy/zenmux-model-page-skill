# -*- coding: utf-8 -*-
"""
statgather.py - minimal stdlib-only stub for the vendored lint.py.

Origin: wendy-writes engine commit 175476d, engine/statgather.py.
Changes: the original module pulls in llm / citations / sitemap (live model and network calls) and
is NOT shipped. This file keeps only what lint.py uses: MARKER_RE and RESOLVED_STAT_RE (regexes
copied verbatim), is_usable, and matches_statistics_type. usable_stats() always returns [] and
stats_contract_active() always returns False, so the statistics-page [STAT:id] contract (lint
rules ST1/ST2/ST3) is inactive: it only applies to statistics articles, never to model pages.
"""

import re

STATISTICS_TYPES = {"statistics"}

MARKER_RE = re.compile(r"\[STAT\s*:\s*([^\]]+?)\s*\]")
RESOLVED_STAT_RE = re.compile(r"\*\*[^*\n]{1,80}\*\*\s*\(")


def matches_statistics_type(page_type):
    return (page_type or "").strip().lower() in STATISTICS_TYPES


def is_usable(stat):
    return False


def usable_stats(registry):
    """No stat registry ships with this skill: always empty."""
    return []


def stats_contract_active(page_type, registry):
    """The [STAT:id] contract is never in force here."""
    return False
