"""CustomTkinter desktop UI for PII Scrub ("Concept B" rebuilt shell)."""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from . import core
from . import settings
from . import VERSION

APP_NAME = "PII Scrub"

# Palette from the "Rebuilt shell" UI concept, approved 2026-09-12.
# Every color is a (light, dark) pair - CustomTkinter widgets re-render these
# automatically when the appearance mode changes; only the plain tk.Text
# tags on the preview pane need a manual refresh (see _apply_preview_tags).
PAGE = ("#efece0", "#15171a")
CARD = ("#fffefa", "#1e2023")
LINE = ("#d8d0ba", "#34363a")
MUTED = ("#6b6455", "#9a9488")
INK = ("#1c2128", "#ece7db")
ACCENT = ("#2b6a5c", "#5fae9c")
ACCENT_HOVER = ("#20554a", "#4f9484")
ACCENT_SOFT = ("#d7ebe4", "#1e2f2a")
ON_ACCENT = ("#fffefa", "#12201c")
REDACT = ("#a83c39", "#d97a72")
REDACT_SOFT = ("#f2ddd6", "#33221f")
BTN_SECONDARY = ("#e7e0cd", "#2a2c30")
BTN_SECONDARY_HOVER = ("#dcd3ba", "#34363a")

THEME_CYCLE = ("system", "light", "dark")
THEME_LABEL = {"system": "Theme: Auto", "light": "Theme: Light", "dark": "Theme: Dark"}


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME} {VERSION}")
        self.geometry("1240x740")
        self.minsize(920, 580)
        self.configure(fg_color=PAGE)

        self.font_ui = ctk.CTkFont(family="Segoe UI", size=13)
        self.font_ui_bold = ctk.CTkFont(family="Segoe UI Semibold", size=13, weight="bold")
        self.font_small = ctk.CTkFont(family="Segoe UI", size=11)
        self.font_mono = ctk.CTkFont(family="Consolas", size=12)
        self.font_badge = ctk.CTkFont(family="Consolas", size=10, weight="bold")

        self._settings_path = settings.default_path()
        self._saved = settings.load(self._settings_path)
        self.enabled_entities: dict[str, bool] = dict(self._saved["enabled_entities"])
        self.threshold_var = tk.DoubleVar(
            value=self._saved.get("threshold", core.DEFAULT_THRESHOLD)
        )
        self.extra_var = tk.StringVar(value=self._saved.get("extra_terms", ""))
        self.theme_mode = self._saved.get("theme_mode", "system")
        self.auto_scan = bool(self._saved.get("auto_scan", True))
        ctk.set_appearance_mode(self.theme_mode)

        self.source_path: Path | None = None
        self.text: str = ""
        self.findings: list[core.Finding] = []
        self.finding_cards: list[dict] = []
        self.active_idx: int | None = None
        self._queue: queue.Queue = queue.Queue()

        self._scanning = False

        self._build_ui()
        self.report_callback_exception = self._on_callback_error
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._drain_queue)

    def _on_callback_error(self, exc_type, value, traceback) -> None:
        """Frozen builds have no console, so unhandled errors must be shown."""
        messagebox.showerror(APP_NAME, f"{exc_type.__name__}: {value}")

    def _persist_settings(self) -> None:
        try:
            threshold = float(self.threshold_var.get())
        except (tk.TclError, ValueError):
            threshold = core.DEFAULT_THRESHOLD
        settings.save(self._settings_path, {
            "threshold": threshold,
            "extra_terms": self.extra_var.get(),
            "enabled_entities": self.enabled_entities,
            "theme_mode": self.theme_mode,
            "auto_scan": self.auto_scan,
        })

    def _on_close(self) -> None:
        self._persist_settings()
        self.destroy()

    # -------------------------------------------------------------- theming
    def _mode_idx(self) -> int:
        return 1 if ctk.get_appearance_mode() == "Dark" else 0

    def _resolve(self, token: tuple[str, str]) -> str:
        return token[self._mode_idx()]

    def _apply_preview_tags(self) -> None:
        self.preview.tag_config(
            "hl_redact", background=self._resolve(REDACT_SOFT), foreground=self._resolve(REDACT)
        )
        self.preview.tag_config(
            "hl_keep", background=self._resolve(ACCENT_SOFT), foreground=self._resolve(ACCENT)
        )
        self.preview.tag_config(
            "active", background=self._resolve(ACCENT), foreground=self._resolve(ON_ACCENT)
        )
        self.preview.tag_raise("active")

    def _cycle_theme(self) -> None:
        idx = THEME_CYCLE.index(self.theme_mode)
        self.theme_mode = THEME_CYCLE[(idx + 1) % len(THEME_CYCLE)]
        ctk.set_appearance_mode(self.theme_mode)
        self.theme_btn.configure(text=THEME_LABEL[self.theme_mode])
        self._apply_preview_tags()
        self._persist_settings()

    # ------------------------------------------------------------- widgets
    def _pill_button(self, master, text, command, primary=False, state="normal") -> ctk.CTkButton:
        """A pill button whose disabled state dims the whole fill, not just
        the text - text_color_disabled alone reads as barely-legible text on
        a still-bright fg_color, especially for the accent-filled primary
        style."""
        enabled = state == "normal"
        if primary:
            fg = ACCENT if enabled else BTN_SECONDARY
            hover = ACCENT_HOVER if enabled else BTN_SECONDARY
            text_color = ON_ACCENT if enabled else MUTED
        else:
            fg = BTN_SECONDARY
            hover = BTN_SECONDARY_HOVER
            text_color = INK if enabled else MUTED
        btn = ctk.CTkButton(
            master, text=text, command=command, state=state,
            fg_color=fg, hover_color=hover, text_color=text_color,
            corner_radius=999, height=34, font=self.font_ui_bold,
        )
        btn._pii_primary = primary
        return btn

    def _set_button_enabled(self, btn: ctk.CTkButton, enabled: bool) -> None:
        primary = getattr(btn, "_pii_primary", False)
        if primary:
            fg = ACCENT if enabled else BTN_SECONDARY
            hover = ACCENT_HOVER if enabled else BTN_SECONDARY
            text_color = ON_ACCENT if enabled else MUTED
        else:
            fg = BTN_SECONDARY
            hover = BTN_SECONDARY_HOVER
            text_color = INK if enabled else MUTED
        btn.configure(
            state="normal" if enabled else "disabled",
            fg_color=fg, hover_color=hover, text_color=text_color,
        )

    # ---------------------------------------------------------------- layout
    def _build_ui(self) -> None:
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(16, 8))
        self.open_btn = self._pill_button(top, "Open PDF or text file…", self.open_file)
        self.open_btn.pack(side="left")
        self.file_label = ctk.CTkLabel(
            top, text="No file loaded", text_color=MUTED, font=self.font_mono
        )
        self.file_label.pack(side="left", padx=14)
        self.scan_btn = self._pill_button(top, "Scan", self.scan, primary=True, state="disabled")
        self.scan_btn.pack(side="right")
        settings_btn = self._pill_button(top, "Settings", self._open_settings)
        settings_btn.pack(side="right", padx=8)
        self.theme_btn = self._pill_button(top, THEME_LABEL[self.theme_mode], self._cycle_theme)
        self.theme_btn.pack(side="right", padx=8)

        hint = ctk.CTkLabel(
            self,
            text="Account numbers and street addresses are the weakest detections — "
                 "check the document and add anything missed in Settings.",
            text_color=MUTED, font=self.font_small, anchor="w",
        )
        hint.pack(fill="x", padx=18, pady=(0, 8))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        body.grid_columnconfigure(0, weight=6)
        body.grid_columnconfigure(1, weight=5)
        body.grid_rowconfigure(0, weight=1)

        self.card_frame = ctk.CTkScrollableFrame(
            body, fg_color=CARD, corner_radius=12,
            border_width=1, border_color=LINE,
        )
        self.card_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.card_frame.grid_columnconfigure(0, weight=1)
        self.empty_label = ctk.CTkLabel(
            self.card_frame, text="Open a document to get started.",
            text_color=MUTED, font=self.font_ui,
        )
        self.empty_label.grid(row=0, column=0, sticky="w", padx=8, pady=8)

        right = ctk.CTkFrame(body, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(
            right, text="Document preview (click a card to jump to it)",
            text_color=MUTED, font=self.font_small, anchor="w",
        ).grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.preview = ctk.CTkTextbox(
            right, wrap="word", state="disabled", corner_radius=12,
            fg_color=CARD, text_color=INK, border_width=1, border_color=LINE,
            font=self.font_ui,
        )
        self.preview.grid(row=1, column=0, sticky="nsew")
        self._apply_preview_tags()

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="x", padx=16, pady=(0, 6))
        self.select_all_btn = self._pill_button(
            bottom, "Select all", lambda: self._set_all(True), state="disabled"
        )
        self.select_all_btn.pack(side="left")
        self.select_none_btn = self._pill_button(
            bottom, "Select none", lambda: self._set_all(False), state="disabled"
        )
        self.select_none_btn.pack(side="left", padx=8)
        self.save_btn = self._pill_button(
            bottom, "Save redacted…", self.save, primary=True, state="disabled"
        )
        self.save_btn.pack(side="right")

        self.status = ctk.CTkLabel(
            self, text="Ready", text_color=MUTED, font=self.font_small, anchor="w"
        )
        self.status.pack(fill="x", padx=18, pady=(0, 12))

    # -------------------------------------------------------------- settings
    def _open_settings(self) -> None:
        dialog = ctk.CTkToplevel(self)
        dialog.title("Settings")
        dialog.configure(fg_color=PAGE)
        dialog.geometry("560x560")
        dialog.transient(self)
        dialog.grab_set()

        opts = ctk.CTkFrame(dialog, fg_color="transparent")
        opts.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkLabel(opts, text="Sensitivity", text_color=INK, font=self.font_ui_bold).pack(
            side="left"
        )
        threshold_choices = []
        v = 0.1
        while v <= core.MAX_THRESHOLD + 1e-9:
            threshold_choices.append(f"{v:.2f}")
            v += 0.05
        threshold_str = tk.StringVar(value=f"{self.threshold_var.get():.2f}")
        ctk.CTkOptionMenu(
            opts, values=threshold_choices, variable=threshold_str,
            fg_color=BTN_SECONDARY, button_color=LINE, button_hover_color=LINE,
            text_color=INK, corner_radius=999, width=90, font=self.font_ui,
        ).pack(side="left", padx=10)

        extra_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        extra_frame.pack(fill="x", padx=16, pady=8)
        ctk.CTkLabel(
            extra_frame, text="Always redact (comma-separated)",
            text_color=INK, font=self.font_ui_bold, anchor="w",
        ).pack(fill="x")
        extra_var = tk.StringVar(value=self.extra_var.get())
        ctk.CTkEntry(
            extra_frame, textvariable=extra_var, fg_color=CARD,
            border_color=LINE, text_color=INK, corner_radius=8,
        ).pack(fill="x", pady=(6, 0))

        auto_scan_var = tk.BooleanVar(value=self.auto_scan)
        ctk.CTkCheckBox(
            dialog, text="Scan automatically when a file is opened",
            variable=auto_scan_var,
            fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color=INK,
            checkmark_color=ON_ACCENT, font=self.font_ui, corner_radius=6,
        ).pack(fill="x", padx=16, pady=(4, 0), anchor="w")

        ctk.CTkLabel(
            dialog, text="Detect these types", text_color=INK,
            font=self.font_ui_bold, anchor="w",
        ).pack(fill="x", padx=16, pady=(10, 4))
        entities_frame = ctk.CTkScrollableFrame(
            dialog, fg_color=CARD, corner_radius=12,
            border_width=1, border_color=LINE,
        )
        entities_frame.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        entity_vars: dict[str, tk.BooleanVar] = {}
        columns = 2
        for i, entity in enumerate(sorted(self.enabled_entities)):
            var = tk.BooleanVar(value=self.enabled_entities[entity])
            entity_vars[entity] = var
            ctk.CTkCheckBox(
                entities_frame, text=entity, variable=var,
                fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color=INK,
                checkmark_color=ON_ACCENT, font=self.font_mono, corner_radius=6,
            ).grid(row=i // columns, column=i % columns, sticky="w", padx=8, pady=6)

        def on_save() -> None:
            try:
                self.threshold_var.set(float(threshold_str.get()))
            except ValueError:
                pass
            self.extra_var.set(extra_var.get())
            self.auto_scan = auto_scan_var.get()
            for entity, var in entity_vars.items():
                self.enabled_entities[entity] = var.get()
            self._persist_settings()
            dialog.destroy()

        buttons = ctk.CTkFrame(dialog, fg_color="transparent")
        buttons.pack(fill="x", padx=16, pady=(0, 16))
        self._pill_button(buttons, "Save", on_save, primary=True).pack(side="right")
        self._pill_button(buttons, "Cancel", dialog.destroy).pack(side="right", padx=8)

    # --------------------------------------------------------------- actions
    def open_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose a document",
            filetypes=[("Documents", "*.pdf *.txt *.md"), ("All files", "*.*")],
        )
        if not path:
            return
        self.source_path = Path(path)
        self.file_label.configure(text=self.source_path.name, text_color=INK)
        self.findings = []
        self._clear_cards()
        self._set_preview_text("")
        self._set_button_enabled(self.save_btn, False)
        self._set_button_enabled(self.select_all_btn, False)
        self._set_button_enabled(self.select_none_btn, False)
        self._set_button_enabled(self.scan_btn, True)
        if self.auto_scan:
            self.scan()
        else:
            self._set_status(f"Loaded {self.source_path.name}. Click Scan.")

    def scan(self) -> None:
        if not self.source_path:
            return
        try:
            threshold = float(self.threshold_var.get())
        except (tk.TclError, ValueError):
            messagebox.showerror(
                APP_NAME,
                f"Sensitivity must be a number between 0.1 and {core.MAX_THRESHOLD}.",
            )
            return

        self._scanning = True
        self._set_button_enabled(self.scan_btn, False)
        self._set_button_enabled(self.save_btn, False)
        self._set_button_enabled(self.open_btn, False)
        self._set_status("Scanning… the language model takes a few seconds to load.")
        extras = [t for t in self.extra_var.get().split(",") if t.strip()]
        entities = [e for e, on in self.enabled_entities.items() if on]
        threading.Thread(
            target=self._scan_worker,
            args=(self.source_path, threshold, extras, entities),
            daemon=True,
        ).start()

    def _scan_worker(self, path: Path, threshold: float, extras: list[str],
                     entities: list[str]) -> None:
        try:
            text = core.extract_text(path)
            findings = core.analyze(text, threshold, extras, entities)
            self._queue.put(("scanned", (text, findings)))
        except Exception as exc:  # noqa: BLE001 - reported verbatim in the UI
            self._queue.put(("error", exc))

    def _drain_queue(self) -> None:
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                if kind == "scanned":
                    self._populate(*payload)
                elif kind == "error":
                    self._scanning = False
                    self._set_button_enabled(self.scan_btn, True)
                    self._set_button_enabled(self.open_btn, True)
                    self._set_status("Scan failed.")
                    messagebox.showerror(APP_NAME, str(payload))
        except queue.Empty:
            pass
        self.after(100, self._drain_queue)

    # ----------------------------------------------------------- findings UI
    def _clear_cards(self) -> None:
        for card in self.finding_cards:
            card["frame"].destroy()
        self.finding_cards = []
        self.active_idx = None

    def _populate(self, text: str, findings: list[core.Finding]) -> None:
        self.text = text
        self.findings = findings
        self._clear_cards()
        self.empty_label.grid_forget()
        self._set_preview_text(text)

        if not findings:
            self.empty_label.configure(
                text="No PII detected. Check the document yourself before trusting that."
            )
            self.empty_label.grid(row=0, column=0, sticky="w", padx=8, pady=8)

        for idx, f in enumerate(findings):
            self._build_finding_card(idx, f)
            self._retag_finding(idx)

        self._scanning = False
        self._set_button_enabled(self.scan_btn, True)
        self._set_button_enabled(self.open_btn, True)
        self._set_button_enabled(self.save_btn, bool(findings))
        self._set_button_enabled(self.select_all_btn, bool(findings))
        self._set_button_enabled(self.select_none_btn, bool(findings))
        self._set_status(
            f"{len(findings)} detections across {len(text):,} characters. "
            f"Untick anything that should stay."
            if findings else "No PII detected. Check the document yourself before trusting that."
        )

    def _build_finding_card(self, idx: int, f: core.Finding) -> None:
        # Rows use PAGE (not CARD) so they read as distinct rows sitting
        # inside the white card_frame panel, instead of blending into it.
        frame = ctk.CTkFrame(
            self.card_frame, fg_color=PAGE, corner_radius=10,
            border_width=1, border_color=LINE,
        )
        frame.grid(row=idx, column=0, sticky="ew", padx=6, pady=4)
        frame.grid_columnconfigure(1, weight=1)

        var = tk.BooleanVar(value=f.selected)
        checkbox = ctk.CTkCheckBox(
            frame, text="", variable=var, width=22, command=lambda i=idx: self._toggle(i),
            fg_color=ACCENT, hover_color=ACCENT_HOVER, checkmark_color=ON_ACCENT,
            corner_radius=999, border_color=LINE,
        )
        checkbox.grid(row=0, column=0, rowspan=2, padx=(10, 8), pady=10)

        preview = " ".join(f.text.split())
        if len(preview) > 100:
            preview = preview[:97] + "…"
        value_label = ctk.CTkLabel(
            frame, text=preview, text_color=INK, font=self.font_mono,
            anchor="w", justify="left",
        )
        value_label.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=(8, 0))

        sub = ctk.CTkFrame(frame, fg_color="transparent")
        sub.grid(row=1, column=1, sticky="w", padx=(0, 12), pady=(2, 8))
        badge = ctk.CTkLabel(
            sub, text=f.entity_type, text_color=ACCENT, fg_color=ACCENT_SOFT,
            font=self.font_badge, corner_radius=999, padx=8, pady=2,
        )
        badge.pack(side="left")
        ctk.CTkLabel(
            sub, text=f"{f.score:.0%}", text_color=MUTED, font=self.font_small,
        ).pack(side="left", padx=(8, 0))

        for widget in (frame, value_label, sub):
            widget.bind("<Button-1>", lambda _e, i=idx: self._select_card(i))

        self.finding_cards.append({
            "frame": frame, "var": var, "checkbox": checkbox, "badge": badge,
        })

    def _select_card(self, idx: int) -> None:
        self._set_active(idx)

    def _toggle(self, idx: int) -> None:
        finding = self.findings[idx]
        card = self.finding_cards[idx]
        finding.selected = card["var"].get()
        self._retag_finding(idx)
        self._set_active(idx)

    def _set_all(self, value: bool) -> None:
        for idx, finding in enumerate(self.findings):
            finding.selected = value
            self.finding_cards[idx]["var"].set(value)
            self._retag_finding(idx)

    # -------------------------------------------------------------- preview
    def _set_preview_text(self, text: str) -> None:
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", text)
        self.preview.configure(state="disabled")

    def _span_indices(self, finding: core.Finding) -> tuple[str, str]:
        return f"1.0+{finding.start}c", f"1.0+{finding.end}c"

    def _retag_finding(self, idx: int) -> None:
        f = self.findings[idx]
        start, end = self._span_indices(f)
        self.preview.tag_remove("hl_redact", start, end)
        self.preview.tag_remove("hl_keep", start, end)
        self.preview.tag_add("hl_redact" if f.selected else "hl_keep", start, end)

    def _set_active(self, idx: int) -> None:
        if self.active_idx is not None and self.active_idx < len(self.finding_cards):
            self.finding_cards[self.active_idx]["frame"].configure(border_color=LINE)
        self.active_idx = idx
        self.finding_cards[idx]["frame"].configure(border_color=ACCENT)

        f = self.findings[idx]
        start, end = self._span_indices(f)
        self.preview.tag_remove("active", "1.0", "end")
        self.preview.tag_add("active", start, end)
        self.preview.see(start)

    def save(self) -> None:
        if not self.findings or not self.source_path:
            return
        result = core.redact(self.text, self.findings)
        if not result.ok:
            messagebox.showerror(
                APP_NAME,
                "Aborted — these values survived redaction and the file was "
                "NOT written:\n\n" + "\n".join(result.leaks) +
                "\n\nThis happens when some rows for a value are ticked and "
                "others are not (tick every row containing it, or none), or "
                "when a bare surname from a ticked full name still appears "
                "elsewhere in the document on its own.",
            )
            return

        out = filedialog.asksaveasfilename(
            title="Save redacted text",
            defaultextension=".md",
            initialfile=f"{self.source_path.stem}-redacted.md",
            filetypes=[("Markdown", "*.md"), ("Text", "*.txt")],
        )
        if not out:
            return

        map_path = Path(out).with_suffix(".map.json")
        core.write_outputs(result, out, map_path)
        self._set_status(f"Wrote {Path(out).name} — {len(result.mapping)} values replaced.")
        messagebox.showinfo(
            APP_NAME,
            f"Saved {Path(out).name}\n\n"
            f"{len(result.mapping)} unique values replaced.\n\n"
            f"The key file {map_path.name} maps placeholders back to the real "
            f"values. Keep it local — never send it with the redacted text.\n\n"
            f"Detection is assistive and not guaranteed complete. Read the "
            f"output before you share it.",
        )

    def _set_status(self, message: str) -> None:
        self.status.configure(text=message)


def main() -> None:
    App().mainloop()
