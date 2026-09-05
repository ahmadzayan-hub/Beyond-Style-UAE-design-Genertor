"""Text Integrity Engine — CORRECT ARABIC FIRST.

The customer's text is the contract. This module never corrects it; it
inspects, compares and certifies:

- `inspect(raw)`: per-character listing + issues (invisible/control/bidi
  characters, zero-width joiners, NFC composition notes). Issues are
  reported with positions and a *suggested* clean text that the customer
  must re-enter explicitly — nothing is stripped silently.
- `compare(expected, actual)`: codepoint-level diff classified in Arabic
  terms (dot change, hamza change, taa-marbuta/haa, alif-maqsura/yaa,
  diacritic lost, ligature/presentation form, reorder, missing, extra).
  ميثه vs ميثة is a DOT change and a FAIL — never an equivalence.
- `certify(source, proof, outline_issues)`: TEXT INTEGRITY: PASS / FAIL for
  a shaped, outlined design — every codepoint covered by a glyph, no
  .notdef, no glyph outline lost.
"""
from __future__ import annotations

import difflib
import hashlib
import unicodedata
from dataclasses import dataclass, field

#: Characters that must never travel silently inside a jewellery text.
INVISIBLE_CODEPOINTS = {
    0x200B: "zero width space", 0x200C: "zero width non-joiner", 0x200D: "zero width joiner",
    0x2060: "word joiner", 0xFEFF: "byte order mark", 0x00AD: "soft hyphen",
    0x200E: "left-to-right mark", 0x200F: "right-to-left mark", 0x061C: "Arabic letter mark",
    0x202A: "LRE", 0x202B: "RLE", 0x202C: "PDF", 0x202D: "LRO", 0x202E: "RLO",
    0x2066: "LRI", 0x2067: "RLI", 0x2068: "FSI", 0x2069: "PDI",
    0x00A0: "no-break space", 0x180E: "Mongolian vowel separator",
}
#: Explicit shaping/tatweel: visible and legitimate, but flagged so nobody
#: mistakes an elongation for a spelling.
NOTE_CODEPOINTS = {0x0640: "tatweel (kashida)"}

#: Arabic letters grouped by rasm (skeleton): same skeleton, different dots.
RASM_GROUPS = [
    "بتثنيىئ", "جحخ", "دذ", "رز", "سش", "صض", "طظ", "عغ", "فق", "هة", "وؤ", "اأإآٱ", "كگ",
]
_RASM = {ch: i for i, grp in enumerate(RASM_GROUPS) for ch in grp}
HAMZA_FORMS = set("أإآٱءؤئ")
MARKS = lambda ch: unicodedata.category(ch) == "Mn"  # noqa: E731


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class CharInfo:
    index: int
    char: str
    codepoint: str
    name: str
    category: str
    joins: bool

    def as_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class IntegrityIssue:
    code: str
    severity: str  # ERROR | WARNING | INFO
    index: int | None
    detail: str
    detail_ar: str

    def as_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class InspectionReport:
    raw_text: str
    normalized_text: str
    sha256_raw: str
    sha256_normalized: str
    characters: list[CharInfo]
    issues: list[IntegrityIssue]
    suggested_clean_text: str | None
    status: str  # PASS | FAIL

    def as_dict(self) -> dict:
        return {
            "raw_text": self.raw_text, "normalized_text": self.normalized_text,
            "sha256_raw": self.sha256_raw, "sha256_normalized": self.sha256_normalized,
            "characters": [c.as_dict() for c in self.characters],
            "issues": [i.as_dict() for i in self.issues],
            "suggested_clean_text": self.suggested_clean_text,
            "status": self.status, "label": f"TEXT INTEGRITY: {self.status}",
        }


class TextIntegrityError(ValueError):
    def __init__(self, report: InspectionReport):
        self.report = report
        super().__init__("; ".join(i.detail for i in report.issues if i.severity == "ERROR"))


def inspect(raw: str) -> InspectionReport:
    normalized = unicodedata.normalize("NFC", raw)
    chars: list[CharInfo] = []
    issues: list[IntegrityIssue] = []
    for i, ch in enumerate(raw):
        cp = ord(ch)
        name = unicodedata.name(ch, f"U+{cp:04X}")
        cat = unicodedata.category(ch)
        chars.append(CharInfo(i, ch, f"U+{cp:04X}", name, cat, is_joining_arabic(ch)))
        if cp in INVISIBLE_CODEPOINTS:
            what = INVISIBLE_CODEPOINTS[cp]
            issues.append(IntegrityIssue(
                "INVISIBLE_CHARACTER", "ERROR", i,
                f"Hidden character at position {i + 1} ({what}, U+{cp:04X}). It cannot be part of a "
                "jewellery text — please re-enter the text without it.",
                f"يوجد حرف مخفي في الموضع {i + 1} ({what}). لا يمكن أن يكون جزءًا من نص المجوهرات — "
                "أعد إدخال النص بدونه.",
            ))
        elif cat.startswith("C") and ch not in "\n":
            issues.append(IntegrityIssue(
                "CONTROL_CHARACTER", "ERROR", i,
                f"Control character U+{cp:04X} at position {i + 1} — please re-enter the text.",
                f"حرف تحكم U+{cp:04X} في الموضع {i + 1} — أعد إدخال النص.",
            ))
        elif cp in NOTE_CODEPOINTS:
            issues.append(IntegrityIssue(
                "TATWEEL_PRESENT", "WARNING", i,
                f"Elongation mark (tatweel) at position {i + 1}. It is not a letter; confirm it is intended.",
                f"علامة تطويل (كشيدة) في الموضع {i + 1}. ليست حرفًا؛ أكّد أنها مقصودة.",
            ))
        elif 0xFB50 <= cp <= 0xFDFF or 0xFE70 <= cp <= 0xFEFF:
            issues.append(IntegrityIssue(
                "PRESENTATION_FORM", "WARNING", i,
                f"Pre-shaped Arabic form at position {i + 1} ({name}). NFC will restore the base letters; "
                "the shaping engine decides the form.",
                f"شكل عرض مُشكَّل مسبقًا في الموضع {i + 1}. سيُعاد إلى الحرف الأساسي وتحدد المحرك شكله.",
            ))
    if normalized != raw:
        issues.append(IntegrityIssue(
            "NFC_COMPOSITION", "INFO", None,
            "Unicode canonical composition (NFC) changed the code sequence without changing any letter, "
            "dot or mark. Both forms hash differently; the normalized form is the contract.",
            "تم توحيد ترميز يونيكود (NFC) دون تغيير أي حرف أو نقطة أو علامة؛ الصيغة الموحّدة هي المرجع.",
        ))
    if not normalized.strip():
        issues.append(IntegrityIssue("EMPTY_TEXT", "ERROR", None, "The text is empty.", "النص فارغ."))
    suggested = None
    if any(i.code in ("INVISIBLE_CHARACTER", "CONTROL_CHARACTER") for i in issues):
        suggested = "".join(
            ch for ch in raw
            if ord(ch) not in INVISIBLE_CODEPOINTS and not (unicodedata.category(ch).startswith("C") and ch != "\n")
        )
    status = "FAIL" if any(i.severity == "ERROR" for i in issues) else "PASS"
    return InspectionReport(raw, normalized, sha256(raw), sha256(normalized), chars, issues, suggested, status)


def is_joining_arabic(ch: str) -> bool:
    return "؀" <= ch <= "ۿ" and unicodedata.category(ch).startswith("L")


# ------------------------------------------------------------------ compare

def _classify(a: str, b: str) -> tuple[str, str, str]:
    """Classify a substitution a→b in Arabic terms: (code, en, ar)."""
    if a in _RASM and b in _RASM and _RASM[a] == _RASM[b]:
        if {a, b} == {"ه", "ة"}:
            return ("DOT_CHANGE", "haa ↔ taa marbuta (dots differ)", "هاء ↔ تاء مربوطة (النقاط تختلف)")
        if {a, b} == {"ي", "ى"}:
            return ("DOT_CHANGE", "yaa ↔ alif maqsura (dots differ)", "ياء ↔ ألف مقصورة (النقاط تختلف)")
        if a in HAMZA_FORMS or b in HAMZA_FORMS:
            return ("HAMZA_CHANGE", "hamza form changed", "تغيّر شكل الهمزة")
        return ("DOT_CHANGE", "same skeleton, different dots", "نفس الرسم، نقاط مختلفة")
    if MARKS(a) or MARKS(b):
        return ("DIACRITIC_CHANGE", "diacritic changed", "تغيّرت علامة التشكيل")
    return ("CHARACTER_CHANGE", "different letter", "حرف مختلف")


@dataclass
class DiffEntry:
    kind: str  # DOT_CHANGE | HAMZA_CHANGE | DIACRITIC_CHANGE | CHARACTER_CHANGE | MISSING | EXTRA | DIACRITIC_LOST | REORDERED
    expected_index: int | None
    actual_index: int | None
    expected: str
    actual: str
    detail: str
    detail_ar: str

    def as_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class ComparisonReport:
    expected: str
    actual: str
    identical: bool
    entries: list[DiffEntry] = field(default_factory=list)

    @property
    def status(self) -> str:
        return "PASS" if self.identical else "FAIL"

    def as_dict(self) -> dict:
        return {"expected": self.expected, "actual": self.actual, "identical": self.identical,
                "status": self.status, "label": f"TEXT INTEGRITY: {self.status}",
                "entries": [e.as_dict() for e in self.entries]}


def compare(expected: str, actual: str) -> ComparisonReport:
    """Codepoint-exact comparison. No normalization is applied here: callers
    compare the contract text (normalized, confirmed) against what a
    pipeline stage carries."""
    if expected == actual:
        return ComparisonReport(expected, actual, True)
    entries: list[DiffEntry] = []
    sm = difflib.SequenceMatcher(a=expected, b=actual, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        if tag == "replace" and (i2 - i1) == (j2 - j1):
            for k in range(i2 - i1):
                a, b = expected[i1 + k], actual[j1 + k]
                code, en, ar = _classify(a, b)
                entries.append(DiffEntry(code, i1 + k, j1 + k, a, b,
                                         f"'{a}' became '{b}' at position {i1 + k + 1}: {en}.",
                                         f"'{a}' أصبح '{b}' في الموضع {i1 + k + 1}: {ar}."))
            continue
        if tag in ("delete", "replace"):
            for k in range(i1, i2):
                a = expected[k]
                kind = "DIACRITIC_LOST" if MARKS(a) else "MISSING"
                entries.append(DiffEntry(kind, k, None, a, "",
                                         f"'{a}' (position {k + 1}) is missing.",
                                         f"'{a}' (الموضع {k + 1}) مفقود."))
        if tag in ("insert", "replace"):
            for k in range(j1, j2):
                b = actual[k]
                entries.append(DiffEntry("EXTRA", None, k, "", b,
                                         f"'{b}' was added at position {k + 1}.",
                                         f"أُضيف '{b}' في الموضع {k + 1}."))
    # Reorder detection: same multiset of codepoints, different order.
    if sorted(expected) == sorted(actual):
        entries.append(DiffEntry("REORDERED", None, None, expected, actual,
                                 "The same letters appear in a different order.",
                                 "نفس الحروف بترتيب مختلف."))
    return ComparisonReport(expected, actual, False, entries)


# ------------------------------------------------------------------ certify

def certify(source_text: str, source_sha256: str, proof, outline_issues: list[str] | None = None,
            carried_text: str | None = None) -> dict:
    """TEXT INTEGRITY verdict for a shaped + outlined design version."""
    checks = []
    ok = True
    if carried_text is not None:
        cmp = compare(source_text, carried_text)
        checks.append({"check": "text_carried_unchanged", "status": cmp.status, "entries": [e.as_dict() for e in cmp.entries]})
        ok &= cmp.identical
    hash_ok = sha256(source_text) == source_sha256
    checks.append({"check": "hash_matches_text", "status": "PASS" if hash_ok else "FAIL"})
    ok &= hash_ok
    verified = bool(getattr(proof, "verified", False))
    uncovered = list(getattr(proof, "uncovered_codepoint_indices", []) or [])
    notdef = int(getattr(proof, "notdef_glyph_count", 0) or 0)
    checks.append({"check": "every_codepoint_has_a_glyph", "status": "PASS" if not uncovered else "FAIL",
                   "uncovered_indices": uncovered})
    checks.append({"check": "no_missing_glyph_notdef", "status": "PASS" if notdef == 0 else "FAIL", "notdef": notdef})
    ok &= verified and not uncovered and notdef == 0
    lost = [i for i in (outline_issues or []) if "empty" in i.lower() or "no contour" in i.lower()]
    checks.append({"check": "no_glyph_outline_lost", "status": "PASS" if not lost else "FAIL", "issues": lost})
    ok &= not lost
    status = "PASS" if ok else "FAIL"
    return {"status": status, "label": f"TEXT INTEGRITY: {status}", "checks": checks,
            "source_text": source_text, "source_text_sha256": source_sha256}
