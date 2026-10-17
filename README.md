# PII Scrub

[![tests](https://github.com/dustinshanehall/piiscrub/actions/workflows/tests.yml/badge.svg)](https://github.com/dustinshanehall/piiscrub/actions/workflows/tests.yml)

Finds personal information in a document and replaces it, so the text is safe to
paste into an LLM. Runs entirely on your own machine — nothing is uploaded.

Open a PDF, review what it found, save a redacted Markdown file.

> **This is an assistive tool, not a guarantee.** Detection is imperfect and
> makes no claim of completeness. It is not a compliance tool. Read the findings
> list and the output before you share anything. Provided without warranty —
> see [LICENSE](LICENSE).

## What it does

1. **Extracts** the text layer from a PDF (or reads a `.txt` / `.md` directly).
2. **Detects** PII with Microsoft Presidio plus spaCy's `en_core_web_lg` model —
   names, emails, phones, SSNs, cards, addresses, postcodes, account numbers,
   locations and more. Each type can be switched off in Settings.
3. **Lets you review** every detection as a card, with the matching span
   highlighted in a live preview of the document. Tick to redact, untick to keep.
4. **Replaces** each unique value with a stable placeholder — `[PERSON_1]`,
   `[US_SSN_1]` — so the same person keeps the same label throughout and the
   document still reads coherently.
5. **Verifies** that no redacted value survived into the output, and refuses to
   write the file if one did.

It also writes a `.map.json` key file next to the output so you can translate
placeholders back afterwards. **Keep that file local. Never send it anywhere.**

## What it does NOT do

- **It does not produce a redacted PDF.** The output is text, for feeding to a
  model. If you need a shareable document with the PII removed from the file
  itself, use a dedicated redaction tool.
- **It does not read scanned PDFs.** No text layer means nothing to extract; run
  the file through OCR (`ocrmypdf`) first.
- **It does not catch everything.** Account numbers and street addresses are the
  weakest detections, and spaCy's name recognition is context-sensitive — the
  same string can be found in one document and missed in another. Anything the
  scan misses can be typed into the **Always redact** box as a literal string.

## Running from source

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m spacy download en_core_web_lg
.venv/bin/python run.py
```

macOS also needs Tk: `brew install python-tk@3.14`.

There is a headless mode too:

```bash
.venv/bin/python run.py --scrub input.pdf output.md
.venv/bin/python run.py --selftest      # verifies detection works end to end
```

## Tests

```bash
.venv/bin/python -m pytest tests/
```

The same tests run on GitHub Actions for every push (`.github/workflows/tests.yml`).

## Building an executable

PyInstaller cannot cross-compile — each platform is built on itself.

| Platform | Command | Output |
|---|---|---|
| macOS | `./build_macos.sh` | `dist/PII Scrub.app` |
| Windows | `.\build_windows.ps1` | `dist\PII Scrub\PII Scrub.exe` |

The spaCy model is bundled, so the built app needs no network access. That makes
the result large — over 500 MB. Run `--selftest` against the built binary
afterwards; bundled model and theme assets are the parts that work from source
and fail only once frozen.

## Licence

Apache License 2.0 — see [LICENSE](LICENSE).

Dependencies keep their own licences: Presidio (MIT), spaCy and
`en_core_web_lg` (MIT), pypdf (BSD), CustomTkinter (MIT).
