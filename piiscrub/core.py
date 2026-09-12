"""PII detection and redaction over PDF / text. No UI code here."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

ENTITIES = [
    "PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "US_SSN", "CREDIT_CARD",
    "US_BANK_NUMBER", "US_DRIVER_LICENSE", "US_PASSPORT", "IBAN_CODE",
    "LOCATION", "IP_ADDRESS", "MEDICAL_LICENSE", "NRP",
    "UK_NINO", "CRYPTO", "URL",
]

# Presidio's PhoneRecognizer scores exactly 0.40 with no surrounding context
# words, so anything above this silently switches phone detection off.
DEFAULT_THRESHOLD = 0.4
MAX_THRESHOLD = 0.4

READABLE_SUFFIXES = {".pdf", ".txt", ".md"}

# Shortest name fragment worth chasing through the document on its own.
MIN_NAME_TOKEN = 3

PLACEHOLDER_RE = re.compile(r"\[[A-Z_]+_\d+\]")

# Presidio's built-in CREDIT_CARD requires a valid Luhn checksum, so plain
# account / member / record numbers are never matched. These fill that gap.
EXTRA_PATTERNS: list[tuple[str, str]] = [
    ("ACCOUNT_NUMBER", r"\b\d(?:[ -]?\d){11,18}\b"),
    ("POSTAL_CODE", r"\b\d{5}(?:-\d{4})?\b"),
    ("STREET_ADDRESS",
     r"\b\d{1,6}\s+(?:[A-Z][a-zA-Z.'-]+\s+){0,4}"
     r"(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct"
     r"|Place|Pl|Terrace|Ter|Way|Row|Circle|Cir|Parkway|Pkwy)\b\.?"),
]


@dataclass
class Finding:
    """One detected span. `selected` drives whether it is actually redacted."""
    start: int
    end: int
    entity_type: str
    score: float
    text: str
    selected: bool = True

    @property
    def length(self) -> int:
        return self.end - self.start


@dataclass
class ScrubResult:
    original: str
    redacted: str
    findings: list[Finding]
    mapping: dict[str, str] = field(default_factory=dict)
    leaks: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.leaks


class NoTextLayerError(RuntimeError):
    """Raised when a PDF yields no extractable text (i.e. it is a scan)."""


class UnsupportedFileError(RuntimeError):
    """Raised for file types we cannot read as text."""


def _read_text_file(path: Path) -> str:
    """Read a text file, tolerating a BOM and Windows-default cp1252."""
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def extract_text(path: str | Path) -> str:
    """Pull the text layer out of a PDF, or read a text file as-is."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in READABLE_SUFFIXES:
        raise UnsupportedFileError(
            f"{path.name}: only PDF, .txt and .md can be read. Office files and "
            f"images would scan as empty and look falsely clean."
        )
    if suffix != ".pdf":
        return _read_text_file(path)

    from pypdf import PdfReader

    reader = PdfReader(str(path))
    if reader.is_encrypted:
        # decrypt() returns 0 (NOT_DECRYPTED) on a wrong password - it does not raise.
        try:
            unlocked = reader.decrypt("")
        except Exception as exc:  # noqa: BLE001 - surfaced to the user as-is
            raise RuntimeError(f"{path.name} could not be opened: {exc}") from exc
        if not unlocked:
            raise RuntimeError(
                f"{path.name} is password-protected. Remove the password and retry."
            )

    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n\n".join(pages)
    text = "\n".join(line.rstrip() for line in text.splitlines())
    if not text.strip():
        raise NoTextLayerError(
            f"{path.name} has no text layer - it is a scan. OCR it first "
            f"(e.g. ocrmypdf) and try again."
        )
    return text


_analyzer = None


def _get_analyzer():
    """Build the Presidio analyzer once; it loads a ~400 MB spaCy model."""
    global _analyzer
    if _analyzer is None:
        # Presidio's EmailRecognizer calls tldextract, which fetches the public
        # suffix list over HTTPS on first use. Pin it to the bundled snapshot so
        # a local-only tool never reaches the network.
        try:
            import tldextract

            tldextract.TLD_EXTRACTOR = tldextract.TLDExtract(suffix_list_urls=())
        except Exception:  # noqa: BLE001 - detection still works without this
            pass

        from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer

        engine = AnalyzerEngine()
        for label, regex in EXTRA_PATTERNS:
            engine.registry.add_recognizer(
                PatternRecognizer(
                    supported_entity=label,
                    patterns=[Pattern(name=label.lower(), regex=regex, score=0.6)],
                )
            )
        _analyzer = engine
    return _analyzer


def supported_entities() -> list[str]:
    return ENTITIES + [label for label, _ in EXTRA_PATTERNS]


def _name_tokens(value: str) -> list[str]:
    """Individual name parts worth hunting for on their own."""
    return [
        token for token in re.split(r"[^\w'-]+", value)
        if len(token) >= MIN_NAME_TOKEN
    ]


def _literal_findings(text: str, terms: Iterable[str],
                      entity_type: str = "CUSTOM") -> list[Finding]:
    out: list[Finding] = []
    seen: set[str] = set()
    for term in terms:
        term = term.strip()
        if not term or term.casefold() in seen:
            continue
        seen.add(term.casefold())
        for match in re.finditer(re.escape(term), text, re.IGNORECASE):
            out.append(
                Finding(match.start(), match.end(), entity_type, 1.0, match.group(0))
            )
    return out


def _dedupe(findings: list[Finding]) -> list[Finding]:
    """Resolve overlaps: nested spans collapse, partial overlaps merge.

    Dropping a partially-overlapping span would leave its uncovered tail in the
    output *and* keep it out of the leak check, so overlaps are merged instead.
    """
    findings.sort(key=lambda f: (f.start, -f.length, -f.score))
    kept: list[Finding] = []
    last_end = -1
    for f in findings:
        if f.start >= last_end:
            kept.append(f)
            last_end = f.end
        elif f.end > last_end:
            previous = kept[-1]
            previous.text += f.text[last_end - f.start:]
            previous.end = f.end
            last_end = f.end
    return kept


def analyze(text: str, threshold: float = DEFAULT_THRESHOLD,
            extra_terms: Iterable[str] = (),
            entities: Iterable[str] | None = None) -> list[Finding]:
    """Find PII spans. Literal `extra_terms` always win over model detections.

    `entities` restricts detection to a subset of `supported_entities()` (e.g.
    to honor a user's disabled-entity settings). Defaults to all of them.
    """
    results = _get_analyzer().analyze(
        text=text, entities=list(entities) if entities is not None else supported_entities(),
        language="en",
    )
    findings = [
        Finding(r.start, r.end, r.entity_type, r.score, text[r.start:r.end])
        for r in results
        if r.score >= threshold
    ]

    # The model tags "Priya Raghunathan" but often not a later bare
    # "Raghunathan", so chase every name part through the whole document.
    tokens: set[str] = set()
    for f in findings:
        if f.entity_type == "PERSON":
            tokens.update(_name_tokens(f.text))
    findings.extend(_literal_findings(text, sorted(tokens), "PERSON"))

    # Scored 1.0, so ties in _dedupe resolve in the user's favour.
    findings.extend(_literal_findings(text, extra_terms))
    return _dedupe(findings)


def redact(text: str, findings: list[Finding]) -> ScrubResult:
    """Replace selected spans with stable per-value placeholders.

    The same original value always maps to the same placeholder, so downstream
    readers can still follow references between them.
    """
    chosen = [f for f in findings if f.selected]
    counters: dict[str, int] = {}
    placeholders: dict[tuple[str, str], str] = {}
    originals: dict[str, str] = {}

    for f in sorted(chosen, key=lambda f: f.start):
        key = (f.entity_type, f.text.casefold())
        if key not in placeholders:
            counters[f.entity_type] = counters.get(f.entity_type, 0) + 1
            placeholder = f"[{f.entity_type}_{counters[f.entity_type]}]"
            placeholders[key] = placeholder
            # Keyed by placeholder, holding the first occurrence's real casing,
            # so the key file can always be read back.
            originals[placeholder] = f.text

    out = text
    for f in sorted(chosen, key=lambda f: f.start, reverse=True):
        out = out[:f.start] + placeholders[(f.entity_type, f.text.casefold())] + out[f.end:]

    leaks = _find_leaks(findings, out, placeholders, originals)
    return ScrubResult(text, out, findings, originals, leaks)


def _find_leaks(findings: list[Finding], out: str,
                placeholders: dict[tuple[str, str], str],
                originals: dict[str, str]) -> list[str]:
    """Check that nothing redacted survived, ignoring the placeholders themselves.

    A blind substring search across the whole document is unsafe: a short
    value (a date, a zip code) can coincidentally recur inside unrelated text
    - a reference number, another value - that was never itself a finding.
    So a value only counts as leaked when a *real, detected* occurrence of it
    was left unticked. PERSON is the one exception: a bare surname is checked
    against the whole document, because a name fragment can appear in a form
    analyze() never matched as its own finding (see core.py module docstring).
    """
    unselected = {(f.entity_type, f.text.casefold()) for f in findings if not f.selected}
    probe = PLACEHOLDER_RE.sub(" ", out).casefold()
    leaks: list[str] = []
    for key, placeholder in placeholders.items():
        entity_type, value = key
        original = originals[placeholder]
        if key in unselected:
            leaks.append(original)
        elif entity_type == "PERSON":
            # A full name can be replaced while a bare surname survives.
            for token in _name_tokens(value):
                if re.search(rf"\b{re.escape(token)}\b", probe):
                    leaks.append(token)
    return sorted(set(leaks))


def write_outputs(result: ScrubResult, out_path: str | Path,
                  map_path: str | Path | None = None) -> None:
    Path(out_path).write_text(result.redacted, encoding="utf-8")
    if map_path:
        Path(map_path).write_text(
            json.dumps(result.mapping, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
