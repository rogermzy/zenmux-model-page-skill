#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Vendored from the wendy-writes engine, commit 175476d (engine/langutil.py). Unmodified except for
# this header and a `from __future__ import annotations` line (Python 3.9 compatibility).
"""
langutil.py — shared language helpers so every stage handles zh/ja/ko/es the same way.
Stdlib only. Extracted 2026-07-04 after a multilingual review found each stage had rolled its
own (English-only) sentence split, language default, and word-boundary find.
"""

from __future__ import annotations   # vendored edit: Python 3.9 compatibility for `X | None` annotations
import os
import re
import tempfile
from pathlib import Path

# canonical 2-letter code. Accepts "EN", "zh-CN", "zh_Hant", "ja-JP" → "en"/"zh"/"ja".
_LANG_ALIASES = {"zh-cn": "zh", "zh-hans": "zh", "zh-hant": "zh", "zh-tw": "zh", "zh-hk": "zh",
                 "cmn": "zh", "en-us": "en", "en-gb": "en", "en-au": "en"}

# Languages the pipeline fully supports (writing, translate, article creation). Single source of
# truth — app/main.py's article-language whitelist and pipeline.py's translate-target whitelist
# both import this instead of carrying their own copy. fr/nl (etc.) are a documented follow-on:
# extend this tuple + _LANG_NAMES/_LANG_ALIASES/serp_language_code/draft._FAQ_HEADING/
# atglance._ATG_I18N together, never just one of them.
SUPPORTED_LANGS = ("en", "zh", "ja", "ko", "es")


def atomic_write_text(path, text: str) -> None:
    """Publish text with an atomic same-directory replace."""
    target = Path(path)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp_name, target)
    finally:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass


def norm_lang(value, default: str = "en") -> str:
    v = (value or "").strip().lower().replace("_", "-")
    if not v:
        return default
    if v in _LANG_ALIASES:
        return _LANG_ALIASES[v]
    return v.split("-")[0]                       # ja-JP → ja, es-ES → es


def is_cjk_lang(lang: str) -> bool:
    return norm_lang(lang) in ("zh", "ja", "ko")


# "Key Takeaways" block heading per article language (tldr.py writes it). English stays the fallback
# for languages without a native entry. KT_HEADING_ALT is the regex body of EVERY name the block can
# carry — the engines that must leave the block alone (A4 exemption, autopilot, at-a-glance placement,
# draft's never-rewrite list) match on it, so adding a language here means adding it there too.
_KT_HEADINGS = {"zh": "核心要点", "ja": "要点まとめ", "ko": "핵심 요약"}
KT_HEADING_ALT = r"key\s*takeaways|核心要点|要点速览|要点总结|要点まとめ|핵심\s*요약"


def kt_heading(lang) -> str:
    return _KT_HEADINGS.get(norm_lang(lang), "Key Takeaways")


# native language name for LLM prompts ("write in 简体中文") — single source; brief.py /
# factcheck.py / product_research.py previously each inlined a copy of this dict, and a
# language added to one silently prompted the others in English
_LANG_NAMES = {"zh": "简体中文", "ja": "日本語", "ko": "한국어", "es": "español", "en": "English"}


def lang_name(lang: str, default: str = "English") -> str:
    return _LANG_NAMES.get(norm_lang(lang), default)


# DataForSEO Google-Ads / SERP language_code for a normalized article language. Google's zh code is
# "zh" for Ads but the SERP endpoint accepts "zh-CN"; callers pass the article language and we map.
def serp_language_code(lang: str) -> str:
    return {"zh": "zh-CN", "ja": "ja", "ko": "ko", "es": "es", "en": "en"}.get(norm_lang(lang), norm_lang(lang))


# HTTP Accept-Language for crawling SERP pages in the article's language. English keeps the bare "en"
# the crawlers always sent; other languages prefer their own, English as the fallback quality.
_ACCEPT_LANGUAGE = {"zh": "zh-CN,zh;q=0.9,en;q=0.5", "ja": "ja,en;q=0.5", "ko": "ko,en;q=0.5",
                    "es": "es,en;q=0.5"}


def accept_language(lang) -> str:
    return _ACCEPT_LANGUAGE.get(norm_lang(lang), "en")


_SENT_SPLIT = re.compile(r"(?<=[。！？!?\.])\s*|(?<=[；;])\s+")
# Latin terminators need trailing space (so "Flux.2" / "No. 1" don't over-split); CJK 。！？；don't.
_LATIN_SPLIT = re.compile(r"(?<=[.!?])\s+")
_CJK_SPLIT = re.compile(r"(?<=[。！？；])")


def split_sentences(text: str, lang: str = "en") -> list:
    """Sentence split that works for BOTH CJK (。！？；, no trailing space) and Latin (.!? + space).
    Language-agnostic: applies both rules, so a mixed-language paragraph splits correctly either way.
    A single pattern that requires whitespace after the terminator silently makes every zh paragraph
    one sentence (the bug this replaces in factcheck.py / citations.py / reco_check.py)."""
    parts = re.split(r"(?<=[。！？；])\s*|(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p and p.strip()]


def term_find_iter(term: str, text: str):
    """Yield match start-positions of `term` in `text`, boundary-aware for BOTH scripts:
    - CJK term (or CJK-adjacent): plain substring (there are no word spaces, so \\b never fires and
      the old (?<!\\w)…(?!\\w) guard NEVER matched inside zh prose — the reco safety-gate bug).
    - Latin term: word-boundary guarded so 'AI' doesn't match inside 'RAID'.
    Case-insensitive. Used by the discontinued-product gate and anywhere a name must be located."""
    if not term:
        return
    if has_cjk(term):
        low_t, low_x = term.lower(), text.lower()
        i = low_x.find(low_t)
        while i != -1:
            yield i
            i = low_x.find(low_t, i + 1)
    else:
        for m in re.finditer(r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])", text, re.I):
            yield m.start()


# THE one CJK range set: kana without the katakana middle dot U+30FB '・' (U+3040–30FA), then everything
# U+30FC–9FFF (prolonged-sound mark, bopomofo, Hangul compat jamo, enclosed CJK / compat blocks, ext-A,
# unified ideographs), compatibility ideographs (U+F900–FAFF) and Hangul syllables + jamo ext-B tail
# (U+AC00–D7AF).
# CJK punctuation (U+3000–303F) and full-width forms are deliberately OUT, so a run of CJK_CLASS
# characters ends at punctuation. assemble / claim_edit / link-plan / citations import this rather
# than keeping a copy — a private copy had already drifted (citations' lacked ext-A). CJK_CLASS is
# the body of a regex character class.
CJK_CLASS = "\u3040-\u30fa\u30fc-\u9fff\uf900-\ufaff\uac00-\ud7af"
# Heading/claim normalization tokens: Latin/digit runs PLUS CJK runs. A bare [a-z0-9]+ matches
# nothing in a zh/ja/ko heading, so every CJK heading normalized to "" (all planned H2s "missing",
# all gaps one dismissal id, all sections' triples on the last heading). Latin-only text tokenizes
# exactly as before.
NORM_TOKEN_RE = re.compile(r"[a-z0-9]+|[" + CJK_CLASS + r"]+")


def has_cjk(text) -> bool:
    return bool(re.search("[" + CJK_CLASS + "]", str(text or "")))


def norm_tokens(value) -> list[str]:
    """Case-fold a name into alphanumeric tokens for boundary-safe entity matching."""
    return re.findall(r"[^\W_]+", str(value or "").casefold(), re.UNICODE)


def token_phrase_match(needle, haystack) -> bool:
    """Whole-token phrase match, ignoring case and spaces between the phrase's characters."""
    want = "".join(norm_tokens(needle))
    tokens = norm_tokens(haystack)
    if not want or not tokens:
        return False
    for start in range(len(tokens)):
        phrase = ""
        for token in tokens[start:]:
            phrase += token
            if phrase == want:
                return True
            if len(phrase) >= len(want):
                break
    return False


def article_language(article_dir, default: str = "en") -> str:
    """Read + normalize 00-input.json 'language' for a stage that only has the article dir."""
    import json
    try:
        d = json.loads((Path(article_dir) / "00-input.json").read_text(encoding="utf-8"))
        return norm_lang(d.get("language"), default)
    except Exception:
        return default


import re as _re
_SLUG_OK = _re.compile(r"^[a-z0-9][a-z0-9-]{0,80}$")


def safe_slug(slug: str) -> str:
    """Reject anything that isn't a plain kebab-case slug — engine CLIs otherwise let '../x' escape
    the articles root (confirmed: `pipeline.py init ../../x` wrote outside the tree). The app's
    SLUG_RE already gates the UI; this closes the CLI/skill path. Raises SystemExit on a bad slug."""
    s = (slug or "").strip()
    if not _SLUG_OK.match(s):
        raise SystemExit(f"[slug] invalid slug '{slug}' — must be lowercase kebab-case "
                         f"([a-z0-9-], start alphanumeric, ≤81 chars); refusing (path-traversal guard)")
    return s


def safe_slug_or_none(slug):
    """Like safe_slug, but for READ sites that must degrade (skip-with-note), never crash, on a bad
    pointer — e.g. a variant's `translation_of`, which is a value in an app-EDITABLE 00-input.json
    file, not a CLI argument a human typed. `'../../x'` (or an absolute path, which pathlib's `/`
    join silently accepts and lets escape the articles root entirely) → None instead of raising."""
    s = (slug or "").strip()
    return s if _SLUG_OK.match(s) else None
