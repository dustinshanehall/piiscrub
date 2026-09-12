# PII Scrub — project notes

**Version 0.3.2.** Python 3.14 + CustomTkinter desktop app, packaged with PyInstaller.

Strips PII out of a document and writes redacted **text**, for safely pasting
into an LLM. Not a PDF redactor — see README for the distinction.

## Why Python and not something else

The detection engine is Presidio + spaCy, which is Python. Rewriting it for
another stack would mean replacing the one part that works.

## Environment

- Dev venv: `.venv` at the repo root (presidio-analyzer, spacy 3.8.16,
  en_core_web_lg 3.8.0, pypdf 6.22.2, pyinstaller 6.22.2, customtkinter 6.0.0).
- macOS needs `brew install python-tk@3.14` — Homebrew's python@3.14 ships
  without `_tkinter` and the app will not start without it.
- **Each platform's binary must be built on that platform.** PyInstaller
  does not cross-compile; run `build_windows.ps1` on Windows.

## Design notes

- `core.py` holds all detection and redaction logic and imports no UI code, so
  it stays testable and scriptable on its own.
- Presidio's `CREDIT_CARD` recogniser validates Luhn. Real cards match; plain
  bank, member and record numbers never do. `EXTRA_PATTERNS` in `core.py`
  covers that gap along with street addresses and postcodes.
- spaCy's NER is context-sensitive for addresses — the same string can be
  detected in one document and missed in another. That is why the literal
  **Always redact** box exists and why the review list is not optional.
- The leak check in `redact()` is the last line of defence. Never weaken it to
  make a file write succeed. It probes PERSON values token by token, because
  a full name can be replaced while a bare surname survives.
- `_dedupe` MERGES partially-overlapping spans. Dropping one leaves its tail
  in the output and out of the leak check — that was a real 0.1.0 bug.
- `_find_leaks` checks a value against the *findings list* (does a real,
  detected occurrence of it exist unticked?), never a blind substring search
  over the whole document. A blind search false-positives on any short value
  (a date, a zip code) that coincidentally recurs inside unrelated text —
  that was a real 0.2.0 bug that blocked otherwise-correct saves. The PERSON
  bare-surname check is the one deliberate exception: it does scan the whole
  document, because a name fragment can appear in a form `analyze()` never
  matched as its own finding.
- `core.analyze(..., entities=...)` restricts detection to a subset of
  `supported_entities()`, driven by the Settings dialog's per-entity toggles.

## UI

**CustomTkinter** (`customtkinter>=5.2`), not plain ttk. Two directions were
mocked up: Concept A ("refined ttk") shipped first in 0.2.0, then Concept B
("rebuilt shell") replaced it in 0.3.0 — same palette, but CustomTkinter's
`CTkButton`/`CTkFrame`/`CTkCheckBox` give real rounded corners and pill
buttons that ttk can't. `ttk.Treeview` has no CustomTkinter
equivalent, so the findings table became a `CTkScrollableFrame` of finding
cards (`App._build_finding_card`) instead — clicking a card selects it
(highlights its border + the matching preview span); its checkbox toggles
redact/keep independently. `CTkTextbox` wraps a real `tk.Text`, so the
existing `tag_add`/`tag_config` preview-highlighting code needed only
`tag_configure` → `tag_config` (CTk doesn't alias the long name).
`piiscrub.spec` needs `customtkinter` and `darkdetect` added to the
`collect_all` loop — CTk ships its own theme JSON assets as package data
that PyInstaller won't pick up otherwise.

Every palette color is a `(light, dark)` tuple; CTk widgets re-render these
automatically on `ctk.set_appearance_mode()`. The one exception is the
`CTkTextbox` preview's tag colors (`hl_redact`/`hl_keep`/`active`) — plain
tk.Text tags aren't theme-aware, so `_apply_preview_tags()` re-applies them
manually on every theme change. The toolbar's theme button cycles
system → light → dark → system (`_cycle_theme`), persisted like the other
settings. `_pill_button`/`_set_button_enabled` dim a disabled button's whole
fill, not just its text — `text_color_disabled` alone was tried first and
left barely-legible text on a still-bright accent background.

## Licensing

**Apache-2.0.** Chosen deliberately over MIT for the express patent grant and
the more thorough warranty disclaimer. The `LICENSE` file is the legally
operative disclaimer — the README's plain-English version is a courtesy, not
a substitute. Keep both.

Never describe the tool as removing or stripping all PII. Claims like
"irretrievable" or any compliance standard create exposure the licence does not
cover, because that is misrepresentation rather than warranty. It *helps find
and replace* PII.

## Session notes

**2026-09-11** — Built from scratch in one session. Grew out of a research
question about whether to build a PDF PII redaction app; the answer was no (that
niche has ~30 entrants and none has traction), but the narrower "clean text
before sending it to a model" case was worth a local tool.

**2026-09-11 (Windows)** — Ran `build_windows.ps1` to produce the .exe.
During manual testing: found and fixed the leak-check false-positive (see
Design notes), dropped `DATE_TIME`
from detection, added a Settings dialog with per-entity toggles and
persistence (`piiscrub/settings.py`, `~/.piiscrub/settings.json`), added the
live document preview pane, and applied the Concept A ttk theme.

**2026-09-12** — Replaced Concept A with Concept B: rebuilt `gui.py` on
CustomTkinter (see UI section). Verified with a full PyInstaller build, not
just `python -m piiscrub` — CTk's bundled theme assets are exactly the kind
of thing that builds fine from source and breaks only in the frozen .exe.
Follow-up polish same day: higher-contrast palette (secondary buttons were
blending into the page background), a system/light/dark theme toggle,
fixed disabled-button contrast (see UI section), auto-scan on file open with
a Settings toggle to turn it off, and Select all/Select none now start
disabled until a scan produces findings.

**2026-09-12 (licensing)** — Added Apache-2.0, moved the README disclaimer up,
and added a line to the save dialog.
