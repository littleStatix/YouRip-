"""YouRip desktop GUI built with tkinter."""

import os
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Optional

import downloader
from config import (
    APP_NAME,
    APP_VERSION,
    AUDIO_FORMATS,
    DEFAULT_AUDIO_FORMAT,
    DEFAULT_AUDIO_QUALITY,
    DEFAULT_DOWNLOAD_DIR,
    VIDEO_FORMATS,
    DEFAULT_VIDEO_FORMAT,
    WINDOW_HEIGHT,
    WINDOW_TITLE,
    WINDOW_WIDTH,
)


class YouRipApp(tk.Tk):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()
        self.title(WINDOW_TITLE)
        self.resizable(False, False)
        self._center_window(WINDOW_WIDTH, WINDOW_HEIGHT)

        self._output_dir = tk.StringVar(value=DEFAULT_DOWNLOAD_DIR)
        self._url_var = tk.StringVar()
        self._audio_only = tk.BooleanVar(value=True)
        self._no_playlist = tk.BooleanVar(value=False)
        self._audio_format = tk.StringVar(value=DEFAULT_AUDIO_FORMAT)
        self._audio_quality = tk.StringVar(value=DEFAULT_AUDIO_QUALITY)
        self._video_format = tk.StringVar(value=DEFAULT_VIDEO_FORMAT)
        self._status_var = tk.StringVar(value="Ready")
        self._progress_var = tk.DoubleVar(value=0.0)

        self._build_ui()

    # ------------------------------------------------------------------
    # Window helpers
    # ------------------------------------------------------------------

    def _center_window(self, width: int, height: int) -> None:
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - width) // 2
        y = (sh - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        pad = {"padx": 12, "pady": 6}

        # ── Header ──────────────────────────────────────────────────────
        header = tk.Frame(self, bg="#1a1a2e")
        header.pack(fill=tk.X)
        tk.Label(
            header,
            text=f"♪  {APP_NAME}  v{APP_VERSION}",
            font=("Helvetica", 18, "bold"),
            fg="#e94560",
            bg="#1a1a2e",
        ).pack(pady=10)

        # ── URL input ───────────────────────────────────────────────────
        url_frame = ttk.LabelFrame(self, text="Track / Playlist URL")
        url_frame.pack(fill=tk.X, **pad)

        ttk.Entry(url_frame, textvariable=self._url_var, width=60).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=6, pady=6
        )
        ttk.Button(url_frame, text="Paste", command=self._paste_url).pack(
            side=tk.LEFT, padx=(0, 6), pady=6
        )

        # ── Options ─────────────────────────────────────────────────────
        opt_frame = ttk.LabelFrame(self, text="Options")
        opt_frame.pack(fill=tk.X, **pad)

        ttk.Checkbutton(
            opt_frame,
            text="Audio only",
            variable=self._audio_only,
            command=self._on_audio_toggle,
        ).grid(row=0, column=0, sticky=tk.W, padx=6, pady=4)

        ttk.Checkbutton(
            opt_frame,
            text="Single track only (skip playlist)",
            variable=self._no_playlist,
        ).grid(row=1, column=0, sticky=tk.W, padx=6, pady=4)

        ttk.Label(opt_frame, text="Audio format:").grid(
            row=0, column=1, sticky=tk.W, padx=(12, 2)
        )
        self._audio_fmt_combo = ttk.Combobox(
            opt_frame,
            textvariable=self._audio_format,
            values=AUDIO_FORMATS,
            width=7,
            state="readonly",
        )
        self._audio_fmt_combo.grid(row=0, column=2, sticky=tk.W)

        ttk.Label(opt_frame, text="Quality (kbps):").grid(
            row=0, column=3, sticky=tk.W, padx=(12, 2)
        )
        ttk.Entry(opt_frame, textvariable=self._audio_quality, width=6).grid(
            row=0, column=4, sticky=tk.W
        )

        ttk.Label(opt_frame, text="Video format:").grid(
            row=1, column=1, sticky=tk.W, padx=(12, 2)
        )
        self._video_fmt_combo = ttk.Combobox(
            opt_frame,
            textvariable=self._video_format,
            values=VIDEO_FORMATS,
            width=7,
            state="readonly",
        )
        self._video_fmt_combo.grid(row=1, column=2, sticky=tk.W, pady=4)
        self._on_audio_toggle()

        # ── Output directory ────────────────────────────────────────────
        dir_frame = ttk.LabelFrame(self, text="Save to")
        dir_frame.pack(fill=tk.X, **pad)

        ttk.Entry(dir_frame, textvariable=self._output_dir, width=55).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=6, pady=6
        )
        ttk.Button(dir_frame, text="Browse…", command=self._browse_dir).pack(
            side=tk.LEFT, padx=(0, 6), pady=6
        )

        # ── Progress ────────────────────────────────────────────────────
        prog_frame = ttk.Frame(self)
        prog_frame.pack(fill=tk.X, **pad)

        self._progress_bar = ttk.Progressbar(
            prog_frame, variable=self._progress_var, maximum=100
        )
        self._progress_bar.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(prog_frame, textvariable=self._status_var).pack(anchor=tk.W)

        # ── Action buttons ──────────────────────────────────────────────
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=10)

        self._download_btn = ttk.Button(
            btn_frame, text="⬇  Download", command=self._start_download, width=18
        )
        self._download_btn.pack(side=tk.LEFT, padx=6)

        ttk.Button(
            btn_frame, text="📂  Open folder", command=self._open_folder, width=18
        ).pack(side=tk.LEFT, padx=6)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_audio_toggle(self) -> None:
        audio_only = self._audio_only.get()
        state = "readonly" if audio_only else "disabled"
        self._audio_fmt_combo.configure(state=state)
        self._video_fmt_combo.configure(
            state="disabled" if audio_only else "readonly"
        )

    def _paste_url(self) -> None:
        try:
            text = self.clipboard_get()
            self._url_var.set(text.strip())
        except tk.TclError:
            pass

    def _browse_dir(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self._output_dir.get())
        if chosen:
            self._output_dir.set(chosen)

    def _open_folder(self) -> None:
        path = self._output_dir.get()
        os.makedirs(path, exist_ok=True)
        try:
            if sys.platform == "win32":
                os.startfile(path)  # noqa: S606
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])  # noqa: S603,S607
            else:
                subprocess.Popen(["xdg-open", path])  # noqa: S603,S607
        except Exception:  # noqa: BLE001
            pass

    def _start_download(self) -> None:
        url = self._url_var.get().strip()
        if not url:
            messagebox.showwarning(APP_NAME, "Please enter a URL first.")
            return

        self._download_btn.configure(state="disabled")
        self._progress_var.set(0)
        self._status_var.set("Starting download…")

        downloader.download_async(
            url=url,
            output_dir=self._output_dir.get(),
            audio_only=self._audio_only.get(),
            audio_format=self._audio_format.get(),
            audio_quality=self._audio_quality.get(),
            video_format=self._video_format.get(),
            no_playlist=self._no_playlist.get(),
            progress_callback=self._on_progress,
            on_complete=self._on_complete,
        )

    def _on_progress(self, d: dict) -> None:
        status = d.get("status", "")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            pct = (downloaded / total * 100) if total else 0
            speed = d.get("_speed_str", "")
            eta = d.get("_eta_str", "")
            msg = f"Downloading…  {pct:.1f}%"
            if speed:
                msg += f"  {speed}"
            if eta:
                msg += f"  ETA {eta}"
            self.after(0, lambda p=pct, m=msg: self._update_progress(p, m))
        elif status == "finished":
            self.after(0, lambda: self._update_progress(100, "Processing…"))

    def _update_progress(self, pct: float, msg: str) -> None:
        self._progress_var.set(pct)
        self._status_var.set(msg)

    def _on_complete(self, filepath: Optional[str], error: Optional[Exception]) -> None:
        def _ui() -> None:
            self._download_btn.configure(state="normal")
            if error:
                self._status_var.set("Error – see details")
                messagebox.showerror(APP_NAME, str(error))
            else:
                self._progress_var.set(100)
                self._status_var.set(
                    f"Done!  Saved to: {filepath or self._output_dir.get()}"
                )

        self.after(0, _ui)
