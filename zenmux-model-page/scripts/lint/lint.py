#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Vendored from the wendy-writes engine, commit 175476d (engine/lint.py). Changes: this header, and
# `from __future__ import annotations` (Python 3.9 compatibility). `import statgather` resolves to the
# sibling stdlib-only stub in this folder (stats contract disabled). The kit_io / brand_guard imports
# (rule H1) sit in try/except and are not shipped, so H1 is a no-op.
"""
Microsemantics Linter v2.0 — language-pack architecture
Rules engine = language-agnostic. All language assets live in packs.

Usage:
    python lint.py draft.md --config config.json
    python lint.py draft.md --lang en
    python lint.py draft.md --lang es --lang-pack packs/es.json
    python lint.py draft.md --json report.json

Language resolution order: --lang flag > config.json "language" > "zh"

External pack JSON = same schema as built-in packs below; missing keys
fall back to the base pack declared in "extends" ("en" or "zh").

Adding a new language = write one JSON file. No code changes.

config.json (all optional):
{
  "language": "zh",
  "entities": ["外链"],
  "brief_headings": ["什么是外链"],
  "extra_hedges": [], "extra_cliches": []
}

Exit code: 0 = PASS, 1 = REWRITE
Stdlib only.
"""

from __future__ import annotations   # vendored edit: lets `X | None` annotations parse on Python 3.9
import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from dataclasses import dataclass, field, asdict

# statistics-page [STAT:] grammar + usable-stats predicate — single source of truth in statgather.py
# (see its module docstring for why: lint/assemble/pipeline used to each keep a drifted copy).
import statgather as _SG
import langutil as _LU      # KT_HEADING_ALT — the Key-Takeaways heading names (shared with tldr/autopilot/atglance)

# ═══════════════════════ LANGUAGE PACKS ═══════════════════════
# tokenizer: "space" (whitespace tokens) | "char" (CJK char count)

# zh count-announcement fragments — composed into BOTH the zh pack pattern and the A4 generic
# fallback so the digit/classifier inventories can never drift again (they had already diverged
# by one classifier: 大 existed only in the fallback copy)
_ZH_NUM = "[0-9一二三四五六七八九十]+"
_ZH_CLS = "[种个条类项步点大]"

# ja count-announcement fragments — same single-source rule as the zh pair above. Full-width digits
# are matched too (int("５") works). The lookbehind refuses a mid-number / approximate start (1,500件,
# 3.5点, 数十個, 約5つ); the (?![目満め]) lookahead refuses 3つ目/2つめ (the third/second one) and 5点満点
# (a score scale) — see the "ja" pack note. The lead-in is MANDATORY for the weak classifiers
# (_JA_CLS_WEAK: 1つ1つ / 3個セット / 10点中8点 / 1件あたり are incidental counts, not announcements) and
# optional only for 選 / 項目, which almost only ever announce a list ("おすすめは3選です").
_JA_NUM = "[0-9０-９一二三四五六七八九十]+"
_JA_CLS = "つ|個|選|項目|点|種類|ステップ|段階|件"
_JA_CLS_WEAK = "つ|個|点|種類|ステップ|段階|件"
_JA_NOT_MID = "(?<![0-9０-９,，.．数約])"
_JA_LEADS = "以下の|次の|下記の|これらの|主な|全|計|合計|全部で"
_JA_COUNT_LEAD = _JA_NOT_MID + f"(?:{_JA_LEADS})?"
_JA_COUNT_TAIL = "(?![目満め])"
_JA_NUM_RANK = "(?<![A-Za-z])(?:ベスト|トップ|(?i:top|best))\\s*([0-9０-９一二三四五六七八九十]{1,3})(?![0-9０-９])"

LANG_PACKS = {
    "en": {
        "tokenizer": "space",
        "hedges": [
            r"\bmight\b", r"\bmaybe\b", r"\bperhaps\b", r"\bpossibly\b",
            r"\bsome people say\b", r"\barguably\b", r"\bit seems\b",
            r"\bsort of\b", r"\bkind of\b",
        ],
        "cliches": [
            r"in today'?s fast-?paced world", r"\bdelve\b", r"\bunlock\b",
            r"navigate the (?:landscape|complexit)", r"it'?s important to note",
            r"in conclusion", r"\bgame-?changer\b", r"\bseamless(?:ly)?\b",
            r"\bleverage\b", r"at the end of the day", r"\bdive deep(?:er)? into\b",
            r"\bever-?evolving\b", r"\bcrucial\b", r"a testament to",
        ],
        "modals": [r"\bcan be\b", r"\bmay be\b", r"\bcould\b", r"\bwould\b", r"\bmight be\b",
                   r"\bshould\b", r"\bprobably\b", r"\blikely\b"],
        "generic_verbs": [r"\bmake sure\b", r"\bmakes?\b", r"\bdo(?:es)?\b", r"\bget(?:s)?\b", r"\bthings?\b"],
        "transitions": [r"^however\b", r"^moreover\b", r"^furthermore\b", r"^in addition\b",
                        r"^on the other hand\b", r"^that being said\b", r"^additionally\b"],
        "if_starters": [r"^if\b", r"^when(?:ever)?\b"],
        "pronoun_start": r"^(it|this|that|these|those|they)\b",
        "pronoun_start_flags": "i",
        "vague_qty": r"\b(many|several|a lot of|lots of|numerous|various|countless)\b",
        "vague_qty_flags": "i",
        "passive": r"\b(?:is|are|was|were|be|been|being)\s+\w+(?:ed|en)\b",
        "passive_flags": "i",
        "list_count": r"\b(?:there are|here are|includes?|consists? of)\s+(\d+|two|three|four|five|six|seven|eight|nine|ten)\b",
        "list_count_flags": "i",
        "num_words": {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
                      "seven": 7, "eight": 8, "nine": 9, "ten": 10},
        "sentence_limit": 30,
        "para_word_limit": 90,
        "para_sent_limit": 4,
        "modal_ratio_max": 0.10,
        "passive_ratio_max": 0.15,
    },
    "zh": {
        "tokenizer": "char",
        "hedges": ["可能", "或许", "也许", "大概", "据说", "据称", "有人认为", "似乎", "貌似"],
        "cliches": ["在当今", "值得注意的是", "总而言之", "让我们深入了解", "让我们一起",
                    "不可或缺", "赋能", "随着.{0,8}的发展", "众所周知", "毋庸置疑",
                    "本文将", "在本文中", "不难发现", "综上所述", "值得一提的是"],
        "modals": ["可以是", "或将", "可能会", "应该", "大概率", "很可能"],
        "generic_verbs": ["进行", "做好", "搞", "弄"],
        "transitions": ["^然而", "^此外", "^另外", "^与此同时", "^总的来说", "^除此之外", "^除此以外", "^另一方面"],
        "if_starters": ["^如果", "^若", "^倘若", "^假如"],
        "pronoun_start": r"^(它|这|那|他们|它们|此)",
        "pronoun_start_flags": "",
        "vague_qty": r"(很多|不少|大量|众多|许多|无数|各种|种种)",
        "vague_qty_flags": "",
        "passive": r"被[\u4e00-\u9fff]{1,6}|由[\u4e00-\u9fff]{1,8}所",
        "passive_flags": "",
        "list_count": rf"(?:共有|共计|总共|共|包括|包含|含有|分为|有以下|以下)\s*({_ZH_NUM})\s*{_ZH_CLS}",   # lead-ins widened Jul 2/4 (共6项, 包含4个 false-blocked live articles); digits/classifiers = shared fragments
        "list_count_flags": "",
        "num_words": {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
                      "六": 6, "七": 7, "八": 8, "九": 9, "十": 10},
        "sentence_limit": 45,
        "para_word_limit": 135,
        "para_sent_limit": 4,
        "modal_ratio_max": 0.10,
        "passive_ratio_max": 0.15,
    },
    # Japanese (added 2026-10): the zh pack used to serve ja by fallback and produced actively harmful
    # results — hedge 可能 blocked 利用可能/対応可能, ^若 flagged 若者, 被[一-鿿] flagged 被害, 大量 fired B2, and
    # kana-heavy sentences counted as ~1 "word" so C4/E3/C7 never fired. Design notes:
    #  • hedges: NO 可能 (a suffix of ordinary technical Japanese) and NO らしい (matches 新しい/素晴らしい).
    #  • pronoun_start: a pronoun used AS a pronoun — the lookahead for a case particle/comma keeps
    #    determiners (この/その/これらの) and それぞれ out; C1 is a BLOCKER so precision beats recall.
    #  • passive: [かがさたばらわ]れ(?:る|た|て|ま) excludes これ/それ/生まれ/流れ; the ratio cap is 0.30
    #    (not 0.15) because される/言われる/知られている are routine in Japanese prose.
    #  • list_count: high-precision count announcement, group 1 = the number (see _JA_* fragments).
    #  • count_generic / count_bare: ja replacements for A4's generic nets (_ZH_COUNT_RX, and
    #    _EN_COUNT_RX whose \b can never fire between a digit and kana).
    #  • e7_qty / e7_sourced: ja quantity units and source markers, ADDED to E7's/ST1's base net for
    #    this pack only — merging them into the shared lists would change zh (件/万人 are ordinary zh).
    "ja": {
        "tokenizer": "char",
        "hedges": ["かもしれ", "おそらく", "恐らく", "たぶん", "多分(?!野)", "と言われてい", "と思われ",
                   "気がします", "気がする", "ようです"],
        "cliches": ["いかがでした", "本記事では", "この記事では", "参考にしてみてください", "ぜひ参考に",
                    "まとめると", "言うまでもなく", "ご存知の通り", "ご存じの通り", "周知の通り",
                    "注目すべき", "特筆すべき", "見ていきましょう", "深掘りしていき", "シームレス",
                    "ゲームチェンジャー", "必要不可欠", "目まぐるしく変化"],
        "modals": ["でしょう", "だろう", "可能性があ", "と考えられ", "はずです", "べきです", "べきだ"],
        "generic_verbs": ["を行[いうっえわ]", "することができ"],
        "transitions": ["^しかし", "^また[、,]", "^さらに", "^加えて(?!ください|みて)", "^それに加えて", "^一方で",
                        "^一方[、,]", "^総じて", "^ちなみに", "^なお[、,]"],
        "if_starters": ["^もし(?!くは)", "^仮に"],
        "pronoun_start": r"^(これら|それら|あれら|彼女ら|彼ら|これ|それ|あれ|彼女|彼)(?=[はがをも、])",
        "pronoun_start_flags": "",
        "vague_qty": r"(多くの|たくさん|沢山|数多く|多数の|無数の|さまざまな|様々な|いくつかの|大量の)",
        "vague_qty_flags": "",
        "passive": r"(?<!分)[かがさたばらわ]れ(?:る|た|て|ま)",
        "passive_flags": "",
        "list_count": rf"{_JA_NOT_MID}(?:(?:{_JA_LEADS})({_JA_NUM})\s*(?:{_JA_CLS}){_JA_COUNT_TAIL}"
                      rf"|({_JA_NUM})\s*(?:選(?![ぶびんばべ])|項目){_JA_COUNT_TAIL})",
        "list_count_flags": "",
        # broad net: the lead-in stays optional and ベスト/トップ/TOP/BEST N counts — but a number here only
        # ever CONFIRMS a count (== n) or stays silent, it can never raise a mismatch
        "count_generic": rf"{_JA_COUNT_LEAD}({_JA_NUM})\s*(?:{_JA_CLS}|社|製品|ツール|方法|ポイント){_JA_COUNT_TAIL}|{_JA_NUM_RANK}",
        "multi_kanji_num": True,                # 二十 / 十五 / 三十二 in a count announcement (see _to_count)
        "count_bare": r"(?<![0-9０-９.,，．$€£¥￥])([0-9０-９]{1,2})(?![0-9０-９.,，．%％年月日])",
        "e7_qty": r"(?:[￥]\s?\d[\d,.]*)|\d[\d,.]*\s*(?:万円|億円|円|億|兆|ドル|時間|分間|件|万人|万|％|パーセント)",
        "e7_sourced": r"出典|によると|によれば|調べ|報告|調査|[(（][^)）]*[A-Za-z぀-ヿ一-鿿]{2}[^)）]*[)）]",
        # a short price/tax note — （税込） (税抜) （送料別） （約500円） — is NOT a source: blanked out of the
        # sourcing window before BOTH source nets run (the shared one also reads any (CJK) as a source).
        # ≤16 chars, so a long attribution that merely mentions a yen figure still counts.
        "e7_noise": r"[(（](?=[^)）]{0,16}[)）])[^)）]*(?:税込|税抜|税別|送料|円)[^)）]*[)）]",
        # a count announcement ("次の3件を紹介します") is a list size, not an unsourced quantity — E7/ST1 skip
        # a 件 match inside one (全/計 leads are NOT here: "合計1200件" is a real figure)
        "e7_announce": r"(?:以下の|次の|下記の|これらの|主な)\s*[0-9０-９一二三四五六七八九十]{1,3}\s*件",
        "num_words": {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
                      "六": 6, "七": 7, "八": 8, "九": 9, "十": 10},
        "sentence_limit": 60,
        "para_word_limit": 200,
        "para_sent_limit": 4,
        "modal_ratio_max": 0.15,
        "passive_ratio_max": 0.30,
    },
}

def _flags(s: str) -> int:
    return re.I if "i" in (s or "") else 0

class Pack:
    """Compiled language pack. Hedges/cliches/modals accept plain strings
    (treated as regex-escaped if no regex metachars needed — we compile as-is)."""

    def __init__(self, raw: dict, extra_hedges=None, extra_cliches=None):
        self.tokenizer = raw.get("tokenizer", "space")
        self.hedges = [re.compile(p, re.I if not _has_cjk(p) else 0)
                       for p in raw["hedges"] + (extra_hedges or [])]
        self.cliches = [re.compile(p, re.I if not _has_cjk(p) else 0)
                        for p in raw["cliches"] + (extra_cliches or [])]
        self.modals = [re.compile(p, re.I if not _has_cjk(p) else 0)
                       for p in raw["modals"]]
        self.generic_verbs = [re.compile(p, re.I if not _has_cjk(p) else 0)
                              for p in raw.get("generic_verbs", [])]
        self.transitions = [re.compile(p, re.I if not _has_cjk(p) else 0)
                            for p in raw.get("transitions", [])]
        self.if_starters = [re.compile(p, re.I if not _has_cjk(p) else 0)
                            for p in raw.get("if_starters", [])]
        self.pronoun_start = re.compile(raw["pronoun_start"], _flags(raw.get("pronoun_start_flags")))
        self.vague_qty = re.compile(raw["vague_qty"], _flags(raw.get("vague_qty_flags")))
        self.passive = re.compile(raw["passive"], _flags(raw.get("passive_flags")))
        self.list_count = re.compile(raw["list_count"], _flags(raw.get("list_count_flags")))
        # optional per-language overrides/additions (None → the shared zh/en defaults apply unchanged):
        # count_generic replaces _ZH_COUNT_RX in A4's generic net, count_bare replaces _EN_COUNT_RX for a
        # colon-ended paragraph, e7_qty/e7_sourced EXTEND E7's (and ST1's) quantity / source-marker nets.
        self.count_generic = re.compile(raw["count_generic"]) if raw.get("count_generic") else None
        self.count_bare = re.compile(raw["count_bare"]) if raw.get("count_bare") else None
        self.e7_qty = re.compile(raw["e7_qty"], re.I) if raw.get("e7_qty") else None
        self.e7_sourced = re.compile(raw["e7_sourced"]) if raw.get("e7_sourced") else None
        self.e7_noise = re.compile(raw["e7_noise"]) if raw.get("e7_noise") else None
        self.e7_announce = re.compile(raw["e7_announce"]) if raw.get("e7_announce") else None
        self.multi_kanji_num = bool(raw.get("multi_kanji_num"))
        self.num_words = raw.get("num_words", {})
        self.sentence_limit = raw.get("sentence_limit", 30)
        self.para_word_limit = raw.get("para_word_limit", 90)
        self.para_sent_limit = raw.get("para_sent_limit", 4)
        self.modal_ratio_max = raw.get("modal_ratio_max", 0.10)
        self.passive_ratio_max = raw.get("passive_ratio_max", 0.15)

def _is_cjk_char(c: str) -> bool:
    """Han + kana (hiragana/katakana U+3040\u201330FF, Han U+4E00\u20139FFF, compat ideographs U+F900\u2013FAFF).
    Han-only counting made a kana-heavy Japanese sentence weigh ~1 "word" (C4/E3/C7 never fired, a
    kana-only keyword failed G1a). Hangul is deliberately NOT here: Korean is space-delimited and
    keeps its whitespace word counting."""
    return "\u3040" <= c <= "\u30ff" or "\u4e00" <= c <= "\u9fff" or "\uf900" <= c <= "\ufaff"

def _has_cjk(s: str) -> bool:
    return any(_is_cjk_char(c) for c in s)

def load_pack(lang: str, pack_path: str | None, extra_hedges, extra_cliches) -> Pack:
    if pack_path:
        ext = json.load(open(pack_path, encoding="utf-8"))
        base = dict(LANG_PACKS.get(ext.get("extends", "en"), LANG_PACKS["en"]))
        base.update({k: v for k, v in ext.items() if k != "extends"})
        return Pack(base, extra_hedges, extra_cliches)
    if lang in LANG_PACKS:
        return Pack(LANG_PACKS[lang], extra_hedges, extra_cliches)
    # auto-discover an external pack (packs/<lang>.json) before falling back
    auto = Path(__file__).resolve().parent / "packs" / f"{lang}.json"
    if auto.exists():
        ext = json.load(open(auto, encoding="utf-8"))
        base = dict(LANG_PACKS.get(ext.get("extends", "en"), LANG_PACKS["en"]))
        base.update({k: v for k, v in ext.items() if k != "extends"})
        return Pack(base, extra_hedges, extra_cliches)
    # DEGRADE, never crash verify: Korean uses the zh pack (char tokenizer + zh limits), everything
    # else the en pack (ja has its own built-in pack now). Sentence rules stay meaningful;
    # language-specific word lists just fall back until a real packs/<lang>.json ships.
    fallback = "zh" if lang == "ko" else "en"
    print(f"[lint] no pack for '{lang}' — using the {fallback} pack (provide packs/{lang}.json to specialize)",
          file=sys.stderr)
    return Pack(LANG_PACKS[fallback], extra_hedges, extra_cliches)

# ═══════════════════════ shared assets (language-neutral) ═══════════════════════

# Single source of truth for "how much shorter is too much shorter" — the truncation-guards fix
# round used 0.4 (a rewrite/revision under 40% of what it replaces is treated as an accidental
# truncation, not a legitimate edit) independently in three places: draft.py's lint-fix splice
# guard, and app/main.py's review-chat markdown-section AND JSON-patch-key shrinkage warnings.
# Importing this one constant everywhere means a future retune can't leave the three guards
# disagreeing with each other (round 2 finding #10).
SHRINK_RATIO = 0.4

# Every deterministic rule id this lint engine can emit, stamped into summary.det_rules_checked so
# downstream consumers (the Evidence Ledger) can tell "ran and found nothing" apart from "the report
# predates this rule" — a report only records violations, so a silent rule and an unknown rule are
# otherwise indistinguishable, and a regenerated ledger for an old report would render newer rules
# as a ✓ pass that never executed. Keep in sync when a rule is added.
DET_RULE_IDS = sorted([
    "A4", "A7", "A8", "B1", "B2", "B3", "C1", "C4", "C5", "C6", "C7", "D3", "D4", "E2", "E3", "E4",
    "E5", "E7", "E8", "E9", "F1", "F3", "F5", "G1a", "G1b", "G1c", "G1d", "G1e", "H1", "TC1",
    "ST1", "ST2", "ST3",
])

PLACEHOLDER_BAD = re.compile(r"\[(?:image|图片|placeholder|插图|表格)", re.I)

@dataclass
class Violation:
    rule: str
    severity: str           # blocker | warning | info
    location: str
    evidence: str
    fix_instruction: str

@dataclass
class SectionReport:
    section: str
    violations: list = field(default_factory=list)

# ═══════════════════════ text utils ═══════════════════════

def is_cjk(text: str) -> bool:
    cjk = sum(1 for c in text if _is_cjk_char(c))
    return cjk > len(text) * 0.25

def word_len(sent: str, pack: Pack) -> int:
    # per-sentence fallback handles mixed-language docs
    if pack.tokenizer == "char" and is_cjk(sent):
        return sum(1 for c in sent if _is_cjk_char(c))
    return len(sent.split())

def split_sentences(text: str, pack: Pack):
    text = re.sub(r"^#{1,6}\s+.*$", "", text, flags=re.M)                     # headings
    text = re.sub(r"^\s*(?:[-*+]|\d+[\.、)])\s+.*$", "", text, flags=re.M)    # list lines
    text = re.sub(r"^\s*\[(?:IMG|TABLE)[^\]]*\]\.?\s*$", "", text, flags=re.M)  # asset markers ≠ prose
    text = re.sub(r"^\s*\|.*$", "", text, flags=re.M)   # markdown table rows ≠ prose(listicle 对比表是正文)
    text = re.sub(r"^\s*>.*$", "", text, flags=re.M)    # blockquote = 逐字引文,不审我们的散文规则
    # 拉丁终止符必须后跟空白才算句界——否则 Flux.2 / Leonardo.ai / 5.85 / et al., 会被误切,
    # 虚增 C4/E3。CJK 终止符(。!?)无需空白,保持原行为。
    parts = re.split(r"(?<=[。！？])\s*|(?<=[!?\.])\s+", text)
    # keep a segment with real content: >1 token by the pack's own counter, OR any CJK char (a
    # spaceless zh sentence is 1 "word" under the en/space tokenizer and was silently dropped from
    # every sentence rule in a mixed-language doc)
    return [p.strip() for p in parts
            if p.strip() and (word_len(p, pack) > 1 or _has_cjk(p))]

def split_paragraphs(text: str):
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()
            and not p.strip().startswith(("#", "|", "```", "- ", "* ", "1.", ">"))
            and not re.match(r"\[(?:IMG|TABLE)\b", p.strip())]                # asset markers ≠ paragraphs

def norm_heading(h: str) -> str:
    # canonical heading identity = the token stream joined. Defined THROUGH _heading_tokens so D3's
    # whole-string matching and D4's token-wise truncation check share one cleaning pipeline — two
    # copies of the markdown-strip/NFKC steps let a one-sided edit make the rules disagree about
    # whether the same heading "is" the same heading.
    return "".join(_heading_tokens(h))


def _heading_tokens(h: str) -> list:
    """Markdown-link-stripped, NFKC-lowered WORD TOKENS of a heading — the single owner of heading
    cleaning (norm_heading is the joined form). Tokens are used where word boundaries matter (D4's
    truncated-heading-prefix check): concatenating first lets two genuinely different headings that
    just happen to share a char run ('Sales Tips' vs 'Sales Tip Sheets' — 'tips' vs 'tip' are
    different words) false-match as a truncation of one another."""
    h = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", h)   # markdown link/image → visible text (drop the
    h = unicodedata.normalize("NFKC", h.lower())        # URL so an inline link still matches the brief)
    return re.findall(r"[^\s\W_]+", h, flags=re.UNICODE)


def _is_truncated_heading(doc_tokens: list, brief_tokens: list) -> bool:
    """True if doc_tokens looks like brief_tokens cut off partway through: every token before the
    last must match brief's corresponding token EXACTLY (word-boundary-aware — a raw concatenated-
    char prefix test can't tell where one word ends and the next begins); the final doc token must
    be a STRICT, non-empty prefix of the corresponding brief token (a genuine partial word). An
    exactly-equal final token — a clean word-boundary shortening, e.g. a human trimming a long
    heading at Gate 3 — is NOT a truncation: it's indistinguishable from an intentional edit, and
    flagging it blocked approvals on content a reviewer deliberately shortened (round 3)."""
    if not doc_tokens or len(doc_tokens) > len(brief_tokens) or doc_tokens == brief_tokens:
        return False
    if doc_tokens[:-1] != brief_tokens[:len(doc_tokens) - 1]:
        return False
    last_doc, last_brief = doc_tokens[-1], brief_tokens[len(doc_tokens) - 1]
    return last_doc != last_brief and last_brief.startswith(last_doc)

def parse_sections(md: str):
    lines = md.splitlines()
    sections, cur_head, buf = [], "_intro", []
    for ln in lines:
        m = re.match(r"^##\s+(?!#)(.+)", ln)
        if m:
            sections.append((cur_head, "\n".join(buf)))
            cur_head, buf = m.group(1).strip(), []
        else:
            buf.append(ln)
    sections.append((cur_head, "\n".join(buf)))
    return sections

def count_list_items(body: str) -> list:
    """Count items per contiguous list. A blank line between items (a "loose" list) and an indented
    continuation line (a wrapped item) both stay in the SAME list — only a non-blank, non-indented,
    non-item line ends one. Fenced code blocks are skipped entirely (``` bullets aren't a prose list)."""
    blocks, cur, in_fence = [], 0, False
    for ln in body.splitlines():
        if re.match(r"^\s*(?:```|~~~)", ln):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if re.match(r"^\s*(?:[-*+]|\d+[\.、)])\s+", ln):
            cur += 1
        elif not ln.strip():
            continue                       # blank line → loose-list continuation, not a list break
        elif cur and re.match(r"^\s+\S", ln):
            continue                       # indented continuation of the current wrapped item
        else:
            if cur:
                blocks.append(cur)
            cur = 0
    if cur:
        blocks.append(cur)
    return blocks

# ═══════════════════════ fix-instruction language ═══════════════════════
# Rule messages are unified to ONE language — the article's — never mixed zh/en. Set from the resolved
# language at the start of lint(); _t() picks the matching half. Default English (most readable fallback).
_FIX_LANG = "en"

def _t(zh: str, en: str) -> str:
    """Return the fix instruction in the article's language (zh for Chinese drafts, else English)."""
    return zh if _FIX_LANG == "zh" else en

# ═══════════════════════ rules (language-agnostic, pack-driven) ═══════════════════════

def _list_blocks_with_pos(body: str):
    """[(start_line_idx, n_items)] — loose lists, wrapped continuations, fenced code skipped —
    keeping each block's position so A4 can inspect the paragraph directly above it."""
    blocks, cur, start, in_fence = [], 0, None, False
    lines = body.splitlines()
    for idx, ln in enumerate(lines):
        if re.match(r"^\s*(?:```|~~~)", ln):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if re.match(r"^\s*(?:[-*+]|\d+[\.、)])\s+", ln):
            if cur == 0:
                start = idx
            cur += 1
        elif not ln.strip():
            continue
        elif cur and re.match(r"^\s+\S", ln):
            continue
        else:
            if cur:
                blocks.append((start, cur))
            cur, start = 0, None
    if cur:
        blocks.append((start, cur))
    return blocks, lines


def count_list_items(body: str) -> list:
    """Item counts per contiguous list. Thin wrapper over _list_blocks_with_pos — ONE walker."""
    return [n for _, n in _list_blocks_with_pos(body)[0]]


# standalone asset/citation marker lines sit between an announcement and its list without being
# prose — the adjacency walk must see through them
_ASSET_LINE = re.compile(r"^\s*\[(?:IMG|IMAGE|TABLE|CHART|CITE|N)\b[^\]]*\]\.?\s*$", re.I)
_ZH_COUNT_RX = re.compile(rf"({_ZH_NUM})\s*{_ZH_CLS}")
# en generic count: 1-2 digits or a number word; never a year (4 digits), price ($ prefix),
# percentage, decimal, or date-unit-suffixed number
_EN_COUNT_RX = re.compile(
    r"(?<![\d.$€£])\b(\d{1,2}|two|three|four|five|six|seven|eight|nine|ten)\b(?![\d.%])(?!\s*[%年月])",
    re.I)
_EN_NUM_WORDS = LANG_PACKS["en"]["num_words"]          # single source — never a second literal


def _adjacent_paragraph(lines: list, start: int) -> str:
    """The contiguous prose paragraph directly above a list (blank lines and standalone asset
    markers skipped; headings/tables/blockquotes/other lists terminate it)."""
    j = start - 1
    while j >= 0 and (not lines[j].strip() or _ASSET_LINE.match(lines[j])):
        j -= 1
    block = []
    while j >= 0:
        ln = lines[j].strip()
        if (not ln or ln.startswith(("#", "|", ">")) or _ASSET_LINE.match(lines[j])
                or re.match(r"^\s*(?:[-*+]|\d+[\.、)])\s+", lines[j])):
            break
        block.append(ln)
        j -= 1
    return " ".join(reversed(block))


def _to_count(raw: str, pack: Pack):
    if raw.isdigit():
        return int(raw)
    n = pack.num_words.get(raw) or _EN_NUM_WORDS.get(raw.lower())
    if n is None and pack.multi_kanji_num:
        n = _cjk_number(raw)                    # 二十 / 十五 / 三十二 (ja only — zh keeps its single-numeral table)
    return n


def _match_count(m, pack: Pack):
    """The count a pattern match carries — its first participating group (an alternation of
    patterns, as ja's count_generic is, puts the number in a different group per branch)."""
    raw = next((g for g in m.groups() if g), None)
    return _to_count(raw, pack) if raw else None


def _a4_verdict(paragraph: str, pack: Pack, n: int):
    """Declarative announcement spec (v2.1) — precision-first, since A4 is a blocker:
      1. any candidate count in the adjacent paragraph == n     → announced (ok)
      2. a HIGH-PRECISION pack-pattern count exists but != n    → mismatch (report last one)
      3. only generic/incidental counts exist, none == n        → silent (don't guess)
      4. no counts at all                                       → missing announcement
    Candidates: pack.list_count matches; zh 数字+量词 anywhere; bare numbers (year/price/%-guarded)
    only when the paragraph ends with a colon. Emphasis stripped first ('There are **7**')."""
    s = re.sub(r"[*_`]", "", paragraph).strip()
    pack_counts = [v for m in pack.list_count.finditer(s) if (v := _match_count(m, pack))]
    gen = []
    if pack.tokenizer == "char":
        # a pack may bring its own generic set (ja: 3つ/7個/5社/10ツール…); zh keeps _ZH_COUNT_RX exactly
        gen += [v for m in (pack.count_generic or _ZH_COUNT_RX).finditer(s)
                if (v := _match_count(m, pack))]
    if s.endswith((":", "：")):
        # likewise the bare-number net: _EN_COUNT_RX needs \b, which never fires between a digit and
        # kana ("TOP5：" / "ツール5：") — a ja paragraph ending in a full-width colon uses count_bare
        gen += [v for m in (pack.count_bare or _EN_COUNT_RX).finditer(s)
                if (v := _to_count(m.group(1), pack))]
    if n in pack_counts or n in gen:
        return "ok", n
    if pack_counts:
        return "mismatch", pack_counts[-1]
    if gen:
        return "ok", None                      # incidental numbers near a list — stay silent
    return "missing", None


def rule_A4_list_count(head, body, rep, pack):
    # A "Key Takeaways" summary block and a "References"/"Sources" bibliography are deliberate scannable
    # lists — they must NOT carry a "There are N…" count announcement (which reads odd in a summary box
    # or a source list). Exempt these headings from A4.
    if re.match(rf"^\s*(?:{_LU.KT_HEADING_ALT}|references?|sources?|参考文献|参考资料)\s*$",
                head.lstrip("# ").strip(), re.I):
        return
    blocks, lines = _list_blocks_with_pos(body)
    for start, n in blocks:
        paragraph = _adjacent_paragraph(lines, start)
        verdict, claimed = (_a4_verdict(paragraph, pack, n) if paragraph else ("missing", None))
        if verdict == "missing":
            rep.violations.append(Violation("A4", "blocker", head,
                f"list({n} items) without count announcement",
                _t(f"紧邻列表上方的段落需报数:'共有 {n} 项…'", f"announce the count in the paragraph directly above the list: 'There are {n}…'")))
        elif verdict == "mismatch":
            rep.violations.append(Violation("A4", "blocker", head, paragraph[:80],
                _t(f"声称 {claimed} 项但实际列表为 [{n}] 项", f"claims {claimed} items, but the list has [{n}]")))


# A listicle's headline is a PROMISE of a count: "10大专家", "Top 10 Tools", "7 Best Cameras".
# saas-geo-10-agency promised 10 in its H1 and every H2, planned 9 in the brief, and the draft wrote
# FOUR — then the at-a-glance table faithfully showed 4 while the comparison table showed 9. Nothing
# caught it: D3 checks that each H2 exists, never that an H2 delivered the entries it promised, and
# A4 governs the count announced in prose, not the one in the heading. It reached final review and a
# human found it, which is the most expensive place to find it.
_PROMISE_RX = re.compile(
    r"(?:top|best)\s+(\d{1,2})\b"                       # Top 10 / Best 7
    r"|\b(\d{1,2})\s+(?:best|top|greatest)\b"            # 10 Best
    # NO trailing \b on the CJK branch: CJK chars are word chars, so "10大专家" has no boundary
    # after 大 and the whole alternation silently never fired — the same trap E7 and _STAT already
    # carry notes about.
    # 第 guard: 第3位 is an ORDINAL ("3rd place"), not a promise of three — it used to read as one
    r"|(?<![0-9第])(\d{1,2})\s*[大个家款种位]"                # 10大 / 7个 / 9家
    r"|最强\s*(\d{1,2})",                                 # 最强10
    re.I)
# Japanese additions: 10選 / 7つ / 10個 / 10社, and ベスト10 / トップ10 (おすすめAIツール10選). Full-width digits
# ride on \d; (?!\d) stops ベスト100 reading as 10; 個(?!月) keeps "3個月" (3 months) out. The space after
# TOP/BEST is optional here (人気ランキングTOP10) — behind (?<![A-Za-z]) / (?![0-9A-Za-z]) so it never reads
# inside a word. These live in their OWN regex, applied only to Japanese headings (see _promised_count):
# zh-Hant "3個小時" / "10社对比" are not promises, and zh/en/ko must keep exactly main's reading.
_PROMISE_JA_RX = re.compile(
    r"(?<![0-9０-９第])(\d{1,2})\s*(?:選|つ|個(?!月)|社)"
    r"|(?:ベスト|トップ)\s*(\d{1,2})(?!\d)"
    r"|(?<![A-Za-z])(?:top|best)\s*(\d{1,2})(?![0-9A-Za-z])",
    re.I)
_KANA_RX = re.compile(r"[\u3040-\u30ff]")
_NUMBERED_H3 = re.compile(r"^\s{0,3}#{3,4}\s+(\d{1,2})[.．、)）]\s*\S", re.M)
# Chinese headlines usually spell the count as a NUMERAL, not a digit — "十大GEO专家", not "10大".
# top-10-geo-experts promised ten that way and every branch above stayed silent, because 十 is not \d.
# The lookbehind keeps ordinary prose out: 第十/几十/数十 are not promises, and neither is a numeral
# that is merely the tail of a longer one.
_PROMISE_CJK_RX = re.compile(
    r"(?<![第几数上好近约0-9一二三四五六七八九十])([一二三四五六七八九十]{1,3})\s*[大个家款种位]")
# Japanese kanji-numeral promises: 十選 / 三つ / 五個 / 十社 (same lookbehind and the same floor below).
_PROMISE_JA_CJK_RX = re.compile(
    r"(?<![第几数上好近约約0-9０-９一二三四五六七八九十])([一二三四五六七八九十]{1,3})\s*(?:選|つ|個(?!月)|社)")
# "一个/两个" is how Chinese says "a" — only a count a list could plausibly promise counts here.
_CJK_PROMISE_FLOOR = 3
_CJK_DIGITS = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
               "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def _cjk_number(text: str):
    """一 … 九十九 as an int, or None. Listicle counts only — no 百/千 forms."""
    s = (text or "").strip()
    if not s:
        return None
    if "十" not in s:
        return _CJK_DIGITS.get(s) if len(s) == 1 else None
    head, _, tail = s.partition("十")
    tens = 1 if head == "" else _CJK_DIGITS.get(head)
    ones = 0 if tail == "" else _CJK_DIGITS.get(tail)
    if tens is None or ones is None:
        return None
    return tens * 10 + ones


def _promised_count(text: str, ja=None):
    """The count a heading promises, or None. Last match wins ('10大专家/Agency榜单' → 10).
    `ja` gates the Japanese-only branches (_PROMISE_JA_RX, _PROMISE_JA_CJK_RX): True/False when the
    article's language is known (rule_A8 passes it); None (callers without a language, e.g. the
    outline gate) reads the heading itself — kana in it means Japanese."""
    text = text or ""
    if ja is None:
        ja = bool(_KANA_RX.search(text))
    hits = [(m.end(), int(g)) for m in _PROMISE_RX.finditer(text) for g in m.groups() if g]
    cjk_rxs = [_PROMISE_CJK_RX]
    if ja:
        hits += [(m.end(), int(g)) for m in _PROMISE_JA_RX.finditer(text) for g in m.groups() if g]
        cjk_rxs.append(_PROMISE_JA_CJK_RX)
    for m in [mm for rx in cjk_rxs for mm in rx.finditer(text)]:
        n = _cjk_number(m.group(1))
        if n and n >= _CJK_PROMISE_FLOOR:
            hits.append((m.end(), n))
    return max(hits)[1] if hits else None


def count_numbered_entries(body: str) -> int:
    """Distinct numbered H3/H4 entries ("### 3. Tool") in a section body — THE definition of "an
    entry" that A8 checks and draft._h3_count mirrors (un-numbered sub-headings such as a per-entry
    "### Pros and Cons" are not entries)."""
    return len({int(m.group(1)) for m in _NUMBERED_H3.finditer(body or "")})


_H1_RX = re.compile(r"^#[ \t]+(\S.*?)\s*$", re.M)


def _document_h1(md: str) -> str:
    """The article's own first H1 line ('' if none). Used as the A8 title when cfg carries neither
    title nor h1 — the pipeline's lint_cfg never does, so the title-level count promise was dead."""
    in_fence = False
    for ln in (md or "").splitlines():
        if re.match(r"^\s*(?:```|~~~)", ln):
            in_fence = not in_fence
            continue
        if not in_fence:
            m = _H1_RX.match(ln)
            if m:
                return m.group(1).strip()
    return ""


def rule_A8_promised_count(sections, title, reports, ja=None):
    """BLOCKER: a heading promises N entries and the section delivers a different number.

    Only fires when the section actually uses numbered H3 entries — a promise answered by a table or
    by prose is not something this can count, and guessing there would be worse than silence.
    """
    for head, body in sections:
        want = _promised_count(head, ja)
        if not want:
            continue
        got = count_numbered_entries(body)
        if got and got != want:
            reports[0].violations.append(Violation(
                "A8", "blocker", head.lstrip("# ").strip()[:40] or "_document",
                f"heading promises {want}, section has {got} numbered entries",
                _t(f"标题承诺 {want} 项，本节实际只有 {got} 个编号条目——补齐条目或改标题数字",
                   f"the heading promises {want} entries but the section has {got}; "
                   f"write the missing ones or change the number in the heading")))
            return                                   # one report is enough; they share a cause
    # the H1/title promises a count that no section delivers as entries
    want = _promised_count(title or "", ja)
    if not want:
        return
    runs = [count_numbered_entries(b) for _, b in sections]
    got = max(runs) if runs else 0
    if got and got != want:
        reports[0].violations.append(Violation(
            "A8", "blocker", "_document", f"title promises {want}, longest entry run is {got}",
            _t(f"标题承诺 {want} 项，全文最长编号条目只有 {got} 个",
               f"the title promises {want} entries; the longest numbered run in the article is {got}")))


def rule_B1_hedges(head, body, rep, pack):
    hits = []
    for i, s in enumerate(split_sentences(body, pack)):
        for rx in pack.hedges:
            if rx.search(s):
                hits.append((i, s, rx.pattern))
    if len(hits) > 1:
        for i, s, w in hits[1:]:
            rep.violations.append(Violation("B1", "blocker", f"{head} sent#{i+1}",
                s[:80], _t(f"去掉模糊词「{w}」,改为确定性陈述或加明确条件", f"remove the hedge ‘{w}’; state it definitively or add an explicit condition")))

def rule_B2_vague_qty(head, body, rep, pack):
    for i, s in enumerate(split_sentences(body, pack)):
        m = pack.vague_qty.search(s)
        if m:
            rep.violations.append(Violation("B2", "warning", f"{head} sent#{i+1}",
                s[:80], _t(f"「{m.group(0)}」改为具体数字+单位", f"replace ‘{m.group(0)}’ with an exact number + unit")))

def rule_B3_modals(head, body, rep, pack):
    sents = split_sentences(body, pack)
    if not sents:
        return
    modal = sum(1 for s in sents if any(rx.search(s) for rx in pack.modals))
    ratio = modal / len(sents)
    if ratio > pack.modal_ratio_max:
        rep.violations.append(Violation("B3", "warning", head,
            f"modal ratio {ratio:.0%} ({modal}/{len(sents)})",
            _t(f"情态句占比超 {pack.modal_ratio_max:.0%}:事实陈述用直陈语气", f"too many modal sentences (>{pack.modal_ratio_max:.0%}); state facts in the indicative mood")))

# this/that/these/those are PRONOUNS only when they head the clause directly (followed by a verb/aux:
# "This is…", "These show…"). As DETERMINERS ("This comparison guide…", "These agencies…") they lead with
# a noun phrase and must NOT be flagged — otherwise the rewriter's natural "This <noun>…" opener can never
# clear the C1 blocker. it/they (and the zh demonstratives) are always pronouns, so they keep firing.
_DEMONSTRATIVE = {"this", "that", "these", "those"}
_PRONOUN_VERB_NEXT = re.compile(
    r"^(?:is|are|was|were|be|been|being|has|have|had|do|does|did|will|'ll|would|wo|shall|should|can|could|"
    r"may|might|must|ca|'s|'re|'ve|'d|seems?|means?|makes?|made|shows?|showed|works?|worked|helps?|helped|"
    r"allows?|allowed|provides?|provided|offers?|offered|includes?|included|requires?|required|ensures?|"
    r"creates?|created|gives?|gave|reflects?|represents?|indicates?|remains?|became?|becomes?|leads?|led|"
    r"results?|matters?|depends?|happens?|happened|occurs?|occurred|tends?|refers?|involves?)\b", re.I)

def rule_C1_para_start(head, body, rep, pack, entities):
    for i, p in enumerate(split_paragraphs(body)):
        if re.fullmatch(r"\[[^\]]+\]", p.strip()):
            continue
        sents = split_sentences(p, pack)
        first = sents[0] if sents else p
        m = pack.pronoun_start.match(first)
        # a demonstrative used as a determiner (followed by a noun, not a verb) is fine — not a pronoun start
        real_pronoun = bool(m) and not (
            m.group(1).lower() in _DEMONSTRATIVE
            and (rest := first[m.end():].lstrip()) and not _PRONOUN_VERB_NEXT.match(rest))
        if real_pronoun:
            rep.violations.append(Violation("C1", "blocker", f"{head} para#{i+1}",
                first[:80], _t("段首禁用代词开头,改为核心 entity 开头", "don't start a paragraph with a pronoun; lead with the core entity")))
        elif entities and not any(e.lower() in first.lower() for e in entities):
            rep.violations.append(Violation("C1", "warning", f"{head} para#{i+1}",
                first[:80], _t(f"段首句未含核心 entity({'/'.join(entities[:3])}…),首句应包含核心 entity",
                               f"the opening sentence lacks the core entity ({' / '.join(entities[:3])}…); embed it in the first sentence")))

def rule_C4_sentence_length(head, body, rep, pack):
    for i, s in enumerate(split_sentences(body, pack)):
        limit = pack.sentence_limit if not (pack.tokenizer == "space" and is_cjk(s)) else 45
        L = word_len(s, pack)
        if L > limit:
            rep.violations.append(Violation("C4", "warning", f"{head} sent#{i+1}",
                s[:80], _t(f"句长 {L} 超限 {limit},拆成两句", f"sentence too long ({L} words > {limit}); split it into two")))

def rule_C5_passive(head, body, rep, pack):
    sents = split_sentences(body, pack)
    if not sents:
        return
    passive = sum(1 for s in sents if pack.passive.search(s))
    ratio = passive / len(sents)
    if ratio > pack.passive_ratio_max:
        rep.violations.append(Violation("C5", "warning", head,
            f"passive ratio {ratio:.0%} ({passive}/{len(sents)})",
            _t(f"被动句占比超 {pack.passive_ratio_max:.0%},改为主动语态", f"too many passive sentences (>{pack.passive_ratio_max:.0%}); rewrite in the active voice")))

def rule_D3_heading_order(headings, brief, reports):
    if not brief:
        return
    doc = [norm_heading(h) for h, _ in headings if h != "_intro"]
    plan = [norm_heading(h) for h in brief]
    plan_set, doc_set = set(plan), set(doc)
    def _dedup(seq, keep):   # first occurrence only, in sequence order, restricted to `keep`
        seen, out = set(), []
        for h in seq:
            if h in keep and h not in seen:
                seen.add(h); out.append(h)
        return out
    # compare the SHARED headings in each side's order, deduped — a legitimately repeated H2 (e.g. "Pricing"
    # under two products) must not trip a bogus "order != brief" blocker just by appearing twice.
    if _dedup(doc, plan_set) != _dedup(plan, doc_set):
        reports[0].violations.append(Violation("D3", "blocker", "_document",
            "doc H2 order != brief order", _t("H2 顺序与 brief 不一致,恢复 brief 排序", "H2 order differs from the brief; restore the brief's order")))
    missing = [brief[i] for i, h in enumerate(plan) if h not in doc_set]
    if missing:
        reports[0].violations.append(Violation("D3", "blocker", "_document",
            f"missing headings: {missing}", _t("补齐 brief 规定但缺失的 H2", "add the H2 headings the brief requires but the draft is missing")))

def rule_D4_truncated_section(sections, brief, reports, empty_severity="blocker"):
    """D4 (document-level): catches a silently truncated LLM section-reply that no other rule sees.
    Two independent signals:
      1. an H2 with an EMPTY body — the per-section loop below (correctly) skips prose rules on
         nothing, but a content hole must still surface, never vanish silently. `empty_severity`
         (blocker by default) lets the caller downgrade this ONE signal to a warning: it's a hard
         blocker for the create-mode content gate (04, where a truncated section means the draft
         driver itself failed and must not proceed), but advisory for optimize-mode revise (no
         per-section retry loop to react to it) and the final re-verify on the assembled 06 (the
         post-assembly/hand-edit stage — the review-chat shrinkage guard already covers accidental
         elisions there, and a blocker would block Gate 3 on content a human already reviewed).
      2. a draft H2 that is a strict, truncated PREFIX (language-aware length floor, word-boundary-aware) of a
         brief-planned heading — the mid-word-cut case, where generation stopped inside the heading
         line itself. ALWAYS a blocker (independent of D3, whose blocker a reviewer can waive
         without noticing the heading was cut short — and unlike the empty-body signal, this one
         isn't specific to the create-mode retry loop). Skipped when the draft heading exactly
         matches ANY brief heading — a brief legitimately carrying both a short heading and a
         longer, related one (e.g. an overview H2 plus a deep-dive H2) is not a truncation."""
    for (head, body), rep in zip(sections, reports):
        if head != "_intro" and not body.strip():
            rep.violations.append(Violation("D4", empty_severity, head,
                "(empty section body)",
                _t(f"「{head}」正文为空——生成被截断,需重新生成该节",
                   f"the '{head}' section has an empty body — generation was truncated; regenerate it")))
    if not brief or not reports:
        return
    norm_brief_set = {norm_heading(b) for b in brief}
    brief_token_lists = [_heading_tokens(b) for b in brief]
    for head, _ in sections:
        if head == "_intro":
            continue
        ndh = norm_heading(head)
        # length floor before the prefix test — but language-aware: 15 normalized chars is tuned for
        # Latin scripts; a typical zh/ja H2 normalizes to 6-14 chars, so a flat 15 silently skipped
        # every CJK heading and made this signal inert for CJK articles (round 3).
        min_chars = 6 if _has_cjk(ndh) else 15
        if len(ndh) < min_chars or ndh in norm_brief_set:
            continue
        doc_tokens = _heading_tokens(head)
        if any(_is_truncated_heading(doc_tokens, bt) for bt in brief_token_lists):
            reports[0].violations.append(Violation("D4", "blocker", "_document",
                f"draft heading '{head}' looks truncated (a prefix of a longer brief heading)",
                _t(f"标题「{head}」疑似被截断(与 brief 中更长标题的前缀相同),需重新生成完整标题",
                   f"the heading '{head}' looks truncated — it's a prefix of a longer brief heading; regenerate the full heading")))


def rule_E2_cliches(head, body, rep, pack):
    for i, s in enumerate(split_sentences(body, pack)):
        for rx in pack.cliches:
            if rx.search(s):
                rep.violations.append(Violation("E2", "blocker", f"{head} sent#{i+1}",
                    s[:80], _t(f"AI 套话命中「{rx.pattern}」,删除或改写为具体陈述", f"AI cliché ‘{rx.pattern}’; delete it or rewrite as a concrete statement")))
                break

def rule_E3_para_length(head, body, rep, pack):
    for i, p in enumerate(split_paragraphs(body)):
        sents = split_sentences(p, pack)
        wl = word_len(p, pack)
        if len(sents) > pack.para_sent_limit or wl > pack.para_word_limit:
            rep.violations.append(Violation("E3", "warning", f"{head} para#{i+1}",
                p[:80], _t(f"段落 {len(sents)} 句/{wl} 词超限(≤{pack.para_sent_limit}句且≤{pack.para_word_limit}),拆分段落",
                           f"paragraph too long ({len(sents)} sentences / {wl} words; limit ≤{pack.para_sent_limit} sentences and ≤{pack.para_word_limit} words); split it")))

def rule_E4_placeholders(head, body, rep):
    for m in PLACEHOLDER_BAD.finditer(body):
        rep.violations.append(Violation("E4", "info", head, m.group(0),
            _t("占位符不规范,统一为 [IMG: 描述 | alt: …] / [TABLE: …] / [CITE]",
               "non-standard placeholder; use [IMG: description | alt: …] / [TABLE: …] / [CITE]")))


def _term_count(term, text):
    if _has_cjk(term):
        # casefolded AND boundary-guarded like serp2terms.count_term — the usage_ranges ceilings were
        # measured with (?<![a-z0-9])…(?![a-z0-9]) guards, so lint must count the same way or a term
        # like "ai检测" gets inflated by every "OpenAI检测" and trips G1d/G1e against a smaller ceiling
        pat = re.escape(term.lower()).replace(r"\ ", r"\s+")
        return len(re.findall(rf"(?<![a-z0-9]){pat}(?![a-z0-9])", text.lower()))
    # allow a trailing English plural on the term's last word so "alternatives" counts as containing
    # "alternative", "tools" as "tool", etc. (a term present in plural IS present — avoids G1a/G1b
    # false negatives on natural plural H1s/keywords). e?s? matches "", "s", "es".
    # boundaries reject only an adjacent ASCII alphanumeric — NOT \b: CJK chars are \w, so \b never fires
    # between "用" and "ChatGPT" and every Latin term inside zh/ja/ko prose counted 0 (false G1b/G1e, dead G1d)
    return len(re.findall(r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?:e?s)?(?![A-Za-z0-9])", text, re.I))

def _stem(w: str) -> str:
    # crude singular→plural normalizer so an INTERNAL inflection still matches: agencies↔agency,
    # mothers↔mother, boxes↔box. _term_count's regex only tolerates a trailing plural on the last word.
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"                              # agencies→agency, categories→category
    if len(w) > 4 and w.endswith("es") and w[-3] in "sxzoh":
        return w[:-2]                                    # boxes→box, heroes→hero, matches→match
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]                                    # mothers→mother, agencys→agency
    return w

_PRESENCE_FILLER = {"a", "an", "the", "your", "my", "our", "its", "their", "his", "her",
                    "this", "that", "these", "those"}

def _term_present(term, text) -> bool:
    """Inflection- and filler-tolerant phrase containment: the term's words must appear in order, modulo
    singular/plural AND modulo short filler words (articles/possessives/demonstratives) the writer naturally
    inserts. So a keyword-style entity 'how to make essay pass turnitin' is satisfied by the natural H1
    'How to Make an Essay Pass Turnitin' (inserted 'an'), and a pluralized H1 ('…agencies…') satisfies a
    singular entity ('…agency…'). Only filler may be skipped between content words — a content-word gap
    still fails (the phrase must be essentially contiguous). Punctuation/case/markdown are stripped by the
    tokenizer. Used for presence checks (G1a) where 0-vs-≥1 is what matters; _term_count keeps its exact
    count semantics for coverage/stuffing."""
    if _has_cjk(term):
        return term.lower() in text.lower()
    # keep tech-brand symbols attached to their token (C#, C++, AT&T, .NET) — a bare [a-z0-9]+ dropped
    # them, so 'C#' and 'C' both tokenized to ['c'] and G1a passed on the wrong headline variant
    _TOK = r"[a-z0-9]+(?:[#+&.][a-z0-9]*)*"
    tt = [_stem(w) for w in re.findall(_TOK, term.lower())]
    xraw = re.findall(_TOK, text.lower())
    xt = [_stem(w) for w in xraw]
    if not tt:
        return False
    n = len(tt)
    for start in range(len(xt)):
        i, j = start, 0
        while i < len(xt) and j < n:
            if xt[i] == tt[j]:
                i += 1; j += 1
            elif j > 0 and xraw[i] in _PRESENCE_FILLER:   # skip an inserted article/possessive INSIDE the run
                i += 1
            else:
                break
        if j == n:
            return True
    return False

def rule_A7_if_order(head, body, rep, pack):
    """A7: 主句在前,if 条件在后 — flag sentence-initial conditionals"""
    for i, s in enumerate(split_sentences(body, pack)):
        if any(rx.search(s) for rx in pack.if_starters):
            rep.violations.append(Violation("A7", "warning", f"{head} sent#{i+1}",
                s[:80], _t("条件句倒装:主句声明放前,if/如果 条件放后", "invert the conditional: put the main declaration first, the if-clause second")))

def rule_C6_generic_verbs(head, body, rep, pack):
    """C6: 通用动词上限 — flag sections overusing make/do/get/进行/做好"""
    sents = split_sentences(body, pack)
    hits = sum(len(rx.findall(s)) for s in sents for rx in pack.generic_verbs)
    if hits > 3:
        rep.violations.append(Violation("C6", "warning", head,
            f"generic verbs ×{hits}", _t("通用动词过多:换成行业精确谓词(diagnose/deploy/抓取/索引…)", "too many generic verbs; use context-specific predicates (diagnose, deploy, index…)")))

BURSTINESS_MIN_COV = 0.40   # σ/μ of sentence word-counts below this = too uniform (AI-detection signal)

def rule_C7_burstiness(head, body, rep, pack):
    """C7: 句长节奏(burstiness)— AI 文本句长过于均匀;人写长短句交错。低变异度 = AI 检测信号。
    Flags a section whose sentence lengths are too uniform (low burstiness). Warning; rewrite-loop fixable."""
    lengths = [L for s in split_sentences(body, pack) if (L := word_len(s, pack)) > 0]
    if len(lengths) < 5:                      # too few sentences to judge rhythm
        return
    mean = sum(lengths) / len(lengths)
    if mean <= 0:
        return
    cov = (sum((x - mean) ** 2 for x in lengths) / len(lengths)) ** 0.5 / mean
    short = sum(1 for x in lengths if x <= 8)
    # low coefficient-of-variation = uniform rhythm (the AI signal). A section can be bursty without any
    # ultra-short sentence, so short-count is reported as evidence but does NOT trigger on its own.
    if cov < BURSTINESS_MIN_COV:
        rep.violations.append(Violation("C7", "warning", f"{head} ({len(lengths)} sents)",
            f"avg {mean:.0f}w σ/μ={cov:.2f} short≤8w×{short}",
            _t("句长过于均匀(低 burstiness = AI 检测信号)——长短句交错:穿插几句 ≤8 词的短句、保留几句长句",
               "sentences too uniform (low burstiness, an AI-detection signal); vary the rhythm — interleave a "
               "few short punchy sentences (≤8 words) with longer ones")))

def rule_E5_transitions(head, body, rep, pack):
    """E5: 日常转场词 — flag sentence-initial transition words"""
    for i, s in enumerate(split_sentences(body, pack)):
        for rx in pack.transitions:
            if rx.search(s):
                rep.violations.append(Violation("E5", "warning", f"{head} sent#{i+1}",
                    s[:60], _t("删除日常转场词,用实体/逻辑衔接", "cut the everyday transition word; connect via a shared entity or logic")))
                break

BOLD_RX = re.compile(r"\*\*([^*\n]{1,80})\*\*")
MD_LINK_RX = re.compile(r"\[([^\]\n]{1,120})\]\(([^)\s]+)\)")

def rule_F1_bold_query(md, sections, reports, term_lists, brief):
    """F1: bold 必须打在答案上,不能打在 query/heading/中心词本身"""
    rep = reports[0]
    tl = term_lists or {}
    # the "query" you must not bold is the central entity OR the primary keyword (both are the query, not an answer)
    queries = {norm_heading(q) for q in (tl.get("central_entity", ""), tl.get("primary_keyword", "")) if q}
    heads = {norm_heading(h) for h in (brief or [])} | {norm_heading(h) for h, _ in sections}
    for m in BOLD_RX.finditer(md):
        t = m.group(1).strip()
        if norm_heading(t) in queries or norm_heading(t) in heads:
            rep.violations.append(Violation("F1", "warning", "_document",
                f"**{t}**", _t("bold 打在了 query/heading 上;应只加粗具体的事实答案值", "bold is on the query/heading; bold only the factual answer value, not the query")))

def rule_F3_link_first_word(head, body, rep):
    """F3: 段落第一个词禁止是链接"""
    for i, p in enumerate(split_paragraphs(body)):
        if p.lstrip().startswith("["):
            m = MD_LINK_RX.match(p.lstrip())
            if m:
                rep.violations.append(Violation("F3", "blocker", f"{head} para#{i+1}",
                    p[:60], _t("段首第一个词不能是链接:先用正文定义概念,链接后置", "never link the first word of a paragraph; define the concept in prose first, place the link later")))

def rule_F5_anchor_repetition(md, reports):
    """F5: 相同锚文本指向同一页面 ≤ 3 次"""
    rep = reports[0]
    pairs = {}
    for m in MD_LINK_RX.finditer(md):
        key = (m.group(1).strip().lower(), m.group(2).strip().lower())
        pairs[key] = pairs.get(key, 0) + 1
    for (anchor, url), n in pairs.items():
        if n > 3:
            rep.violations.append(Violation("F5", "blocker", "_document",
                f"[{anchor}]({url}) ×{n}",
                _t(f"相同锚文本指向同一页面 {n} 次(上限 3):换用锚文本变体", f"the same anchor text points to the same page {n} times (limit 3); vary the anchor text")))

def _untranslatable_demand(term: str, pack, primary_keyword: str = "", central_entity: str = "") -> bool:
    """True when a term list demands an ENGLISH literal a non-English article has no reason to carry.

    The L2 attribute list is measured off the live Top-10, and for a Chinese keyword whose SERP is
    mostly English pages that list arrives in English: engine, digital, optimization, generative.
    A Chinese article covers those concepts in Chinese — 引擎 ×50, 优化 ×18 in saas-geo-10-agency —
    and got 37 under-coverage warnings anyway, which is most of the noise in its report and drowns
    the findings that are real.

    Proper nouns and acronyms survive translation (ChatGPT, SaaS, GEO, B2B stay Latin in Chinese
    prose), so anything the article's own keyword or central entity uses is still demanded. What is
    dropped is a generic English word in a CJK article — where absence proves nothing.
    """
    if pack.tokenizer != "char" or _has_cjk(term):
        return False                       # English article, or a CJK term — check it normally
    ctx = f"{primary_keyword} {central_entity}".lower()
    return not any(w and w in ctx for w in term.lower().split())


def rule_G1_term_coverage(md, sections, reports, pack, term_lists):
    """G1: 三层词项覆盖 — L1 位置 / L2 覆盖率 / L3 出现 / stuffing 上限"""
    if not term_lists:
        return
    rep = reports[0]
    full = md
    ce = term_lists.get("central_entity")
    # Headline target vs topical hub (the central_entity role split): the H1 must carry the PRIMARY KEYWORD
    # (what the page ranks for — a long-tail phrase), while the CENTRAL ENTITY is the short topical hub used
    # for the first-sentence anchor + coverage/drift. When no primary_keyword is threaded (e.g. standalone
    # lint runs / golden tests), fall back to central_entity so behaviour is unchanged.
    pk = (term_lists.get("primary_keyword") or "").strip() or ce

    # G1a (blocker): H1 must contain the primary keyword; first body sentence must contain the central
    # entity. Presence is inflection- + filler-tolerant (_term_present) — a pluralized H1 ("…agencies…")
    # satisfies a singular term, and inserted articles ("make AN essay pass") don't break the match.
    if pk:
        h1 = next((l for l in md.splitlines() if l.startswith("# ")), "")
        if not _term_present(pk, h1):
            rep.violations.append(Violation("G1a", "blocker", "_title",
                h1[:80] or "(no H1)", _t(f"H1 必须含 primary keyword「{pk}」", f"the H1 must contain the primary keyword ‘{pk}’")))
    if ce:
        intro_body = next((b for h, b in sections if h == "_intro" and b.strip()), "")
        first_sents = split_sentences(intro_body, pack)
        if first_sents and not _term_present(ce, first_sents[0]):
            rep.violations.append(Violation("G1a", "blocker", "_intro sent#1",
                first_sents[0][:80], _t(f"首段第一句必须含 central entity「{ce}」", f"the first sentence must contain the central entity ‘{ce}’")))

    # G1b (warning): L2 attributes — coverage + correct section placement
    attrs = term_lists.get("attributes", {})
    if attrs:
        sec_map = {norm_heading(h): b for h, b in sections}
        missing, misplaced = [], []
        for term, target in attrs.items():
            if _term_count(term, full) == 0:
                missing.append((term, target))
            elif target:
                body = sec_map.get(norm_heading(target), "")
                if _term_count(term, body) == 0:
                    misplaced.append((term, target))
        covered = len(attrs) - len(missing)
        coverage = covered / len(attrs)
        if coverage < 0.80:
            rep.violations.append(Violation("G1b", "warning", "_document",
                f"L2 coverage {coverage:.0%} ({covered}/{len(attrs)}), missing: {[t for t,_ in missing]}",
                _t("属性词覆盖率 <80%,在对应 section 补入缺失词项", "attribute-term coverage <80%; add the missing terms in their sections")))
        for term, target in misplaced:
            rep.violations.append(Violation("G1b", "warning", f"section:{target}",
                f"「{term}」出现在全文但不在目标节", _t(f"把「{term}」移入或补充到《{target}》节", f"move or add ‘{term}’ into the ‘{target}’ section")))

    # G1c (info): L3 cooccurrence terms
    cooc = term_lists.get("cooccurrence", [])
    miss3 = [t for t in cooc if _term_count(t, full) == 0]
    if miss3:
        rep.violations.append(Violation("G1c", "info", "_document",
            f"missing co-occurrence terms: {miss3}",
            _t("共现词项未覆盖(各出现 1 次即可,勿堆砌)", "co-occurrence terms not covered; include each once, naturally (don't stuff)")))

    # G1e (warning): per-term usage range from Cora competitor data
    ranges = term_lists.get("usage_ranges", {})
    for term, r in ranges.items():
        occ = _term_count(term, full)
        lo, hi = r.get("min", 0), r.get("max", 10**9)
        if occ > hi:
            rep.violations.append(Violation("G1e", "warning", "_document",
                f"「{term}」×{occ} > Top10 上限 {hi}",
                _t(f"「{term}」用量超 Top 10 实测天花板,有 stuffing 风险:删减或换变体", f"‘{term}’ exceeds the measured Top-10 ceiling (stuffing risk); reduce below {hi} or use variants")))
        elif (0 < lo and occ < lo and term in term_lists.get("attributes", {})
              and not _untranslatable_demand(term, pack, pk, ce)):
            rep.violations.append(Violation("G1e", "warning", "_document",
                f"「{term}」×{occ} < 下限 {lo}",
                _t(f"L2 属性词「{term}」覆盖不足(Top 10 实测至少 {lo} 次)", f"L2 attribute ‘{term}’ is under-covered (Top-10 pages use it at least {lo}×); increase coverage")))

    # G1d (warning): stuffing guard — central entity > max_per_100 per 100 words
    if ce:
        total_words = word_len(full, pack)
        occ = _term_count(ce, full)
        max_per_100 = term_lists.get("max_per_100", 4)
        if total_words > 0 and occ / (total_words / 100) > max_per_100:
            rep.violations.append(Violation("G1d", "warning", "_document",
                f"「{ce}」{occ} 次 / {total_words} 词 = {occ/(total_words/100):.1f}/100词,上限 {max_per_100}",
                _t("频次超上限,有 stuffing 风险:用自然变体或代回指替换部分出现", "frequency over the cap (stuffing risk); replace some mentions with natural variants or pronouns")))

# ── H1: under-promotion warning (inverse of the Task-5 over-promotion guard) ──
# brand_guard.py REFUSES to package a draft that recommends the brand too hard for its level.
# H1 is the mirror: when an article DECLARES brand_push >= 2 (the brand should be recommended) but
# the brand never makes it into the copy, warn the reviewer "you said push the brand but it isn't here."
# WARNING only — under-promotion is a quality miss, not a packaging blocker.

def under_promotion_warning(md: str, brand_push, brand_terms: list) -> str | None:
    """PURE: return a warning message if the brand SHOULD be recommended (brand_push >= 2) but no
    brand term appears in the body; else None. Returns None when brand_push < 2 (not checked) or when
    there are no brand terms to look for (can't judge). Non-int brand_push coerces to 0 (no check)."""
    try:
        brand_push = int(brand_push)
    except (TypeError, ValueError):
        brand_push = 0
    if brand_push < 2:
        return None
    terms = [t for t in (brand_terms or []) if t]
    if not terms:
        return None
    body = md or ""
    low = body.lower()
    if any(t.lower() in low for t in terms):
        return None
    return (f"declared brand_push L{brand_push} but no brand recommendation found in the body "
            f"(no brand term {terms[:3]} appears) — add the brand placement the level calls for")


def rule_H1_under_promotion(md, ctx, reports):
    """H1 (warning): article declares brand_push >= 2 but never recommends the brand.
    Reads brand_push from the lint config (same channel as entities/brief_headings/term_lists —
    all sourced from 02-context.json by the pipeline). Resolves brand terms from the first brand
    kit (kit_io.load_first_kit + brand_guard.brand_terms_from_kit), the same convention draft.py/
    brief.py and the package-step guard use. No kit / no brand terms → can't check → no-op."""
    brand_push = (ctx or {}).get("brand_push", 0) or 0
    try:
        from kit_io import load_first_kit
        from brand_guard import brand_terms_from_kit
        brand_terms = brand_terms_from_kit(load_first_kit(Path(".")))
    except Exception:
        brand_terms = []
    msg = under_promotion_warning(md, brand_push, brand_terms)
    if msg:
        reports[0].violations.append(Violation("H1", "warning", "_document",
            f"brand_push L{brand_push}, brand absent from body", msg))


# ═══════════════════════ runner ═══════════════════════

PASS_RATE_THRESHOLD = 0.80
# ── E7: unsourced factual quantity (anti-hallucination DET rule) ──
# 原则:模型不是数字的来源。带计量单位的数字断言必须在本句或相邻句带来源标注
# ([CITE]/[N]/括号来源/according to/per X/on|at|from|by + 专名),否则视为疑似编造。
# 结构性计数(3 steps / 4 种)不带单位,不在此规则范围内。
# two families: word units keep a trailing \b (so "millionaire" ≠ "million"); the % symbol and CJK units
# do NOT — a \b after "%" or a CJK char requires a word→non-word flip that "43% of"/"30秒内" never has,
# which silently disabled the rule on the single most common fabricated-stat form (percentages).
_QTY_CJK_UNITS = ("%", "亿", "百万", "千万", "万亿", "秒", "分钟", "小时", "美元", "欧元", "积分", "像素")
_QTY_LATIN_UNITS = ("percent", "billion", "million", "trillion", "seconds?", "minutes?", "hours?",
                   "credits?", "pixels?", "px", "Elo", "USD", "EUR")
_E7_QTY = re.compile(
    r"(?:[$¥€]\s?\d[\d,.]*)|"
    rf"\d[\d,.]*\s*(?:{'|'.join(_QTY_CJK_UNITS)})|"
    rf"\d[\d,.]*\s*(?:{'|'.join(_QTY_LATIN_UNITS)})\b", re.I)
# case handling is deliberate: "according to"/"per" tolerate a sentence-initial capital ONLY
# ("According to Turnitin, 43%…" is attributed — flagging it was a false positive), while the
# [A-Z] after per/on/at/from/by stays strict — it means "followed by a proper noun", and a
# blanket re.I would turn every "from a"/"by the" into a source marker.
_E7_SOURCED = re.compile(
    r"\[CITE\]|\[N\]|[Aa]ccording to|数据来自|来源|报告|《[^》]+》|"
    r"\b[Pp]er\s+[A-Z]|\b(?:on|at|from|by)\s+[A-Z]|"
    r"\([^)]*[A-Za-z一-鿿]{2}[^)]*\)")

def _qty_match(s: str, pack: Pack, base_rx):
    """First quantity in `s`: the shared net `base_rx` first, then the pack's own e7_qty. A match
    inside a count announcement (pack.e7_announce — ja "次の3件を紹介します") is a list size, skipped."""
    for rx in (base_rx, pack.e7_qty):
        for m in (rx.finditer(s) if rx else ()):
            if pack.e7_announce and any(a.start() <= m.start() and m.end() <= a.end()
                                        for a in pack.e7_announce.finditer(s)):
                continue
            return m
    return None


def rule_E7_unsourced_qty(head, body, rep, pack, stats_active=False):
    """`stats_active` (statistics pages with a usable registry ONLY — statgather.stats_contract_active):
    also accept an unresolved [STAT:id] marker or an already-resolved "**value** (...)" form as
    sourcing, so E7 doesn't double-flag a number ST1 already governs. Off a statistics page (or one
    whose registry has nothing usable, so the draft never emitted [STAT:] markers in the first
    place), E7 keeps its ORIGINAL net — literal "[STAT:" text appearing on an ordinary page is not a
    real source marker and must still be flagged like any other unsourced figure."""
    sents = split_sentences(body, pack)
    for i, s in enumerate(sents):
        m = _qty_match(s, pack, _E7_QTY)
        if not m:
            continue
        window = " ".join(sents[max(0, i - 1):i + 2])
        if pack.e7_noise:
            window = pack.e7_noise.sub(" ", window)
        if _E7_SOURCED.search(window) or (pack.e7_sourced and pack.e7_sourced.search(window)):
            continue
        if stats_active and (_SG.MARKER_RE.search(window) or _SG.RESOLVED_STAT_RE.search(window)):
            continue
        rep.violations.append(Violation("E7", "warning", f"{head} sent#{i+1}",
            s[:80], _t(f"数字断言「{m.group(0)}」无来源标注——补 [CITE]/[N]/括号来源,或删除该数字",
                       f"the quantity claim ‘{m.group(0)}’ lacks a source marker; add [CITE]/[N]/(source) or remove the number")))

# ── ST1/ST2/ST3: statistics-page rules (docs/plans/2026-07-21-statistics-articles.md Task 8) ──
# Active only when statgather.stats_contract_active(page_type, registry) is True — a page_type
# where numeric density INVERTS (the numbers ARE the content) and [CITE]/[N] are retired in favor
# of [STAT:id] registry markers, AND the registry actually has something usable to reference (else
# brief/draft fell back to the standard contract and ST1 would blocker-fail every ordinary number).
# _ST1_QTY is COMPOSED from _E7_QTY's own shared unit lists plus stats-specific extras (bare
# 万-scale figures and ratio "x"/倍 multipliers — the CJK scale words a derived-stat article
# commonly states) — not a separately-maintained copy, so a future edit to _QTY_CJK_UNITS/
# _QTY_LATIN_UNITS (e.g. widening what E7 recognizes) can never leave ST1 with a weaker net.
_ST1_EXTRA_CJK = ("万", "倍", "个月", "年", "条", "次")
_ST1_EXTRA_LATIN = ("times?", "x")
_ST1_QTY = re.compile(
    r"(?:[$¥€]\s?\d[\d,.]*)|"
    rf"\d[\d,.]*\s*(?:{'|'.join(_QTY_CJK_UNITS + _ST1_EXTRA_CJK)})|"
    rf"\d[\d,.]*\s*(?:{'|'.join(_QTY_LATIN_UNITS + _ST1_EXTRA_LATIN)})\b", re.I)


def _table_rows(body: str):
    """Yield (header_cells, data_cells) for each markdown table row in body — a line-based parse
    (matching TC1's existing convention, not a full GFM parser). The delimiter row (|---|:--:|) is
    skipped; a blank/non-table line ends the current table so a NEW header is captured next time."""
    header = None
    for line in body.split("\n"):
        s = line.strip()
        if not s.startswith("|"):
            header = None
            continue
        if re.fullmatch(r"[\s:|-]+", s):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if header is None:
            header = cells
            continue
        yield header, cells


def rule_ST1_unmarked_number(head, body, rep, pack):
    """ST1 (blocker, statistics pages only): a numeric claim with no [STAT:id] marker (or an
    already-RESOLVED "**value** (...)" form, for a re-lint of the assembled article) in the SAME
    sentence or table cell — tightened from a ±1-sentence window, which missed a second unmarked
    figure sitting in a neighboring sentence of a marked one. Prose: split_sentences already
    excludes headings, list items, table rows, and blockquotes, so a year in a heading or an
    ordinal list marker never reaches this scan. Tables: every numeric, non-Source column cell
    must itself carry a marker or resolved form — split_sentences drops table rows entirely, so
    without this a stats-table cell could ship an unmarked figure invisibly."""
    sents = split_sentences(body, pack)
    for i, s in enumerate(sents):
        m = _qty_match(s, pack, _ST1_QTY)   # ja units: 億円/万人/…
        if not m:
            continue
        if _SG.MARKER_RE.search(s) or _SG.RESOLVED_STAT_RE.search(s):
            continue
        rep.violations.append(Violation("ST1", "blocker", f"{head} sent#{i+1}",
            s[:80], _t(f"数字「{m.group(0)}」缺少 [STAT:id] 标注——统计页面的每个数字都必须来自已核实的登记表",
                       f"the figure '{m.group(0)}' has no [STAT:id] marker — on a statistics page every "
                       f"number must trace to a verified stat-registry entry")))
    for header, cells in _table_rows(body):
        for ci, cell in enumerate(cells):
            col = header[ci] if ci < len(header) else ""
            if re.search(r"source", col, re.I):
                continue
            m = _qty_match(cell, pack, _ST1_QTY)
            if not m:
                continue
            if _SG.MARKER_RE.search(cell) or _SG.RESOLVED_STAT_RE.search(cell):
                continue
            rep.violations.append(Violation("ST1", "blocker", f"{head} table row",
                cell[:80], _t(f"表格单元格数字「{m.group(0)}」缺少 [STAT:id] 标注",
                              f"the table figure '{m.group(0)}' has no [STAT:id] marker — on a "
                              f"statistics page every number must trace to a verified stat-registry entry")))


# (ja equivalents appended: 方法論/調査方法, 出典/参考文献/情報源, 最終更新/更新日 — the zh forms are
# simplified characters, so 出典 / 最終更新 / 方法論 were invisible to this rule)
_ST2_METHODOLOGY_H = re.compile(r"methodology|方法论|方法論|調査方法", re.I)
_ST2_SOURCES = re.compile(r"sources?|references?|来源|参考|出典|情報源", re.I)
_ST2_LAST_UPDATED = re.compile(r"last[\s-]?updated|updated on|最后更新|更新[于时]|最終更新|更新日", re.I)


def rule_ST2_required_sections(sections, reports):
    """ST2 (blocker, statistics pages only): a statistics article must carry a Methodology H2, a
    sources/references mention, and a last-updated stamp — the backlink-magnet's minimum trust
    signals. Checked article-wide (not per-section) since these are document-level requirements."""
    if not reports:
        return
    headings = [h for h, _ in sections if h != "_intro"]
    whole_text = "\n".join(b for _, b in sections)
    missing = []
    if not any(_ST2_METHODOLOGY_H.search(h) for h in headings):
        missing.append("a 'Methodology' H2 section")
    if not (any(_ST2_SOURCES.search(h) for h in headings) or _ST2_SOURCES.search(whole_text)):
        missing.append("a sources/references list")
    if not _ST2_LAST_UPDATED.search(whole_text):
        missing.append("a last-updated line")
    if missing:
        reports[0].violations.append(Violation("ST2", "blocker", "_document",
            f"missing: {missing}",
            _t(f"统计页面缺少必需元素:{'; '.join(missing)}",
               f"missing required statistics-page element(s): {'; '.join(missing)}")))


def rule_ST3_headline_stats_unreferenced(md, reports, cfg):
    """ST3 (warning, statistics pages only) — the INVERSE of ST1: a headline usable stat (one of a
    chart spec's stat_ids, or one of the first 5 usable registry entries when no chart exists) that
    is never referenced anywhere in the body — by its [STAT:id] marker OR (on an already-assembled
    article) its resolved bold value. These are the numbers the page exists to publish; a headline
    stat nobody cites is a wasted (or mis-drafted) asset."""
    registry = cfg.get("stat_registry")
    verified = _SG.usable_stats(registry)
    if not verified or not reports:
        return
    chart_ids = {i for c in (registry.get("charts") or []) for i in (c.get("stat_ids") or [])}
    headline = [s for s in verified if s["id"] in chart_ids] or verified[:5]
    for s in headline:
        marker_hit = re.search(rf"\[STAT\s*:\s*{re.escape(s['id'])}\s*\]", md)
        resolved_hit = s.get("value") and re.search(r"\*\*" + re.escape(s["value"]) + r"\*\*", md)
        if marker_hit or resolved_hit:
            continue
        reports[0].violations.append(Violation("ST3", "warning", "_registry",
                f"{s['id']}: {s['metric']} = {s['value']}",
                _t(f"重点统计数据 {s['id']}({s['metric']})从未在正文中引用——考虑加入 [STAT:{s['id']}]",
                   f"headline stat {s['id']} ({s['metric']}) is never referenced in the body — "
                   f"consider citing [STAT:{s['id']}] in Key Takeaways or a relevant section")))

# ── E8: zh 文本 ASCII 引号(排版规范 + 下游安全)──
# 中文内容里用 ASCII 直引号包中文("秒排名")既不合中文排版规范,又曾让 judge 把原文抄进
# evidence 时产生系统性坏 JSON(每次重试都崩)。只flag引号内含 CJK 的情况 —— 引英文词组
# ("guest post")常见且无害,不flag。修法:改用「」或""(全角)。
_CODE_SPAN = re.compile(r"`[^`\n]+`")

def rule_E8_ascii_quotes(head, body, rep, pack):
    if pack.tokenizer != "char":
        return                                   # 仅 CJK 语言检查
    # v2: (a) 跳过代码围栏与行内代码(ASCII 引号在代码里是语法必需——JSON 示例被自动修复换成「」会直接损坏);
    # (b) 逐行按引号配对取"引号内"片段,只有片段含 CJK 才flag——旧正则会把两段合法英文引号之间的中文
    # (…"guest post" 和 "link exchange"…) 误配成一对引号。
    in_fence = False
    for ln in body.splitlines():
        if re.match(r"^\s*(?:```|~~~)", ln):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        parts = _CODE_SPAN.sub("", ln).split('"')
        for k in range(1, len(parts) - 1, 2):    # odd indices = inside a complete quote pair
            seg = parts[k]
            if len(seg) <= 40 and any(_is_cjk_char(c) for c in seg):
                rep.violations.append(Violation("E8", "warning", head, f'"{seg[:36]}"',
                    _t("中文内容改用「」或“”全角引号,不用 ASCII 直引号",
                       f"use CJK quotes 「」/“” around {'Japanese' if _FIX_LANG.startswith('ja') else 'Chinese'} "
                       f"text, not ASCII straight quotes")))


# ── E9: "surrender sentences" — prose that BAKES THE ABSENCE of the datum into the shipped text
# while still carrying [N]/[CITE]. Example from buzzy-now-vs-higgsfield-ai:
#   "Pricing details for Buzzy AI's subscription tiers are [N] [CITE] at the time of writing, so a
#    direct per-clip cost comparison is not possible here."
# Two independent reasons this can NEVER be resolved downstream, which is why it's a blocker here
# (at 04, where the rewrite loop can still fix it) rather than a Gate-3 surprise:
#   1. citations.py's serp_query strips the markers and searches what's left — i.e. it searches the
#      EXCUSE ("…so a direct per-clip cost comparison is not possible here"), never the price → junk
#      SERP → no_source → the marker survives to Gate 3, where the placeholder gate hard-blocks it.
#   2. Even a SUCCESSFUL fill is self-contradicting: "…are $19/mo at the time of writing, so a direct
#      comparison is not possible here."
# The fix is always a re-draft (fill from the 01d roster, or drop the claim) — never a source hunt.
# Family A = phrases inherently ABOUT the datum/verification, safe to flag on their own.
# NOTE the negation is REQUIRED, not optional: an earlier "(?:not\s+)?be\s+verified" also matched the
# positive "the figure CAN BE VERIFIED on the vendor page", which would have blocker-failed a
# perfectly good sentence and sent the rewrite loop after it.
_E9_SURRENDER_A = re.compile(
    r"(?:comparison|calculation|breakdown|figures?|numbers?)\s+(?:is|are)\s+not\s+possible"
    r"|not\s+possible\s+(?:to\s+)?(?:compare|calculate|determine|verify)"
    r"|(?:cannot|can\s*n[o']t|could\s*n[o']t|can\s+not|could\s+not|couldn|wasn[o']?t\s+able\s+to)"
    r"\s*(?:be\s+)?(?:verified|confirmed|determined|compared|calculated|sourced|verify|confirm)"
    r"|无法(?:比较|对比|确认|核实|计算|获取|得知)"
    r"|未(?:公开|披露|公布|标明)"
    r"|暂无(?:公开)?(?:数据|价格|资料|信息)"
    # Japanese: 非公開 / 公表されていません (+ 公開/開示/明記 and いない/おりません) / 比較できません …
    r"|非公開"
    r"|(?:公表|公開|開示|明記)されて(?:いません|おりません|いない)"
    r"|(?:比較|確認|算出|計算|特定|検証)(?:することが)?でき(?:ません|ない)", re.I)
# Family A2 = "the vendor doesn't publish it". Reads like family A but the wording is also ordinary
# English about non-data subjects ("the study was not published until 2024" is a real, citable
# claim), so it needs a data noun SOMEWHERE in the sentence — the noun often follows the verb
# ("does not publish its per-clip cost"), so precedence is not required here.
_E9_SURRENDER_A2 = re.compile(
    r"not\s+(?:publicly\s+)?(?:disclosed|published|documented|advertised)"
    r"|(?:does|do)\s*n[o']?t\s+(?:publicly\s+)?(?:publish|disclose|list)"
    r"|no\s+(?:publicly\s+available\s+|public\s+)(?:pricing|price|cost|data|figures?|information|breakdown)", re.I)
# Family B = ambiguous absence wording ("not available" can mean the PRODUCT is unavailable in a
# region, which is a legitimate factual claim). Only a surrender when the sentence is talking about
# the datum itself, so require a data noun in the same sentence.
_E9_SURRENDER_B = re.compile(
    r"not\s+(?:currently\s+|publicly\s+)?available"
    r"|unavailable|undisclosed|unclear|not\s+(?:specified|stated|listed|known)", re.I)
# Deliberately NARROW: only nouns naming the DATUM itself. "tier"/"plan"/"credits" are PRODUCT
# nouns — including them made "the free tier is not available in the EU" (a legitimate availability
# fact sitting beside an ordinary placeholder) trip the rule.
_E9_DATA_NOUN = re.compile(
    r"pricing|prices?|costs?|details?|data|figures?|information|allowances?"
    r"|numbers?|rates?|specs?|breakdown"
    r"|价格|费用|数据|资料|额度|信息", re.I)


def rule_E9_surrender_placeholder(head, body, rep, pack):
    """E9 (blocker): a [N]/[CITE] sentence that also ASSERTS the datum is unavailable/uncomparable.
    Unresolvable by stage 5.5b by construction — must be re-drafted, not sourced."""
    for i, s in enumerate(split_sentences(body, pack)):
        if "[N]" not in s and "[CITE]" not in s:
            continue
        hit = _E9_SURRENDER_A.search(s)
        if not hit:
            m2 = _E9_SURRENDER_A2.search(s)
            hit = m2 if (m2 and _E9_DATA_NOUN.search(s)) else None
        if not hit:
            m = _E9_SURRENDER_B.search(s)
            # the data noun must SUBJECT the absence (appear before it), not merely co-occur —
            # "…the paid plan starts at [N] per month" must not license a flag on an unrelated
            # "not available" earlier in the same sentence.
            hit = m if (m and _E9_DATA_NOUN.search(s[:m.start()])) else None
        if not hit:
            continue
        rep.violations.append(Violation("E9", "blocker", f"{head} sent#{i+1}", s[:120],
            _t(f"该句一边留占位符、一边宣称数据不可得(「{hit.group(0)}」)——取源阶段永远修不了它:"
               f"5.5b 会拿这句「借口」去搜索。请改写:用 01d 榜单里的真实数字填上,或整句删掉该断言。",
               f"this sentence carries a placeholder AND asserts the datum is unavailable "
               f"(‘{hit.group(0)}’) — stage 5.5b can never resolve it (it searches the excuse, not "
               f"the value). Re-draft: fill the real figure from the 01d roster, or drop the claim "
               f"entirely. Do not simply delete the marker.")))


def _tc_key(s: str) -> str:
    """Fold a value/row to a match key: lowercase, non-alphanumeric runs → single spaces."""
    return re.sub(r"[^0-9a-z]+", " ", (s or "").lower()).strip()


def rule_TC1_table_cell_provenance(sections, cfg, reports):
    """TC1: a third-party figure that came from the deep-research roster (01d) and appears in a
    comparison-table cell must carry its source pill ([…](url)) somewhere in that row — the draft
    collapses same-source pills to one PER ROW, so provenance is checked at row granularity. This
    closes the table-cell blind spot: split_sentences strips '|' rows, so E7/factcheck never see
    them, and a Gate-3 pill-strip (or a dropped column) can orphan the row's other sourced figures.
    WARNING (not blocker): surfaces it for Gate-2.5 review without wedging the fix loop. Only
    roster-sourced values are checked, so first-hand [N] cells and rank/name cells never trip it."""
    # group the roster's source URLs BY value: the SAME value string often recurs across products
    # (two products both "$29/mo" or "1080p") sourced to DIFFERENT urls, and one value can be
    # offered via both pricing and a spec. A row that states the value is sourced if it cites ANY
    # of that value's urls — checking each (value,url) pair independently would flag a correctly
    # cited row for lacking some OTHER product's url.
    value_urls: dict = {}
    for s in (cfg.get("sourced_values") or []):
        v, u = _tc_key(s.get("value")), (s.get("url") or "").strip()
        if len(v) >= 4 and u:
            value_urls.setdefault(v, set()).add(u)
    if not value_urls:
        return
    for (head, body), rep in zip(sections, reports):
        emitted = 0
        for line in body.split("\n"):
            if emitted >= 6:                               # bound noise on a long table
                break
            if not line.lstrip().startswith("|") or re.fullmatch(r"[\s|:\-]+", line):
                continue                                   # non-row or the |---| separator
            # token-boundary match on the space-folded row so "1080" doesn't match inside "21080";
            # url presence via substring (robust to '(' / ')' in a source URL, which MD_LINK_RX
            # would truncate)
            row_key = f" {_tc_key(line)} "
            missing = [v for v, urls in value_urls.items()
                       if f" {v} " in row_key and not any(u in line for u in urls)]
            if missing:
                emitted += 1
                rep.violations.append(Violation("TC1", "warning", head, line.strip()[:80],
                    _t("对比表这一行里的第三方数据缺来源标注(可能 Gate-3 编辑删掉了该行的 ([source](URL)))——补回该行的来源 pill,或把该单元格改成 [N]",
                       "a third-party figure in this comparison-table row has no source pill (a Gate-3 edit may have stripped the row's ([source](URL))); restore the row's source pill or change the cell to [N]")))


WARNING_RULES_PER_SECTION = 8

def lint(md: str, cfg: dict, pack: Pack) -> dict:
    global _FIX_LANG
    _FIX_LANG = (cfg.get("language") or "en").lower()   # unify fix instructions to the article's language
    entities = cfg.get("entities", [])
    brief = cfg.get("brief_headings", [])
    # ST1/ST2/ST3 (and E7's [STAT:]-aware sourcing check) arm only when the [STAT:id] contract was
    # actually ASKED of the draft — page_type=='statistics' AND the registry has a usable stat.
    # Gating on page_type alone deadlocked: brief/draft fall back to the standard bare-number
    # contract whenever the registry is empty/absent (no creds, SCN_STATGATHER=off, mode=optimize,
    # an untranslated variant), but lint would still demand a [STAT:id] marker on every number.
    is_stats = _SG.stats_contract_active(cfg.get("page_type"), cfg.get("stat_registry"))

    sections = parse_sections(md)
    reports = [SectionReport(h) for h, _ in sections]

    for (head, body), rep in zip(sections, reports):
        if not body.strip():
            continue
        rule_A4_list_count(head, body, rep, pack)
        rule_A7_if_order(head, body, rep, pack)
        rule_B1_hedges(head, body, rep, pack)
        rule_B2_vague_qty(head, body, rep, pack)
        rule_B3_modals(head, body, rep, pack)
        rule_C1_para_start(head, body, rep, pack, entities)
        rule_C4_sentence_length(head, body, rep, pack)
        rule_C5_passive(head, body, rep, pack)
        rule_C6_generic_verbs(head, body, rep, pack)
        rule_C7_burstiness(head, body, rep, pack)
        rule_E2_cliches(head, body, rep, pack)
        rule_E3_para_length(head, body, rep, pack)
        rule_E4_placeholders(head, body, rep)
        rule_E5_transitions(head, body, rep, pack)
        rule_E7_unsourced_qty(head, body, rep, pack, stats_active=is_stats)
        rule_E8_ascii_quotes(head, body, rep, pack)
        rule_E9_surrender_placeholder(head, body, rep, pack)
        rule_F3_link_first_word(head, body, rep)
        if is_stats:
            rule_ST1_unmarked_number(head, body, rep, pack)

    # title-level count promise: cfg title/h1 if given, else the draft's own H1 — the pipeline's
    # lint_cfg sets neither, so "# Top 10 …" with 4 entries used to pass silently
    rule_A8_promised_count(sections, cfg.get("title") or cfg.get("h1") or _document_h1(md), reports,
                           ja=_FIX_LANG.startswith("ja"))
    rule_D3_heading_order(sections, brief, reports)
    rule_D4_truncated_section(sections, brief, reports,
                              empty_severity=cfg.get("empty_section_severity", "blocker"))
    rule_F1_bold_query(md, sections, reports, cfg.get("term_lists", {}), brief)
    rule_F5_anchor_repetition(md, reports)
    rule_G1_term_coverage(md, sections, reports, pack, cfg.get("term_lists", {}))
    rule_H1_under_promotion(md, cfg, reports)
    rule_TC1_table_cell_provenance(sections, cfg, reports)
    if is_stats:
        rule_ST2_required_sections(sections, reports)
        rule_ST3_headline_stats_unreferenced(md, reports, cfg)

    all_v = [v for r in reports for v in r.violations]
    blockers = [v for v in all_v if v.severity == "blocker"]
    warnings = [v for v in all_v if v.severity == "warning"]
    n_sections = max(1, len([s for s, b in sections if b.strip()]))
    warn_capacity = n_sections * WARNING_RULES_PER_SECTION
    failed_warn_slots = len({(v.rule, v.location) for v in warnings})
    pass_rate = max(0.0, 1 - failed_warn_slots / warn_capacity)

    # Gate on BLOCKERS only; warn-pass is reported (not gating) — warnings = human polish at the gate.
    verdict = "PASS" if not blockers else "REWRITE"

    return {
        "summary": {
            "sections": n_sections,
            "blockers_failed": len(blockers),
            "warnings_failed": len(warnings),
            "warning_pass_rate": round(pass_rate, 2),
            "warn_capacity": warn_capacity,   # the denominator, stored so a later waiver rebalance reuses it
            "warnings_for_review": pass_rate < PASS_RATE_THRESHOLD,
            "verdict": verdict,
            "det_rules_checked": DET_RULE_IDS,   # attestation: which det rules THIS report ran
        },
        "sections": [
            {"section": r.section, "violations": [asdict(v) for v in r.violations]}
            for r in reports if r.violations
        ],
        "next_action": ("proceed" if verdict == "PASS"
                        else "feed violations[].fix_instruction as rewrite constraints, max_iterations=3"),
    }

def main():
    ap = argparse.ArgumentParser(description="Microsemantics Linter v2 (language packs)")
    ap.add_argument("draft")
    ap.add_argument("--config", help="config.json")
    ap.add_argument("--lang", help="language code (overrides config); built-in: en, zh, ja")
    ap.add_argument("--lang-pack", help="external pack JSON for other languages")
    ap.add_argument("--json", help="write lint-report.json here")
    args = ap.parse_args()

    cfg = json.load(open(args.config, encoding="utf-8")) if args.config else {}
    from langutil import norm_lang
    lang = norm_lang(args.lang or cfg.get("language"), "en")   # normalize EN/zh-CN/ja-JP; default en (matches every other stage)
    cfg["language"] = lang   # let --lang override flow into lint() so fix instructions use the right language
    pack = load_pack(lang, args.lang_pack,
                     cfg.get("extra_hedges", []), cfg.get("extra_cliches", []))

    md = open(args.draft, encoding="utf-8").read()
    report = lint(md, cfg, pack)
    report["summary"]["language"] = lang

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    s = report["summary"]
    print(f"\n{'='*60}")
    print(f"  VERDICT: {s['verdict']}  [lang={lang}]  "
          f"blockers={s['blockers_failed']}  warnings={s['warnings_failed']}  "
          f"warn-pass={s['warning_pass_rate']:.0%}")
    print(f"{'='*60}")
    try:
        for sec in report["sections"]:
            print(f"\n## {sec['section']}")
            for v in sec["violations"]:
                icon = {"blocker": "🔴", "warning": "🟡", "info": "⚪"}[v["severity"]]
                print(f"  {icon} [{v['rule']}] {v['location']}")
                print(f"     ⮑ {v['evidence']}")
                print(f"     ✏️  {v['fix_instruction']}")
    except BrokenPipeError:
        pass
    sys.exit(0 if s["verdict"] == "PASS" else 1)

if __name__ == "__main__":
    main()
