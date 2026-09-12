"""Entry point. Launches the GUI, or runs headless with --scrub / --selftest."""
from __future__ import annotations

import sys
from pathlib import Path


def _scrub_cli(argv: list[str]) -> int:
    """Headless mode: piiscrub --scrub in.pdf out.md [extra,terms]"""
    from piiscrub import core

    if len(argv) < 2:
        print("usage: --scrub <input.pdf> <output.md> [comma,separated,literals]",
              file=sys.stderr)
        return 2
    src, dest = argv[0], argv[1]
    extras = argv[2].split(",") if len(argv) > 2 else []

    text = core.extract_text(src)
    result = core.redact(text, core.analyze(text, core.DEFAULT_THRESHOLD, extras))
    if not result.ok:
        print(f"ABORT - values survived redaction: {result.leaks}", file=sys.stderr)
        return 1

    core.write_outputs(result, dest, Path(dest).with_suffix(".map.json"))
    print(f"wrote {dest} ({len(result.mapping)} unique values replaced)")
    for placeholder, original in sorted(result.mapping.items()):
        print(f"  {placeholder:22} <- {original}")
    return 0


def _selftest() -> int:
    """Prove the packaged app can load its model and redact. Used after a build."""
    from piiscrub import core

    sample = (
        "Marcus Delgado, SSN 412-88-9031, marcus@example.com, (415) 555-0192, "
        "88 Cypress Row, Oakland, CA 94607, account 4539 8821 0034 7712."
    )
    result = core.redact(sample, core.analyze(sample))
    found = {f.entity_type for f in result.findings}
    required = {"PERSON", "US_SSN", "EMAIL_ADDRESS", "PHONE_NUMBER"}
    missing = required - found

    print("detected:", ", ".join(sorted(found)) or "(nothing)")
    print("redacted:", result.redacted)
    if missing:
        print(f"SELFTEST FAILED - missed {sorted(missing)}", file=sys.stderr)
        return 1
    if not result.ok:
        print(f"SELFTEST FAILED - leaks {result.leaks}", file=sys.stderr)
        return 1
    print("SELFTEST OK")
    return 0


def main() -> int:
    args = sys.argv[1:]
    if args and args[0] == "--selftest":
        return _selftest()
    if args and args[0] == "--scrub":
        return _scrub_cli(args[1:])

    from piiscrub.gui import main as gui_main

    gui_main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
