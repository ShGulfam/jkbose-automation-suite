#!/usr/bin/env python3
"""
JKBOSE Automation Tool -- GUI

A desktop front-end (Tkinter) for the same automation code used by
main.py / the terminal menu. It wraps main.cmd_browse / cmd_inspect /
cmd_screenshot / cmd_submit -- no automation logic lives in this file,
it only collects input from forms, runs the existing commands on a
background thread, and shows their output live.

Run it with:
    python gui_main.py

Needs Google Chrome, plus the same packages as the CLI tool
(see requirements.txt) and Tkinter (bundled with the standard Windows/
macOS Python installers; on Linux you may need `sudo apt install
python3-tk`).
"""
import sys
import queue
import threading
import traceback
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path
from PIL import Image, ImageTk

from jkbose_tool import config
from jkbose_tool.internal_assessment_gui import InternalAssessmentGUI
import main as cli  # cmd_browse / cmd_inspect / cmd_screenshot / cmd_submit
from jkbose_tool.features.submit_form import build_preflight

APP_TITLE = "JKBOSE Automation Tool"

BG = "#f4f7fb"
SIDEBAR_BG = "#132337"
SIDEBAR_HOVER = "#2a3350"
ACCENT = "#166b75"
ACCENT_DARK = "#10535b"
CARD_BG = "#ffffff"
MUTED = "#5c6472"
LOG_BG = "#0f1420"
LOG_FG = "#c8f7d4"


# ---------------------------------------------------------------------
# stdout -> GUI log bridge
# ---------------------------------------------------------------------

class QueueWriter:
    """File-like object that forwards writes to a thread-safe queue, so
    the automation code's ordinary print() calls show up live in the
    GUI's Activity Log without any changes to that code."""

    def __init__(self, q):
        self.q = q

    def write(self, s):
        if s:
            self.q.put(("log", s))

    def flush(self):
        pass


# ---------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------

class App(InternalAssessmentGUI):
    def __init__(self, root):
        self.root = root
        root.title(APP_TITLE)
        root.geometry("1100x740")
        root.minsize(960, 640)
        root.configure(bg=BG)

        self.msg_queue = queue.Queue()
        self.worker = None
        self.stop_event = threading.Event()
        self.current_driver = None
        self.run_buttons = []
        self.sections = {}
        self.nav_buttons = {}
        self.log_unread = False

        self._build_style()
        self._build_layout()
        self._show_section("dashboard")
        self._poll_queue()

    # ------------------------------------------------------------
    # Look & feel
    # ------------------------------------------------------------
    def _build_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("Content.TFrame", background=BG)
        style.configure("Card.TFrame", background=CARD_BG)
        style.configure("Sidebar.TFrame", background=SIDEBAR_BG)

        style.configure("TLabel", background=BG, foreground="#1a1f2b", font=("Segoe UI", 10))
        style.configure("Card.TLabel", background=CARD_BG, foreground="#1a1f2b", font=("Segoe UI", 10))
        style.configure("Header.TLabel", background=BG, foreground="#111827",
                         font=("Segoe UI", 17, "bold"))
        style.configure("SubHeader.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 10))
        style.configure("Muted.Card.TLabel", background=CARD_BG, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("SidebarTitle.TLabel", background=SIDEBAR_BG, foreground="white",
                         font=("Segoe UI", 14, "bold"))
        style.configure("SidebarSub.TLabel", background=SIDEBAR_BG, foreground="#8b93ab",
                         font=("Segoe UI", 8))

        style.configure("Sidebar.TButton", background=SIDEBAR_BG, foreground="#c7cde0",
                         borderwidth=0, font=("Segoe UI", 10), padding=(14, 8), anchor="w")
        style.map("Sidebar.TButton",
                  background=[("active", SIDEBAR_HOVER)],
                  foreground=[("active", "white")])
        style.configure("SidebarActive.TButton", background=ACCENT, foreground="white",
                         borderwidth=0, font=("Segoe UI", 10, "bold"), padding=(14, 8), anchor="w")
        style.map("SidebarActive.TButton", background=[("active", ACCENT)])

        style.configure("Accent.TButton", background=ACCENT, foreground="white",
                         font=("Segoe UI", 10, "bold"), padding=(12, 6), borderwidth=0)
        style.map("Accent.TButton", background=[("active", ACCENT_DARK), ("disabled", "#aab6d6")])

        style.configure("Danger.TButton", background="#d9483a", foreground="white",
                         font=("Segoe UI", 9, "bold"), padding=(10, 6), borderwidth=0)
        style.map("Danger.TButton", background=[("active", "#b23a2f"), ("disabled", "#e8b3ac")])

        style.configure("TButton", font=("Segoe UI", 9), padding=(10, 5))
        style.configure("TEntry", padding=4)
        style.configure("TSpinbox", padding=4)
        style.configure("TCombobox", padding=4)
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", font=("Segoe UI", 10), padding=(18, 8))
        style.map("TNotebook.Tab", background=[("selected", CARD_BG)], foreground=[("selected", ACCENT)])
        style.configure("Card.TLabelframe", background=CARD_BG)
        style.configure("Card.TLabelframe.Label", background=CARD_BG, foreground=MUTED, font=("Segoe UI", 9, "bold"))

    # ------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------
    def _build_layout(self):
        container = ttk.Frame(self.root, style="Content.TFrame")
        container.pack(fill="both", expand=True)
        container.columnconfigure(1, weight=1)
        container.rowconfigure(0, weight=1)

        self._build_sidebar(container)

        right = ttk.Frame(container, style="Content.TFrame")
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)

        self.workspace_tabs = ttk.Notebook(right)
        self.workspace_tabs.grid(row=0, column=0, sticky="nsew", padx=12, pady=(12, 0))
        self.workspace_tab = ttk.Frame(self.workspace_tabs, style="Content.TFrame")
        self.activity_tab = ttk.Frame(self.workspace_tabs, style="Content.TFrame")
        self.workspace_tab.columnconfigure(0, weight=1)
        self.workspace_tab.rowconfigure(0, weight=1)
        self.workspace_tabs.add(self.workspace_tab, text="Workspace")
        self.workspace_tabs.add(self.activity_tab, text="Activity Log")
        self.workspace_tabs.bind("<<NotebookTabChanged>>", self._on_workspace_tab_changed)

        # ---- Scrollable content area ----
        # A plain Frame here would clip anything taller than the window
        # (e.g. Check Students with several Stream Group rows added) --
        # the Run button etc. would become invisible AND unreachable.
        # Canvas + Scrollbar keeps every section fully reachable no
        # matter how tall it grows.
        canvas_frame = ttk.Frame(self.workspace_tab, style="Content.TFrame")
        canvas_frame.grid(row=0, column=0, sticky="nsew", padx=(12, 0), pady=(12, 6))
        canvas_frame.columnconfigure(0, weight=1)
        canvas_frame.rowconfigure(0, weight=1)

        self.content_canvas = tk.Canvas(canvas_frame, bg=BG, highlightthickness=0)
        self.content_canvas.grid(row=0, column=0, sticky="nsew")
        content_scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical",
                                           command=self.content_canvas.yview)
        content_scrollbar.grid(row=0, column=1, sticky="ns", padx=(4, 8))
        self.content_canvas.configure(yscrollcommand=content_scrollbar.set)

        self.content_holder = ttk.Frame(self.content_canvas, style="Content.TFrame")
        self.content_holder.columnconfigure(0, weight=1)
        self._content_window = self.content_canvas.create_window(
            (0, 0), window=self.content_holder, anchor="nw")

        def _sync_scrollregion(event=None):
            self.content_canvas.configure(scrollregion=self.content_canvas.bbox("all"))

        def _sync_content_width(event):
            self.content_canvas.itemconfig(self._content_window, width=event.width)

        self.content_holder.bind("<Configure>", _sync_scrollregion)
        self.content_canvas.bind("<Configure>", _sync_content_width)

        def _on_mousewheel(event):
            if self.workspace_tabs.select() != str(self.workspace_tab):
                return  # The Activity Log has its own scrolling.
            # Windows/macOS give event.delta; Linux uses Button-4/5 instead.
            self.content_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self.content_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        self.content_canvas.bind_all("<Button-4>", lambda e: _on_mousewheel(type('Wheel', (), {'delta':120})()))
        self.content_canvas.bind_all("<Button-5>", lambda e: _on_mousewheel(type('Wheel', (), {'delta':-120})()))

        self._build_status_bar(right)
        self._build_log_panel(self.activity_tab)

        for key, builder in [
            ("dashboard", self._build_dashboard),
            ("screenshot", self._build_screenshot_section),
            ("submit", self._build_submit_section),
            ("internal", self._build_internal_section),
            ("inspect", self._build_inspect_section),
            ("browse", self._build_browse_section),
            ("photos", self._build_photos_section),
            ("help", self._build_help_section),
        ]:
            frame = ttk.Frame(self.content_holder, style="Content.TFrame")
            builder(frame)
            self.sections[key] = frame

    def _build_sidebar(self, parent):
        sidebar = ttk.Frame(parent, style="Sidebar.TFrame", width=184)
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)

        header = ttk.Frame(sidebar, style="Sidebar.TFrame")
        header.pack(fill="x", pady=(22, 18), padx=14)
        ttk.Label(header, text="JKBOSE Tool", style="SidebarTitle.TLabel").pack(anchor="w")
        ttk.Label(header, text="School automation", style="SidebarSub.TLabel").pack(anchor="w", pady=(3, 0))

        ttk.Separator(sidebar, orient="horizontal").pack(fill="x", padx=20, pady=(0, 8))

        nav_items = [
            ("dashboard", "Dashboard"),
            ("screenshot", "Check Students"),
            ("submit", "Submit Exam Forms"),
            ("internal", "Internal Assessment"),
            ("inspect", "Inspect Page"),
            ("browse", "Browse Site"),
            ("photos", "Photo Extract / Rename"),
            ("help", "Help"),
        ]
        for key, label in nav_items:
            btn = ttk.Button(sidebar, text=label, style="Sidebar.TButton",
                              command=lambda k=key: self._show_section(k))
            btn.pack(fill="x")
            self.nav_buttons[key] = btn

    def _build_status_bar(self, parent):
        bar = ttk.Frame(parent, style="Content.TFrame")
        bar.grid(row=1, column=0, sticky="ew", padx=20, pady=10)
        bar.columnconfigure(0, weight=1)

        self.status_var = tk.StringVar(value="Ready.")
        ttk.Label(bar, textvariable=self.status_var, style="SubHeader.TLabel", wraplength=380).grid(
            row=0, column=0, sticky="w", pady=3)

        btns = ttk.Frame(bar, style="Content.TFrame")
        btns.grid(row=0, column=1, sticky="e")
        ttk.Button(btns, text="View log", command=lambda: self.workspace_tabs.select(self.activity_tab)).pack(side="left", padx=(0, 8))
        self.force_close_btn = ttk.Button(
            btns, text="Force Close Browser", style="Danger.TButton",
            command=self.force_close_browser)
        self.force_close_btn.pack(side="left", padx=(0, 8))
        self.stop_btn = ttk.Button(
            btns, text="Stop", style="Danger.TButton",
            command=self.stop_task, state="disabled")
        self.stop_btn.pack(side="left")

        self.approval_progress_frame=ttk.Frame(bar,style='Content.TFrame')
        self.approval_progress_frame.grid(row=1,column=0,columnspan=2,sticky='ew',pady=(5,0))
        self.approval_progress_frame.columnconfigure(0,weight=1)
        self.approval_progress_var=tk.StringVar(value='')
        ttk.Label(self.approval_progress_frame,textvariable=self.approval_progress_var,style='SubHeader.TLabel',wraplength=680).grid(row=0,column=0,sticky='w')
        self.approval_progress_bar=ttk.Progressbar(self.approval_progress_frame,mode='determinate')
        self.approval_progress_bar.grid(row=1,column=0,sticky='ew',pady=(3,0))
        self.approval_progress_frame.grid_remove()

    def _show_approval_progress(self,data):
        self.approval_progress_frame.grid()
        self.approval_progress_bar.configure(maximum=max(data['total_records'],1),value=data['verified'])
        self.approval_progress_var.set(f"Class {data['student_class']} | {data['verified']}/{data['total_records']} tracked awards verified | {data['remaining']} awards remaining | {data['students_remaining']}/{data['students_total']} students pending | {data['held']} held/excluded")

    def _build_log_panel(self, parent):
        frame = ttk.Frame(parent, style="Content.TFrame")
        frame.pack(fill="both", expand=True, padx=16, pady=14)
        toolbar = ttk.Frame(frame, style="Content.TFrame")
        toolbar.pack(fill="x", pady=(0, 10))
        ttk.Label(toolbar, text="Activity Log", style="Header.TLabel").pack(side="left")
        ttk.Button(toolbar, text="Save log…", command=self._save_activity_log).pack(side="right")
        ttk.Button(toolbar, text="Clear view", command=self._log_clear).pack(side="right", padx=8)
        self.log_widget = scrolledtext.ScrolledText(
            frame, height=20, bg=LOG_BG, fg=LOG_FG, insertbackground="white",
            font=("Consolas", 9), wrap="word", state="disabled", borderwidth=0)
        self.log_widget.pack(fill="both", expand=True, pady=(4, 0))

    def _on_workspace_tab_changed(self, _event=None):
        if self.workspace_tabs.select() == str(self.activity_tab):
            self.log_unread = False
            self.workspace_tabs.tab(self.activity_tab, text="Activity Log")

    def _save_activity_log(self):
        path = filedialog.asksaveasfilename(title="Save activity log", defaultextension=".txt", filetypes=[("Text log", "*.txt")])
        if path:
            try:
                Path(path).write_text(self.log_widget.get("1.0", "end-1c"), encoding="utf-8")
            except OSError as error:
                messagebox.showerror(APP_TITLE, str(error))

    # ------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------
    def _section_header(self, parent, title, subtitle):
        ttk.Label(parent, text=title, style="Header.TLabel").pack(anchor="w")
        ttk.Label(parent, text=subtitle, style="SubHeader.TLabel", wraplength=680).pack(
            anchor="w", pady=(1, 10))

    def _card(self, parent):
        outer = ttk.Frame(parent, style="Content.TFrame")
        outer.pack(fill="both", expand=True)
        card = ttk.Frame(outer, style="Card.TFrame", padding=12)
        card.pack(fill="x")
        return card

    def _field_row(self, card, label, var, browse_kind=None, filetypes=None,
                   default_ext=None, help_text=None):
        """browse_kind: None | 'open' | 'save' | 'dir'"""
        row = ttk.Frame(card, style="Card.TFrame")
        row.pack(fill="x", pady=3)
        ttk.Label(row, text=label, style="Card.TLabel", width=17, anchor="w").pack(side="left")
        entry = ttk.Entry(row, textvariable=var)
        entry.pack(side="left", fill="x", expand=True, padx=(4, 8))

        if browse_kind:
            def browse():
                path = None
                if browse_kind == "dir":
                    path = filedialog.askdirectory()
                elif browse_kind == "save":
                    path = filedialog.asksaveasfilename(
                        defaultextension=default_ext or "",
                        filetypes=filetypes or [("All files", "*.*")])
                else:
                    path = filedialog.askopenfilename(
                        filetypes=filetypes or [("All files", "*.*")])
                if path:
                    var.set(path)
            ttk.Button(row, text="Browse…", command=browse).pack(side="left")

        if help_text:
            ttk.Label(card, text=help_text, style="Muted.Card.TLabel", wraplength=580).pack(
                anchor="w", pady=(0, 2))
        return entry

    def _class_row(self, card, var, help_text):
        """Class (11/12) dropdown row -- the site requires this be set
        BEFORE the registration number on every lookup."""
        row = ttk.Frame(card, style="Card.TFrame")
        row.pack(fill="x", pady=3)
        ttk.Label(row, text="Class", style="Card.TLabel", width=17, anchor="w").pack(side="left")
        combo = ttk.Combobox(row, textvariable=var, values=["11", "12"],
                              state="readonly", width=8)
        combo.pack(side="left", padx=(4, 8))
        if help_text:
            ttk.Label(card, text=help_text, style="Muted.Card.TLabel", wraplength=600).pack(
                anchor="w", padx=(128, 0), pady=(0, 2))
        return combo

    def _run_button(self, card, text, command):
        btn_row = ttk.Frame(card, style="Card.TFrame")
        btn_row.pack(fill="x", pady=(10, 0))
        btn = ttk.Button(btn_row, text=text, style="Accent.TButton", command=command)
        btn.pack(anchor="w")
        self.run_buttons.append(btn)
        return btn

    # ---- Dashboard ----
    def _build_dashboard(self, parent):
        self._section_header(
            parent, "Dashboard",
            "One tool for automating tasks on jkbose.jk.gov.in. Pick a task "
            "from the left. Every task opens its own Chrome window and asks "
            "you to log in (and solve the captcha) manually the first time -- "
            "the session is then reused across runs.")
        card = self._card(parent)

        ttk.Label(card, text="Site", style="Card.TLabel", width=17, anchor="w").grid(
            row=0, column=0, sticky="w", pady=4)
        ttk.Label(card, text=config.LOGIN_URL, style="Card.TLabel").grid(
            row=0, column=1, sticky="w", pady=4)

        ttk.Label(card, text="Saved login session", style="Card.TLabel", width=17, anchor="w").grid(
            row=1, column=0, sticky="w", pady=4)
        self.session_status_var = tk.StringVar()
        ttk.Label(card, textvariable=self.session_status_var, style="Card.TLabel").grid(
            row=1, column=1, sticky="w", pady=4)
        self._refresh_session_status()

        ttk.Button(card, text="Refresh", command=self._refresh_session_status).grid(
            row=1, column=2, sticky="w", padx=(12, 0))

        ttk.Separator(card, orient="horizontal").grid(
            row=2, column=0, columnspan=3, sticky="ew", pady=16)

        tips = (
            "• \"Check Students\" looks up RR numbers one by one and saves a screenshot of each result.\n"
            "• \"Submit Exam Forms\" fills the exam form row-by-row from an Excel sheet; you solve the "
            "captcha and click Submit for each one.\n"
            "• \"Inspect Page\" dumps field IDs from a live page to a CSV -- use it whenever the site's "
            "forms change and automation starts failing.\n"
            "• \"Browse Site\" just opens a logged-in browser window with no automation, for looking around.\n"
            "• \"Photo Extract / Rename\" copies photos by registration number from a large source folder and can rename them by class roll.\n"
            "• Both \"Check Students\" and \"Submit Exam Forms\" ask for a Class (11/12) up front -- the "
            "site requires the Class dropdown be set before every registration-number lookup."
        )
        ttk.Label(card, text=tips, style="Card.TLabel", justify="left", wraplength=680).grid(
            row=3, column=0, columnspan=3, sticky="w")

    def _refresh_session_status(self):
        profile_dir = Path(config.CHROME_PROFILE_DIR) if config.CHROME_PROFILE_DIR else None
        if profile_dir and profile_dir.exists():
            self.session_status_var.set("Found — you likely won't need to log in again.")
        else:
            self.session_status_var.set("None yet — you'll be asked to log in on first use.")

    # ---- Check Students (screenshot) ----
    def _build_screenshot_section(self, parent):
        self._section_header(
            parent, "Check Students",
            "Looks up each RR number in a text file, opens its registration "
            "details, and saves a compressed screenshot of the result.")
        card = self._card(parent)

        self.ss_rr_file = tk.StringVar()
        self._field_row(card, "RR numbers file", self.ss_rr_file, browse_kind="open",
                         filetypes=[("Automation Excel", "*.xlsx"), ("Text files", "*.txt"), ("All files", "*.*")],
                         help_text="Automation Excel (Sheet2) or one RR number per line in .txt.")

        self.ss_class = tk.StringVar(value="12")
        self._class_row(card, self.ss_class,
                         "Set before every lookup -- required by the site's Class dropdown.")

        # ---- Stream groups: map serial-number ranges to a Stream ----
        ttk.Separator(card, orient="horizontal").pack(fill="x", pady=(6, 5))
        stream_header = ttk.Frame(card, style="Card.TFrame")
        stream_header.pack(fill="x")
        ttk.Label(stream_header, text="Stream groups", style="Card.TLabel",
                  font=("Segoe UI", 10, "bold")).pack(side="left")
        ttk.Label(
            card,
            text="Before the subjects screenshot, Stream is set per student based on its "
                 "serial number (line number in the RR file, matching the '#' in each output "
                 "filename). E.g. Stream 'Science', serials '1-40, 55' covers RR lines 1-40 and 55.",
            style="Muted.Card.TLabel", wraplength=620,
        ).pack(anchor="w", pady=(2, 8))

        self.ss_stream_rows_frame = ttk.Frame(card, style="Card.TFrame")
        self.ss_stream_rows_frame.pack(fill="x")
        self.ss_stream_rows = []  # list of (stream_var, serials_var, row_frame)
        self._add_stream_row()  # start with one row

        ttk.Button(card, text="+ Add Stream Group", command=self._add_stream_row).pack(
            anchor="w", pady=(3, 0))
        ttk.Separator(card, orient="horizontal").pack(fill="x", pady=(6, 0))

        self.ss_output_dir = tk.StringVar()
        self._field_row(card, "Output folder", self.ss_output_dir, browse_kind="dir",
                         help_text="Leave blank to save next to the RR file.")

        # ---- Output mode: screenshot (image) vs PDF (whole page) ----
        mode_row = ttk.Frame(card, style="Card.TFrame")
        mode_row.pack(fill="x", pady=3)
        ttk.Label(mode_row, text="Save as", style="Card.TLabel", width=17, anchor="w").pack(side="left")
        self.ss_output_mode = tk.StringVar(value="screenshot")
        ttk.Radiobutton(mode_row, text="Screenshot (image)", value="screenshot",
                         variable=self.ss_output_mode, command=self._toggle_output_mode).pack(side="left")
        ttk.Radiobutton(mode_row, text="PDF (whole page)", value="pdf",
                         variable=self.ss_output_mode, command=self._toggle_output_mode).pack(side="left", padx=(12, 0))
        ttk.Label(
            card,
            text="PDF captures the entire page in one shot (no scrolling/stitching needed), "
                 "with crisp text and usually a smaller file. Screenshot matches exactly what's "
                 "on screen -- safer if the page looks different when printed.",
            style="Muted.Card.TLabel", wraplength=620,
        ).pack(anchor="w", padx=(128, 0), pady=(0, 2))

        # ---- Capture mode (screenshot only): top-only (fast) vs top+subjects ----
        self.ss_capture_row = ttk.Frame(card, style="Card.TFrame")
        self.ss_capture_row.pack(fill="x", pady=3)
        ttk.Label(self.ss_capture_row, text="Capture", style="Card.TLabel", width=17, anchor="w").pack(side="left")
        self.ss_capture_mode = tk.StringVar(value="top_and_subjects")
        ttk.Radiobutton(self.ss_capture_row, text="Top only (faster)", value="top",
                         variable=self.ss_capture_mode).pack(side="left")
        ttk.Radiobutton(self.ss_capture_row, text="Top + Subjects (default)", value="top_and_subjects",
                         variable=self.ss_capture_mode).pack(side="left", padx=(12, 0))
        ttk.Label(
            card,
            text="\"Top + Subjects\" takes a second shot scrolled to the SUBJECT DETAILS heading "
                 "and stacks it below the top -- slower (one extra screenshot per student) but "
                 "includes Subjects. \"Top only\" skips that entirely for speed.",
            style="Muted.Card.TLabel", wraplength=620,
        ).pack(anchor="w", padx=(128, 0), pady=(0, 2))

        self.ss_format_row = ttk.Frame(card, style="Card.TFrame")
        self.ss_format_row.pack(fill="x", pady=3)
        ttk.Label(self.ss_format_row, text="Format", style="Card.TLabel", width=17, anchor="w").pack(side="left")
        self.ss_format = tk.StringVar(value="png")
        ttk.Radiobutton(self.ss_format_row, text="PNG (crisp text, default)", value="png",
                         variable=self.ss_format, command=self._toggle_jpeg_quality).pack(side="left")
        ttk.Radiobutton(self.ss_format_row, text="JPEG (smallest files)", value="jpeg",
                         variable=self.ss_format, command=self._toggle_jpeg_quality).pack(side="left", padx=(12, 0))

        self.ss_quality_row = ttk.Frame(card, style="Card.TFrame")
        self.ss_quality_row.pack(fill="x", pady=3)
        ttk.Label(self.ss_quality_row, text="JPEG quality", style="Card.TLabel", width=17, anchor="w").pack(side="left")
        self.ss_jpeg_quality = tk.StringVar(value="80")
        self.ss_quality_spin = ttk.Spinbox(self.ss_quality_row, from_=1, to=100, width=6,
                                            textvariable=self.ss_jpeg_quality, state="disabled")
        self.ss_quality_spin.pack(side="left")

        self._run_button(card, "Run — Check Students", self.run_screenshot)

    def _toggle_jpeg_quality(self):
        self.ss_quality_spin.configure(state=("normal" if self.ss_format.get() == "jpeg" else "disabled"))

    def _toggle_output_mode(self):
        is_pdf = self.ss_output_mode.get() == "pdf"
        state = "disabled" if is_pdf else "normal"
        for child in self.ss_format_row.winfo_children():
            child.configure(state=state)
        for child in self.ss_capture_row.winfo_children():
            child.configure(state=state)
        if is_pdf:
            self.ss_quality_spin.configure(state="disabled")
        else:
            self._toggle_jpeg_quality()

    def _add_stream_row(self):
        row = ttk.Frame(self.ss_stream_rows_frame, style="Card.TFrame")
        row.pack(fill="x", pady=1)

        ttk.Label(row, text="Stream", style="Card.TLabel").pack(side="left")
        stream_var = tk.StringVar()
        ttk.Entry(row, textvariable=stream_var, width=16).pack(side="left", padx=(4, 12))

        ttk.Label(row, text="Serial #s", style="Card.TLabel").pack(side="left")
        serials_var = tk.StringVar()
        ttk.Entry(row, textvariable=serials_var, width=28).pack(side="left", padx=(4, 8))

        entry = [stream_var, serials_var, row]

        def remove():
            row.destroy()
            self.ss_stream_rows.remove(entry)

        ttk.Button(row, text="✕", width=3, command=remove).pack(side="left")

        self.ss_stream_rows.append(entry)

    def _collect_stream_map(self):
        pairs = [(v.get().strip(), s.get().strip()) for v, s, _ in self.ss_stream_rows]
        pairs = [(v, s) for v, s in pairs if v and s]
        if not pairs:
            return None
        from jkbose_tool.utils import build_stream_map
        return build_stream_map(pairs)

    # ---- Submit Forms ----
    def _build_submit_section(self, parent):
        self._section_header(
            parent, "Submit Exam Forms",
            "Fills the exam form row-by-row from an Excel sheet (stream, "
            "personal info, address, subjects, photo/signature). For pending rows, "
            "solve the captcha and click Submit in Chrome; the tool continues automatically.")
        card = self._card(parent)

        self.sf_excel = tk.StringVar()
        self._field_row(card, "Excel file", self.sf_excel, browse_kind="open",
                         filetypes=[("Excel workbook", "*.xlsx"), ("All files", "*.*")],
                         help_text="One row per student. 'Status' and 'Notes' columns are added/updated as it runs.")

        self.sf_sheet = tk.StringVar(value="Sheet2")
        self._field_row(card, "Sheet name", self.sf_sheet)

        self.sf_photos = tk.StringVar()
        self._field_row(card, "Photos folder", self.sf_photos, browse_kind="dir",
                         help_text="Folder containing the photo/signature files referenced by the sheet.")

        self.sf_class = tk.StringVar(value="")
        combo = self._class_row(
            card, self.sf_class,
            "Leave blank to use each row's own 'Class' column instead of one fixed value.")
        combo.configure(values=["", "11", "12"])

        # Subject entry method. Friendly names are the default; legacy numeric
        # Group*_choice codes remain available for existing workbooks.
        moderow = ttk.Frame(card, style="Card.TFrame")
        moderow.pack(fill="x", pady=(7, 2))
        ttk.Label(moderow, text="Subject Input Mode", style="Card.TLabel").pack(side="left", padx=(0, 12))
        self.sf_subject_mode = tk.StringVar(value="Subject Names (recommended)")
        modecombo = ttk.Combobox(moderow, textvariable=self.sf_subject_mode, state="readonly", width=30,
                                 values=["Subject Names (recommended)", "Subject Codes (legacy)"])
        modecombo.pack(side="left")
        ttk.Label(moderow, text="Names use sub1/sub2/...; Codes use Group*_choice / SubjectCode*.",
                  style="Muted.Card.TLabel").pack(side="left", padx=(10, 0))

        resumerow = ttk.Frame(card, style="Card.TFrame")
        resumerow.pack(fill="x", pady=(7, 2))
        ttk.Label(resumerow, text="Last submitted RegNo", style="Card.TLabel").pack(side="left", padx=(0, 12))
        self.sf_last_submitted_regno = tk.StringVar(value="")
        ttk.Entry(resumerow, textvariable=self.sf_last_submitted_regno, width=28).pack(side="left")
        ttk.Label(
            resumerow,
            text="Optional. Skip this exact row + everything above it; process every row below it. Takes priority over old Status values.",
            style="Muted.Card.TLabel", wraplength=720,
        ).pack(side="left", padx=(10, 0))

        skiprow = ttk.Frame(card, style="Card.TFrame")
        skiprow.pack(fill="x", pady=(7, 2))
        self.sf_auto_skip_submitted = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            skiprow, text="Auto-skip completed / already-submitted records (Class 11 & 12)",
            variable=self.sf_auto_skip_submitted
        ).pack(side="left")
        ttk.Label(skiprow, text="Used when Last submitted RegNo is blank; Submitted - verified rows are silently excluded.",
                  style="Muted.Card.TLabel").pack(side="left", padx=(10, 0))

        templaterow = ttk.Frame(card, style="Card.TFrame")
        templaterow.pack(fill="x", pady=(8, 2))
        ttk.Label(templaterow, text="Download template", style="Card.TLabel").pack(side="left", padx=(0, 12))
        ttk.Button(templaterow, text="Download Class 11 Template",
                   command=lambda: self.download_submit_template("11")).pack(side="left", padx=(0, 8))
        ttk.Button(templaterow, text="Download Class 12 Template",
                   command=lambda: self.download_submit_template("12")).pack(side="left")

        ttk.Label(
            card,
            text="No Continue popup is used for Submit Forms. Completed rows are skipped silently; "
                 "for pending rows, solve captcha and click JKBOSE Submit in Chrome and the tool advances automatically.",
            style="Muted.Card.TLabel", wraplength=620,
        ).pack(anchor="w", pady=(6, 0))

        btnrow = ttk.Frame(card, style="Card.TFrame")
        btnrow.pack(fill="x", pady=(10, 0))
        ttk.Button(btnrow, text="Preview & Validate", command=self.preview_submit).pack(side="left", padx=(0, 8))
        runbtn = ttk.Button(btnrow, text="Run — Submit Forms", style="Accent.TButton", command=self.run_submit)
        runbtn.pack(side="left")
        self.run_buttons.append(runbtn)

    # ---- Inspect Page ----
    def _build_inspect_section(self, parent):
        self._section_header(
            parent, "Inspect Page",
            "Logs in, then dumps every field's id/name/label on a page to a "
            "CSV — in page order. Use this whenever the site's fields change "
            "and screenshot/submit start failing with 'element not found'.")
        card = self._card(parent)

        self.in_url = tk.StringVar()
        self._field_row(card, "Page URL (optional)", self.in_url,
                         help_text="Leave blank to navigate there yourself in the browser, "
                                    "then click Continue when you're on the right page.")

        self.in_output = tk.StringVar(value="fields.csv")
        self._field_row(card, "Output CSV", self.in_output, browse_kind="save",
                         filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                         default_ext=".csv")

        self._run_button(card, "Run — Inspect Page", self.run_inspect)

    # ---- Browse Site ----
    def _build_browse_section(self, parent):
        self._section_header(
            parent, "Browse Site",
            "Logs in and leaves the browser open so you can look around the "
            "live site manually — nothing here clicks or fills anything.")
        card = self._card(parent)

        self.br_url = tk.StringVar()
        self._field_row(card, "Page to open (optional)", self.br_url,
                         help_text="Leave blank to land on the default page after login.")

        ttk.Label(
            card,
            text="A Continue prompt will appear here when you're done browsing, to close the browser.",
            style="Muted.Card.TLabel", wraplength=620,
        ).pack(anchor="w", pady=(6, 0))

        self._run_button(card, "Run — Browse Site", self.run_browse)

    # ---- Photo Extract / Rename ----
    def _build_photos_section(self, parent):
        self._section_header(
            parent, "Photo Extract / Rename",
            "Copies only the required student photos from a large photo folder by matching "
            "registration numbers inside filenames. Optionally renames copied photos from a "
            "registration-no,class-roll mapping file. This utility is local only — Chrome is not opened.")
        card = self._card(parent)

        self.ph_reg_file = tk.StringVar()
        self._field_row(
            card, "Reg. numbers file", self.ph_reg_file, browse_kind="open",
            filetypes=[("Text/CSV files", "*.txt *.csv"), ("Text files", "*.txt"), ("All files", "*.*")],
            help_text="One registration number per line. If a comma is present, the first value is used as the registration number.")

        self.ph_source_dir = tk.StringVar()
        self._field_row(
            card, "Source photos", self.ph_source_dir, browse_kind="dir",
            help_text="Folder containing many students' photos. The registration number may appear anywhere in each photo filename.")

        self.ph_destination_dir = tk.StringVar()
        self._field_row(
            card, "Copy into folder", self.ph_destination_dir, browse_kind="dir",
            help_text="Choose an existing folder you created manually. Matching photos are copied here; the source files are never moved or deleted.")

        self.ph_rename_map = tk.StringVar()
        self._field_row(
            card, "Rename map (optional)", self.ph_rename_map, browse_kind="open",
            filetypes=[("Text/CSV files", "*.txt *.csv"), ("Text files", "*.txt"), ("CSV files", "*.csv"), ("All files", "*.*")],
            help_text="Format: registration_no,class_roll — for example 301002068,1 copies a matching JPEG as 1.jpg.")

        opt = ttk.Frame(card, style="Card.TFrame")
        opt.pack(fill="x", pady=(7, 2))
        ttk.Label(opt, text="Options", style="Card.TLabel", width=17, anchor="w").pack(side="left")
        self.ph_recursive = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt, text="Search source subfolders", variable=self.ph_recursive).pack(side="left", padx=(4, 16))
        self.ph_overwrite = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt, text="Overwrite same-named destination files", variable=self.ph_overwrite).pack(side="left")

        ttk.Label(
            card,
            text="If more than one source filename contains the same registration number, the tool logs a warning and uses the shortest/best filename match. "
                 "If a rename mapping is missing for a student, that photo is still copied with its original filename.",
            style="Muted.Card.TLabel", wraplength=650,
        ).pack(anchor="w", pady=(4, 0))

        self._run_button(card, "Run — Extract / Rename Photos", self.run_photos)

    # ---- Help ----
    def _build_help_section(self, parent):
        self._section_header(
            parent, "Help",
            "Where to look if a task starts failing with 'element not found', "
            "or a form's fields visibly change on screen -- or if things feel slow.")
        card = self._card(parent)

        help_text = (
            "The JKBOSE portal has changed field IDs and form layouts before. "
            "When that happens:\n\n"
            "1.  Go to \"Inspect Page\" and run it on the affected page — it writes a "
            "fresh CSV of every field's id/name/label, in page order.\n\n"
            "2.  Compare it against an older CSV dump (keep dated copies, e.g. "
            "fields_2026-08-15.csv) to see what changed.\n\n"
            "3.  Update the ids that changed in jkbose_tool/config.py (mainly FIELD_MAP, "
            "and CLASS_SELECT_ID / GET_DETAILS_BTN_ID / PHOTO_UPLOAD_ID / SIGNATURE_UPLOAD_ID).\n\n"
            "4.  Re-test on one RR number / one row before running a full batch.\n\n"
            "If you're not comfortable editing the Python yourself, run Inspect, "
            "save the resulting CSV plus a screenshot of the live form, and share "
            "them with whoever maintains this tool.\n\n"
            "Speed: fields listed in config.FIELD_MAP that aren't present on the "
            "current page are skipped quickly (a few seconds, config.QUICK_WAIT) "
            "instead of waiting the full 25s each -- if \"Submit Exam Forms\" still "
            "feels slow, it's most likely Chrome/network startup time, not the "
            "field-filling logic."
        )
        ttk.Label(card, text=help_text, style="Card.TLabel", justify="left", wraplength=680).pack(anchor="w")

    # ------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------
    def _show_section(self, key):
        self.workspace_tabs.select(self.workspace_tab)
        for frame in self.sections.values():
            frame.grid_forget()
        self.sections[key].grid(row=0, column=0, sticky="nsew")
        self.content_canvas.yview_moveto(0)
        for k, btn in self.nav_buttons.items():
            btn.configure(style="SidebarActive.TButton" if k == key else "Sidebar.TButton")
        if key == "dashboard":
            self._refresh_session_status()

    # ------------------------------------------------------------
    # "Press ENTER to continue" replacement -- a modal dialog that
    # blocks the background thread (via a threading.Event) until the
    # user clicks Continue, without freezing the GUI itself.
    # ------------------------------------------------------------
    def gui_pause(self, prompt):
        event = threading.Event()

        def show():
            top = tk.Toplevel(self.root)
            top.title("Action needed")
            top.configure(bg=CARD_BG)
            top.transient(self.root)
            top.resizable(False, False)
            top.grab_set()

            frm = ttk.Frame(top, style="Card.TFrame", padding=24)
            frm.pack()
            ttk.Label(frm, text=prompt, style="Card.TLabel", wraplength=380,
                      justify="left", font=("Segoe UI", 10)).pack(pady=(0, 18))

            def cont():
                top.destroy()
                event.set()

            btn = ttk.Button(frm, text="Continue", style="Accent.TButton", command=cont)
            btn.pack()
            top.protocol("WM_DELETE_WINDOW", cont)

            top.update_idletasks()
            x = self.root.winfo_x() + (self.root.winfo_width() - top.winfo_width()) // 2
            y = self.root.winfo_y() + (self.root.winfo_height() - top.winfo_height()) // 2
            top.geometry(f"+{max(x, 0)}+{max(y, 0)}")
            btn.focus_set()

        self.root.after(0, show)
        event.wait()
        return True

    # ------------------------------------------------------------
    # Background task plumbing
    # ------------------------------------------------------------
    def _start_task(self, name, func, kwargs, needs_stop=False):
        if getattr(self.current_driver, "_jkbose_keep_open", False) is True:
            messagebox.showinfo("Browser left open", "Inspect the previous browser, then use Force Close Browser before starting another task.")
            return
        if self.worker and self.worker.is_alive():
            messagebox.showwarning(APP_TITLE, "Another task is already running. Please wait or stop it first.")
            return

        self.stop_event = threading.Event()
        if needs_stop:
            kwargs = dict(kwargs)
            kwargs["stop_event"] = self.stop_event

        self.approval_progress_frame.grid_remove()
        self._log_clear()
        self._log(f"=== Starting: {name} ===\n\n")
        self._set_running(True, name)

        def task():
            old_stdout = sys.stdout
            sys.stdout = QueueWriter(self.msg_queue)
            try:
                func(**kwargs)
                self.msg_queue.put(("status", f"{name}: finished."))
            except Exception as e:
                brief = (str(e).splitlines()[0] if str(e) else type(e).__name__).strip()
                if len(brief) > 220:
                    brief = brief[:217] + "..."
                expected_interruption = type(e).__name__ == "BrowserSessionLost"
                portal_unreachable = "JKBOSE portal could not be reached" in str(e)
                if expected_interruption:
                    self.msg_queue.put(("log", f"\n[STOPPED] {brief}\n"))
                    self.msg_queue.put(("status", f"{name}: interrupted — progress saved; run again to resume."))
                elif portal_unreachable:
                    self.msg_queue.put(("log", f"\n[CONNECTION ERROR] {brief}\n"))
                    self.msg_queue.put(("status", f"{name}: JKBOSE portal not reachable — retry when site/network is available."))
                else:
                    tb = traceback.format_exc()
                    self.msg_queue.put(("log", f"\n[FATAL ERROR] {brief}\n"))
                    self.msg_queue.put(("log", tb + "\n"))
                    self.msg_queue.put(("status", f"{name}: failed — {brief}"))
            finally:
                sys.stdout = old_stdout
                self._release_driver_reference()
                self.msg_queue.put(("done", None))

        self.worker = threading.Thread(target=task, daemon=True)
        self.worker.start()

    def _release_driver_reference(self):
        if getattr(self.current_driver, "_jkbose_keep_open", False) is not True:
            self.current_driver = None

    def _set_driver_ready(self, driver):
        self.current_driver = driver

    def _set_running(self, running, name):
        state = "disabled" if running else "normal"
        for b in self.run_buttons:
            b.configure(state=state)
        self.stop_btn.configure(state=("normal" if running else "disabled"))
        if running:
            self.status_var.set(f"Running: {name}…")

    def stop_task(self):
        if not (self.worker and self.worker.is_alive()):
            return
        self.stop_event.set()
        self._log("\n[INFO] Stop requested — will finish the current step, then stop.\n"
                   "         If it's stuck waiting for login/captcha, use \"Force Close Browser\".\n")

    def force_close_browser(self):
        if self.current_driver is None:
            messagebox.showinfo(APP_TITLE, "No automation browser window is currently open.")
            return
        if messagebox.askyesno(
                APP_TITLE,
                "Force close the automation browser window now?\n\n"
                "The current task will stop (with an error) if one is running."):
            self.stop_event.set()
            try:
                self.current_driver.quit()
            except Exception:
                pass
            finally:
                self.current_driver = None

    # ------------------------------------------------------------
    # Log panel helpers
    # ------------------------------------------------------------
    def _log(self, text):
        self.log_widget.configure(state="normal")
        self.log_widget.insert(tk.END, text)
        self.log_widget.see(tk.END)
        self.log_widget.configure(state="disabled")
        if self.workspace_tabs.select() != str(self.activity_tab):
            self.log_unread = True
            self.workspace_tabs.tab(self.activity_tab, text="Activity Log •")

    def _log_clear(self):
        self.log_widget.configure(state="normal")
        self.log_widget.delete("1.0", tk.END)
        self.log_widget.configure(state="disabled")
        self.log_unread = False
        self.workspace_tabs.tab(self.activity_tab, text="Activity Log")

    def _poll_queue(self):
        try:
            while True:
                kind, payload = self.msg_queue.get_nowait()
                if kind == "log":
                    self._log(payload)
                elif kind == "status":
                    self.status_var.set(payload)
                elif kind == "approval_progress":
                    self._show_approval_progress(payload)
                elif kind == "done":
                    self._set_running(False, None)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)

    # ------------------------------------------------------------
    # Run handlers -- one per section, each builds kwargs for the
    # matching main.cmd_* function and hands it to _start_task.
    # ------------------------------------------------------------
    def run_browse(self):
        url = self.br_url.get().strip() or None
        kwargs = dict(url=url, pause_callback=self.gui_pause, on_driver_ready=self._set_driver_ready)
        self._start_task("Browse Site", cli.cmd_browse, kwargs)

    def run_inspect(self):
        url = self.in_url.get().strip() or None
        output = self.in_output.get().strip() or "fields.csv"
        kwargs = dict(url=url, output=output, pause_callback=self.gui_pause,
                       on_driver_ready=self._set_driver_ready)
        self._start_task("Inspect Page", cli.cmd_inspect, kwargs)

    def run_screenshot(self):
        rr_file = self.ss_rr_file.get().strip()
        if not rr_file:
            messagebox.showwarning(APP_TITLE, "Please choose an RR numbers text file.")
            return
        if not Path(rr_file).exists():
            messagebox.showwarning(APP_TITLE, f"File not found:\n{rr_file}")
            return
        student_class = self.ss_class.get().strip() or None
        try:
            stream_map = self._collect_stream_map()
        except Exception as e:
            messagebox.showwarning(APP_TITLE, f"Couldn't parse a Stream group's serial numbers:\n{e}")
            return
        output_dir = self.ss_output_dir.get().strip() or None
        output_mode = self.ss_output_mode.get()
        fmt = self.ss_format.get()
        jpeg_quality = None
        if output_mode != "pdf" and fmt == "jpeg":
            try:
                jpeg_quality = int(self.ss_jpeg_quality.get())
            except ValueError:
                jpeg_quality = 80
        capture_mode = self.ss_capture_mode.get()
        kwargs = dict(rr_file=rr_file, output_dir=output_dir, fmt=fmt, jpeg_quality=jpeg_quality,
                      student_class=student_class, stream_map=stream_map, output_mode=output_mode,
                      capture_mode=capture_mode, on_driver_ready=self._set_driver_ready)
        self._start_task("Check Students", cli.cmd_screenshot, kwargs, needs_stop=True)

    def run_photos(self):
        reg_file = self.ph_reg_file.get().strip()
        source_dir = self.ph_source_dir.get().strip()
        destination_dir = self.ph_destination_dir.get().strip()
        rename_map_file = self.ph_rename_map.get().strip() or None

        if not reg_file or not source_dir or not destination_dir:
            messagebox.showwarning(APP_TITLE, "Please choose the registration-number file, source photo folder, and destination folder.")
            return
        if not Path(reg_file).is_file():
            messagebox.showwarning(APP_TITLE, f"Registration-number file not found:\n{reg_file}")
            return
        if not Path(source_dir).is_dir():
            messagebox.showwarning(APP_TITLE, f"Source photo folder not found:\n{source_dir}")
            return
        if not Path(destination_dir).is_dir():
            messagebox.showwarning(APP_TITLE, f"Destination folder not found:\n{destination_dir}\n\nCreate it manually first, then select it.")
            return
        if rename_map_file and not Path(rename_map_file).is_file():
            messagebox.showwarning(APP_TITLE, f"Rename mapping file not found:\n{rename_map_file}")
            return

        kwargs = dict(
            reg_file=reg_file, source_dir=source_dir, destination_dir=destination_dir,
            rename_map_file=rename_map_file, recursive=self.ph_recursive.get(),
            overwrite=self.ph_overwrite.get(),
        )
        self._start_task("Photo Extract / Rename", cli.cmd_photos, kwargs, needs_stop=True)

    def download_submit_template(self, student_class):
        """Save the bundled template matching class and selected subject mode."""
        mode = "codes" if getattr(self, "sf_subject_mode", tk.StringVar(value="")).get().startswith("Subject Codes") else "names"
        if str(student_class) == "11":
            filename = ("JKBOSE_Class_11_Submit_Template_Codes.xlsx" if mode == "codes"
                        else "JKBOSE_Class_11_Submit_Template.xlsx")
        else:
            filename = "JKBOSE_Class_12_Submit_Template.xlsx"
        source = Path(__file__).resolve().parent / "templates" / filename
        if not source.exists():
            messagebox.showerror(APP_TITLE, f"Bundled template is missing:\n{source}")
            return
        target = filedialog.asksaveasfilename(
            title=f"Save Class {student_class} submit template",
            defaultextension=".xlsx",
            initialfile=filename,
            filetypes=[("Excel workbook", "*.xlsx")],
        )
        if not target:
            return
        try:
            shutil.copyfile(source, target)
            messagebox.showinfo(APP_TITLE, f"Template saved successfully:\n{target}")
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"Could not save template:\n{e}")

    def _submit_inputs(self):
        excel_file = self.sf_excel.get().strip()
        photos_dir = self.sf_photos.get().strip()
        sheet = self.sf_sheet.get().strip() or "Sheet2"
        student_class = self.sf_class.get().strip() or None
        subject_input_mode = "codes" if self.sf_subject_mode.get().startswith("Subject Codes") else "names"
        if not excel_file:
            messagebox.showwarning(APP_TITLE, "Please choose the Excel file.")
            return None
        if not Path(excel_file).exists():
            messagebox.showwarning(APP_TITLE, f"File not found:\n{excel_file}")
            return None
        if photos_dir and not Path(photos_dir).exists():
            messagebox.showwarning(APP_TITLE, f"Folder not found:\n{photos_dir}")
            return None
        last_submitted_regno = self.sf_last_submitted_regno.get().strip()
        return excel_file, sheet, photos_dir, student_class, subject_input_mode, bool(self.sf_auto_skip_submitted.get()), last_submitted_regno

    def preview_submit(self, require_confirm=False):
        vals = self._submit_inputs()
        if not vals:
            return False
        excel_file, sheet, photos_dir, student_class, subject_input_mode, auto_skip_submitted, last_submitted_regno = vals
        try:
            rows = build_preflight(excel_file, sheet, photos_dir, student_class, subject_input_mode)
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"Could not build preview:\n{e}")
            return False

        top = tk.Toplevel(self.root)
        top.title("Submit Preview & Validation")
        top.geometry("1180x650")
        top.transient(self.root)
        result = {"go": not require_confirm}

        head = ttk.Frame(top, padding=(12, 10))
        head.pack(fill="x")
        problems = sum(1 for r in rows if r["issues"])
        ttk.Label(head, text=f"{len(rows)} students • {problems} rows with warnings",
                  font=("Segoe UI", 11, "bold")).pack(side="left")
        ttk.Label(head, text=f"Subject mode: {subject_input_mode.title()}", foreground=MUTED).pack(side="left", padx=18)
        if last_submitted_regno:
            ttk.Label(head, text=f"Resume after: {last_submitted_regno}", foreground=MUTED).pack(side="left", padx=18)
        ttk.Label(head, text="Class 12: stream/subjects/photo/signature are not submitted.",
                  foreground=MUTED).pack(side="left", padx=18)

        body = ttk.Panedwindow(top, orient="horizontal")
        body.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        left = ttk.Frame(body)
        right = ttk.Frame(body, padding=12)
        body.add(left, weight=5); body.add(right, weight=2)

        cols=("row","regno","class","stream","optional","vocational","photo","signature","issues")
        tree=ttk.Treeview(left, columns=cols, show="headings", selectmode="browse")
        widths={"row":50,"regno":145,"class":55,"stream":90,"optional":230,"vocational":145,"photo":70,"signature":70,"issues":260}
        optional_title = "Optional Codes" if subject_input_mode == "codes" else "Optional Subjects"
        vocational_title = "Vocational Code" if subject_input_mode == "codes" else "Vocational"
        titles={"row":"Excel Row","regno":"Registration No","class":"Class","stream":"Stream","optional":optional_title,"vocational":vocational_title,"photo":"Photo","signature":"Signature","issues":"Validation / Warnings"}
        for c in cols:
            tree.heading(c,text=titles[c]); tree.column(c,width=widths[c],anchor="w")
        vs=ttk.Scrollbar(left,orient="vertical",command=tree.yview); hs=ttk.Scrollbar(left,orient="horizontal",command=tree.xview)
        tree.configure(yscrollcommand=vs.set,xscrollcommand=hs.set)
        tree.grid(row=0,column=0,sticky="nsew"); vs.grid(row=0,column=1,sticky="ns"); hs.grid(row=1,column=0,sticky="ew")
        left.rowconfigure(0,weight=1); left.columnconfigure(0,weight=1)
        row_by_iid={}
        for n,r in enumerate(rows):
            iid=str(n); row_by_iid[iid]=r
            photo_state = "N/A" if r["class"] == "12" else ("OK" if r["photo"] and Path(r["photo"]).exists() else "Missing")
            sign_state = "N/A" if r["class"] == "12" else ("OK" if r["signature"] and Path(r["signature"]).exists() else "Missing")
            tree.insert("", "end", iid=iid, values=(r["row"],r["regno"],r["class"],r["stream"],r.get("optional", ""),r.get("vocational", ""),
                        photo_state, sign_state, r["issues"]))

        ttk.Label(right,text="Selected student",font=("Segoe UI",11,"bold")).pack(anchor="w")
        details=tk.StringVar(value="Select a row to inspect files.")
        ttk.Label(right,textvariable=details,wraplength=320,justify="left").pack(anchor="w",pady=(4,10))
        imgrow=ttk.Frame(right); imgrow.pack(fill="x")
        photo_label=ttk.Label(imgrow,text="Photo\n(no preview)",anchor="center"); photo_label.pack(side="left",padx=(0,8))
        sign_label=ttk.Label(imgrow,text="Signature\n(no preview)",anchor="center"); sign_label.pack(side="left")
        top._preview_images=[]
        def load_img(path, max_size):
            if not path or not Path(path).exists(): return None
            try:
                im=Image.open(path); im.thumbnail(max_size); return ImageTk.PhotoImage(im)
            except Exception: return None
        def on_sel(event=None):
            sel=tree.selection()
            if not sel:return
            r=row_by_iid[sel[0]]
            details.set(
                f"RegNo: {r['regno']}\nClass: {r['class']}\nStream: {r['stream'] or '—'}\n"
                f"Compulsory: {r.get('compulsory') or '—'}\nOptional: {r.get('optional') or '—'}\n"
                f"Vocational: {r.get('vocational') or '—'}\n\n{r['issues'] or 'No preflight warnings.'}"
            )
            pimg=load_img(r['photo'],(145,180)); simg=load_img(r['signature'],(180,90))
            top._preview_images=[pimg,simg]
            photo_label.configure(image=pimg,text="" if pimg else "Photo\nmissing/unreadable",compound="top")
            sign_label.configure(image=simg,text="" if simg else "Signature\nmissing/unreadable",compound="top")
        tree.bind("<<TreeviewSelect>>",on_sel)
        if rows: tree.selection_set("0"); on_sel()

        foot=ttk.Frame(top,padding=(12,0,12,12)); foot.pack(fill="x")
        ttk.Button(foot,text="Close",command=top.destroy).pack(side="right")
        if require_confirm:
            def proceed(): result["go"]=True; top.destroy()
            ttk.Button(foot,text="Proceed to Submit",style="Accent.TButton",command=proceed).pack(side="right",padx=(0,8))
        top.grab_set(); self.root.wait_window(top)
        return result["go"]

    def run_submit(self):
        vals = self._submit_inputs()
        if not vals:
            return
        if not self.preview_submit(require_confirm=True):
            return
        excel_file, sheet, photos_dir, student_class, subject_input_mode, auto_skip_submitted, last_submitted_regno = vals
        kwargs = dict(excel_file=excel_file, sheet=sheet, photos_dir=photos_dir,
                      student_class=student_class, subject_input_mode=subject_input_mode,
                      auto_skip_submitted=auto_skip_submitted,
                      last_submitted_regno=last_submitted_regno or None,
                      pause_callback=None, on_driver_ready=self._set_driver_ready)
        self._start_task("Submit Forms", cli.cmd_submit, kwargs, needs_stop=True)


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
