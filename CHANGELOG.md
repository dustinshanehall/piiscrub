# Changelog

## 0.3.3 — 2026-10-17

Continuous integration. No behaviour changes.

- Tests now run on GitHub Actions for every push and pull request, with a
  status badge at the top of the README.

## 0.3.2 — 2026-09-12

Licensing and documentation. No behaviour changes.

- **Added an Apache-2.0 `LICENSE`.** There was no licence file at all, which
  meant all rights reserved — nobody could legally use it — *and* no warranty
  disclaimer applied. Apache-2.0 gives both the grant and the liability clause.
- Moved the "assistive tool, no guarantee, not a compliance tool" disclaimer to
  the top of the README instead of leaving it buried mid-page.
- The save confirmation now says detection is not guaranteed complete and the
  output should be read before sharing — the last moment the user can act on it.
- README brought back in line with the app: CustomTkinter UI, per-entity
  Settings toggles, live preview, repo-root `.venv`, headless `--scrub` /
  `--selftest` modes, `pytest` instructions, real bundle size.

## 0.3.1 — 2026-09-12

- **Higher-contrast palette.** Secondary buttons were nearly the same color
  as the page background; disabled Scan/Save buttons kept their bright
  accent fill with barely-legible text. Both fixed — disabled buttons now
  dim their whole background, not just the text.
- **Theme toggle** — a System/Light/Dark button in the toolbar that cycles
  System → Light → Dark. Persists across launches.
- **Auto-scan on file open**, on by default, with a toggle in Settings to
  turn it back into a manual Scan-button workflow.
- Select all / Select none now start disabled and only enable once a scan
  has produced findings to act on.

## 0.3.0 — 2026-09-12

- **Rebuilt the UI on CustomTkinter** ("Concept B"). Rounded pill buttons,
  the findings table is now a scrollable list of cards (a table widget isn't
  available in CustomTkinter), and the same redact/keep/active highlighting
  in the document preview. Same palette and behavior as 0.2.0, different
  widget library.
- New dependency: `customtkinter`. The Windows build now bundles its theme
  assets via `piiscrub.spec`.

## 0.2.0 — 2026-09-11

- **Fixed a false-positive leak that blocked saving.** The leak check used to
  do a blind substring search across the whole document, so a short redacted
  value (a date, a zip code) that coincidentally reappeared inside unrelated
  text — a reference number, another number entirely — got reported as a
  "leak" and aborted the save, even though every real occurrence was
  correctly redacted. It now checks whether a real, detected occurrence of
  the value was left unticked, which is the only case that's actually a leak.
- **Dates are no longer detected or redacted.** `DATE_TIME` produced a lot of
  noise for little privacy value and was the main trigger for the leak-check
  bug above.
- **Settings screen** — Sensitivity and Always-redact moved out of the main
  toolbar into a `Settings…` dialog, alongside a new **per-entity toggle**
  (e.g. turn off `PHONE_NUMBER` detection entirely). All settings persist to
  `~/.piiscrub/settings.json` and restore on next launch.
- **Live document preview** — a read-only preview pane next to the findings
  table highlights every detected span (amber = will be redacted, teal =
  kept) and jumps to a span when you click its row.
- Visual refresh: custom ttk theme (warm paper palette, teal accent,
  monospace for detected values), row striping in the findings table.

## 0.1.1 — 2026-09-11

Audit pass. Four of these were live PII leaks.

- **Bare surnames no longer survive.** The model tags "Priya Raghunathan" but
  often misses a later bare "Raghunathan"; every name part is now chased through
  the whole document, and the leak check probes name parts individually.
- **Partially-overlapping detections merge instead of one being dropped.** The
  discarded span's uncovered tail used to stay in the output *and* escape the
  leak check — including terms typed into "Always redact".
- **The key file is no longer lossy.** It is keyed by placeholder and stores the
  real casing, so every placeholder can be read back.
- **Sensitivity is capped at 0.40.** Presidio scores phone numbers at exactly
  0.40, so one click higher silently switched phone detection off.
- Password-protected PDFs report that, rather than pypdf's internal error.
- Text files are read as UTF-8 (BOM tolerated) then cp1252, so Windows-saved
  files no longer mangle accented names past recognition.
- Office files and other binaries are rejected instead of scanning as empty and
  looking falsely clean.
- Errors raised inside the UI are shown in a dialog; frozen builds have no
  console to print them to.
- The Open button is disabled during a scan, so results cannot land against the
  wrong file.
- An invalid Sensitivity value no longer wedges the Scan button.
- `tldextract` is pinned to its bundled suffix list — Presidio's email
  recogniser would otherwise fetch publicsuffix.org on first use.
- `core` is importable without tkinter; `--scrub` and `--selftest` CLI modes.

## 0.1.0 — 2026-09-11

First version.

- Text-layer extraction from PDF via pypdf; `.txt` / `.md` read directly.
- PII detection with Presidio + spaCy `en_core_web_lg`.
- Extra pattern recognisers for the gaps in Presidio's defaults: account
  numbers (its card recogniser requires a valid Luhn checksum, so plain account
  and record numbers never match), street addresses and postcodes.
- Free-text **Always redact** box for literal strings the model misses.
- Review table — every detection listed with its confidence, tick to include.
- Stable per-value placeholders, so the same value keeps the same label.
- Leak check: the output is re-scanned for every redacted value and the file is
  not written if one survived.
- `.map.json` key file written alongside the output.
- PyInstaller builds for macOS and Windows with the spaCy model bundled.
