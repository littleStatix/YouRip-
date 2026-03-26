# main.py
# Main GUI application for YouRip

import os
import sys
import time
import json
import re
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
from io import BytesIO

import customtkinter as ctk
from PIL import Image
import requests
import shutil
import core as core_module
from ui_views import (
    show_main_menu as show_main_menu_view,
    open_media_suite as open_media_suite_view,
    open_settings_from_menu as open_settings_from_menu_view,
    toggle_video_fullscreen as toggle_video_fullscreen_view,
    update_speed_widgets as update_speed_widgets_view,
)

# Import from core module
from core import (
    queue, verbose_mode, app_settings, logger,
    search_youtube, get_stream_url, add_to_queue, remove_from_queue,
    download_queue_with_hook, progress_hook,
    clear_cache_and_history,
    load_settings, save_settings, load_queue, save_queue,
    ensure_default_dir, DEFAULT_DOWNLOAD_DIR, SCRIPT_DIR, CACHE_DIR,
    VideoPlayer
)

# ──────────────────────────────────────────────────────────────
# FRONTEND – GUI
# ──────────────────────────────────────────────────────────────

class YouRipApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Load settings first
        load_settings()
        
        # Apply theme and color scheme from settings
        ctk.set_appearance_mode(app_settings.get('theme', 'dark'))
        
        # Fix: Handle color theme correctly
        theme_name = app_settings.get('color_scheme', 'dark-blue')
        try:
            # For built-in themes, we can use the theme name directly
            # CustomTkinter will look in its internal themes directory
            ctk.set_default_color_theme(theme_name)
            logger.info(f"Set color theme to: {theme_name}")
        except Exception as e:
            logger.error(f"Failed to set color theme '{theme_name}': {e}")
            # Fall back to default
            try:
                ctk.set_default_color_theme('dark-blue')
                logger.info("Falling back to dark-blue theme")
            except:
                logger.error("Could not set any color theme")

        self.title("YouRip — Media Suite")
        self.geometry('1280x720')
        self.minsize(1100, 640)

        try:
            self.attributes('-alpha', 0.97)
        except Exception:
            pass

        # Start maximized for better default visibility on desktop.
        try:
            self.state('zoomed')
        except Exception:
            pass

        # Force true fullscreen shortly after startup for platforms where zoomed is not enough.
        self.after(120, lambda: self.attributes('-fullscreen', True))

        self.bind("<Escape>", lambda _e: self.toggle_video_fullscreen() if self.video_fullscreen_mode else None)

        ensure_default_dir()
        load_queue()
        self._sync_queue_reference()

        self.last_search_results = []
        self.current_index = 0
        self.download_dir = Path(app_settings.get('download_dir', DEFAULT_DOWNLOAD_DIR))
        self.downloading = False
        self.current_image = None
        self.video_player = VideoPlayer()
        self.streaming = False
        self.stream_url = None
        self.update_slider_timer = None
        self.settings_open = False
        self.settings_frame = None
        self.top_bar = None  # Will store the top bar reference
        self.main_menu_frame = None

        # Loading animation support
        self.loading_frames = []
        self.loading_label = None
        self.current_frame = 0
        self.is_searching = False

        # Download progress
        self.total_to_download = 0
        self.downloaded_count = 0
        self.current_file_progress = 0.0
        self.current_speed_mbps = 0.0
        self.peak_speed_mbps = 0.0
        self.avg_speed_mbps = 0.0
        self.speed_sample_count = 0
        self.speed_sample_total = 0.0

        # Color theme with accent customization
        accent_color_map = {
            'cyan': '#d03b3b',
            'blue': '#b73a3a',
            'green': '#c24141',
            'red': '#d03b3b',
            'purple': '#b23f54',
        }
        accent_color = accent_color_map.get(app_settings.get('accent_color', 'red'), '#d03b3b')
        
        self.colors = {
            'BG_PRIMARY':     "#0a0a0a",
            'BG_SECONDARY':   "#1f1f1f",
            'BG_TERTIARY':    "#2a2a2a",
            'ACCENT':         accent_color,
            'ACCENT_LIGHT':   self._lighten_color(accent_color),
            'SUCCESS':        "#00ff85",
            'TEXT_PRIMARY':   "#ffffff",
            'TEXT_SECONDARY': "#aaaaaa",
            'BORDER_COLOR':   "#333333",
        }

        self.download_paused = False
        self.queue_metric_bars = []
        self.queue_metric_labels = []
        self.duration_pct_label = None
        self.speed_now_label = None
        self.speed_peak_label = None
        self.speed_avg_label = None
        self.video_fullscreen_mode = False
        self.brand_logo_image = None
        self.slider_warmup_attempts = 0

        self.left_panel = None
        self.center_panel = None
        self.right_panel = None

        self.load_loading_animation()
        self.load_brand_logo()
        self.build_ui()
        self.refresh_queue()

    def _sync_queue_reference(self):
        """Ensure main app uses core's live queue object."""
        global queue
        if queue is not core_module.queue:
            queue = core_module.queue

    def _lighten_color(self, color):
        """Lighten a color for hover effects"""
        # Simple lightening - convert hex to RGB, lighten, convert back
        try:
            color = color.lstrip('#')
            rgb = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
            # Lighten by 20%
            lighter = tuple(min(255, int(c * 1.2)) for c in rgb)
            return f"#{lighter[0]:02x}{lighter[1]:02x}{lighter[2]:02x}"
        except:
            return color

    def load_loading_animation(self):
        try:
            gif_path = SCRIPT_DIR / "loading.gif"
            if gif_path.exists():
                img = Image.open(gif_path)
                try:
                    while True:
                        frame = img.copy()
                        frame = frame.resize((396, 396), Image.Resampling.LANCZOS)
                        self.loading_frames.append(ctk.CTkImage(frame, size=(396,396)))
                        img.seek(img.tell() + 1)
                except EOFError:
                    pass
            else:
                logger.info("No loading.gif found – using text fallback")
        except Exception as e:
            logger.warning(f"Could not load animation: {e}")

    def load_brand_logo(self):
        """Load a small brand logo image for the left panel."""
        candidate_paths = [
            SCRIPT_DIR / "logo.png",
            SCRIPT_DIR / "logo.jpg",
            SCRIPT_DIR / "logo.jpeg",
            SCRIPT_DIR / "yourip_logo.png",
            SCRIPT_DIR / "yourip_logo.jpg",
            SCRIPT_DIR / "yourip_logo.jpeg",
        ]

        for path in candidate_paths:
            if not path.exists():
                continue
            try:
                img = Image.open(path)
                if img.mode not in ("RGB", "RGBA"):
                    img = img.convert("RGB")
                img.thumbnail((120, 120), Image.Resampling.LANCZOS)
                self.brand_logo_image = ctk.CTkImage(img, size=(img.width, img.height))
                logger.info(f"Loaded brand logo from: {path.name}")
                return
            except Exception as e:
                logger.warning(f"Could not load brand logo '{path.name}': {e}")

    def build_ui(self):
        BG_PRIMARY    = self.colors['BG_PRIMARY']
        BG_SECONDARY  = self.colors['BG_SECONDARY']
        BG_TERTIARY   = self.colors['BG_TERTIARY']
        ACCENT        = self.colors['ACCENT']
        ACCENT_LIGHT  = self.colors['ACCENT_LIGHT']
        SUCCESS       = self.colors['SUCCESS']
        TEXT_PRIMARY  = self.colors['TEXT_PRIMARY']
        TEXT_SECONDARY= self.colors['TEXT_SECONDARY']
        BORDER_COLOR  = self.colors['BORDER_COLOR']

        self.configure(fg_color=BG_PRIMARY)

        # Top accent strip + title row matching the reference mockup
        self.top_bar = ctk.CTkFrame(self, height=58, fg_color="#111214", border_color=ACCENT, border_width=1, corner_radius=0)
        self.top_bar.grid(row=0, column=0, columnspan=3, sticky="ew")
        self.top_bar.grid_columnconfigure(0, weight=1)
        self.top_bar.grid_columnconfigure(1, weight=0)

        ctk.CTkFrame(self.top_bar, fg_color="#8f2222", height=8, corner_radius=0).grid(row=0, column=0, columnspan=2, sticky="ew")
        ctk.CTkLabel(self.top_bar, text="YouRip V1", font=ctk.CTkFont(size=30, weight="bold"), text_color="#ff2d2d")\
            .grid(row=1, column=0, padx=12, pady=(6, 2), sticky="w")
        ctk.CTkButton(self.top_bar, text="↩ Back", font=ctk.CTkFont(size=15, weight="bold"), width=110, height=30,
                      fg_color="#01070f", hover_color="#021a2f", border_color=ACCENT, border_width=2,
                  text_color="#ffdcdc", corner_radius=0, command=self.show_main_menu)\
            .grid(row=1, column=1, padx=14, pady=(6, 4), sticky="e")

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=0, minsize=240)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0, minsize=300)

        # LEFT – Controls
        self.left_panel = ctk.CTkFrame(self, fg_color="#191b1f", border_color="#2b2f35", border_width=1, corner_radius=0)
        self.left_panel.grid(row=1, column=0, sticky="nsew", padx=12, pady=12)
        left = self.left_panel

        # ═══ Header ═══
        ctk.CTkLabel(left, text="⚙ CONTROLS", font=ctk.CTkFont(size=14, weight="bold"), text_color=ACCENT)\
            .pack(pady=16, padx=18, fill="x", anchor="w")

        # ═══ Media Section ═══
        ctk.CTkLabel(left, text="Media", font=ctk.CTkFont(size=11, weight="bold"), text_color=TEXT_SECONDARY)\
            .pack(pady=(12, 6), padx=18, anchor="w")

        ctk.CTkButton(left, text="✚ Add to Queue", font=ctk.CTkFont(size=12, weight="bold"), height=34,
                      fg_color=ACCENT, hover_color=ACCENT_LIGHT, text_color="#000000",
                      corner_radius=0, command=self.add_current_media)\
            .pack(pady=4, padx=18, fill="x")

        ctk.CTkButton(left, text="⬒ Download Folder", font=ctk.CTkFont(size=12, weight="bold"), height=32,
                      fg_color="#23262b", hover_color="#2f343b", text_color=TEXT_PRIMARY,
                      corner_radius=0, command=self.choose_download_dir)\
            .pack(pady=4, padx=18, fill="x")

        ctk.CTkButton(left, text="🗑  Clear All", font=ctk.CTkFont(size=12, weight="bold"), height=32,
                      fg_color="#23262b", hover_color="#2f343b", text_color=TEXT_PRIMARY,
                      corner_radius=0, command=self.clear_queue)\
            .pack(pady=4, padx=18, fill="x")

        # Divider
        ctk.CTkFrame(left, fg_color=BORDER_COLOR, height=1).pack(fill="x", pady=12, padx=18)

        # ═══ Format Section ═══
        ctk.CTkLabel(left, text="Format", font=ctk.CTkFont(size=11, weight="bold"), text_color=TEXT_SECONDARY)\
            .pack(pady=(6, 8), padx=18, anchor="w")

        self.format_var = tk.StringVar(value=app_settings.get('default_format', 'wav'))
        ff = ctk.CTkFrame(left, fg_color="transparent")
        ff.pack(padx=18, fill="x")
        for v, t in [("mp4", "◉ MP4 Video"), ("mp3", "◉ MP3 Audio"), ("wav", "◉ WAV Audio")]:
            ctk.CTkRadioButton(ff, text=t, variable=self.format_var, value=v,
                               text_color=TEXT_PRIMARY, fg_color=ACCENT, font=ctk.CTkFont(size=11)).pack(anchor="w", pady=4)

        # Divider
        ctk.CTkFrame(left, fg_color=BORDER_COLOR, height=1).pack(fill="x", pady=12, padx=18)

        # ═══ Download Section ═══
        ctk.CTkLabel(left, text="Download", font=ctk.CTkFont(size=11, weight="bold"), text_color=TEXT_SECONDARY)\
            .pack(pady=(6, 8), padx=18, anchor="w")

        ctk.CTkButton(left, text="⬇ Start Download", font=ctk.CTkFont(size=12, weight="bold"), height=34,
                      fg_color=SUCCESS, hover_color="#00cc6b", text_color="#000000",
                      corner_radius=0, command=self.start_download)\
            .pack(pady=4, padx=18, fill="x")

        controls_row = ctk.CTkFrame(left, fg_color="transparent")
        controls_row.pack(fill="x", padx=18, pady=(4, 4))
        ctk.CTkButton(controls_row, text="Pause downloads Ⅱ", font=ctk.CTkFont(size=12, weight="bold"), height=34,
                      fg_color="#05050a", border_color=ACCENT, border_width=2, hover_color="#111622",
                      text_color=TEXT_PRIMARY, corner_radius=0, command=self.pause_downloads).pack(fill="x", pady=(0, 6))
        ctk.CTkButton(controls_row, text="Resume downloads ▶", font=ctk.CTkFont(size=12, weight="bold"), height=34,
                      fg_color="#05050a", border_color=ACCENT, border_width=2, hover_color="#111622",
                      text_color=TEXT_PRIMARY, corner_radius=0, command=self.resume_downloads).pack(fill="x")

        ctk.CTkButton(left, text="🧹 Clear Cache / History", font=ctk.CTkFont(size=11, weight="bold"), height=32,
              fg_color="#05050a", border_color=ACCENT, border_width=2, hover_color="#111622", text_color=TEXT_PRIMARY,
              corner_radius=0, command=self.clear_cache_history).pack(pady=(4, 2), padx=18, fill="x")

        logo_slot = ctk.CTkFrame(left, fg_color="#111214", border_color=ACCENT, border_width=1, corner_radius=0)
        logo_slot.pack(fill="x", padx=18, pady=(4, 10))
        logo_slot.configure(height=124)
        logo_slot.pack_propagate(False)
        if self.brand_logo_image:
            ctk.CTkLabel(logo_slot, image=self.brand_logo_image, text="").pack(expand=True)
        else:
            ctk.CTkLabel(logo_slot, text="YouRip", text_color=ACCENT, font=ctk.CTkFont(size=14, weight="bold")).pack(expand=True)

        # CENTER – Carousel + Search
        self.center_panel = ctk.CTkFrame(self, fg_color="transparent")
        self.center_panel.grid(row=1, column=1, sticky="nsew", padx=12, pady=12)
        center = self.center_panel
        center.grid_rowconfigure(0, weight=1)
        center.grid_rowconfigure(1, weight=0)
        center.grid_columnconfigure(0, weight=0, minsize=50)
        center.grid_columnconfigure(1, weight=1)
        center.grid_columnconfigure(2, weight=0, minsize=50)

        carousel = ctk.CTkFrame(center, fg_color="#1e1e21", border_color=ACCENT, border_width=2, corner_radius=4)
        carousel.grid(row=0, column=0, columnspan=3, sticky="nsew")

        top_bar = ctk.CTkFrame(carousel, fg_color="transparent", height=32)
        top_bar.pack(fill="x", padx=16, pady=(12, 0))
        self.download_indicator = ctk.CTkLabel(top_bar, text="", font=ctk.CTkFont(size=12, weight="bold"), text_color=SUCCESS)
        self.download_indicator.pack(side="left")
        self.preview_name = ctk.CTkLabel(top_bar, text="Song name over here", font=ctk.CTkFont(size=18), text_color="#a2a2a2")
        self.preview_name.pack(side="top", pady=(0, 2))

        # MAIN CONTENT AREA - Preserve original layout with side navigation buttons
        # Left navigation button
        ctk.CTkButton(carousel, text="◀", font=ctk.CTkFont(size=24, weight="bold"), width=36, height=100,
                      fg_color="transparent", hover_color=BG_TERTIARY, text_color=ACCENT_LIGHT,
                      corner_radius=0, command=self.prev_item).pack(side="left", padx=8, pady=20)

        # Center content area
        content = ctk.CTkFrame(carousel, fg_color="transparent")
        content.pack(side="left", fill="both", expand=True, padx=12, pady=20)
        self.content_panel = content

        # Thumbnail/Video area with buttons below
        thumb_f = ctk.CTkFrame(content, fg_color="transparent")
        thumb_f.pack(fill="x", expand=False, pady=(0, 4))
        self.thumb_frame = thumb_f

        # Thumbnail frame (top)
        self.display_frame = ctk.CTkFrame(thumb_f, fg_color="#010205", corner_radius=0)
        self.display_frame.pack(fill="x", expand=False, pady=(0, 8))
        self.display_frame.configure(height=220)
        self.display_frame.pack_propagate(False)

        self.thumb_label = ctk.CTkLabel(self.display_frame, text="Search to preview", fg_color=BG_PRIMARY,
                text_color="#c0c7cf", corner_radius=0, width=520, height=240)
        self.thumb_label.pack(fill="both", expand=True)

        # Position slider frame
        slider_frame = ctk.CTkFrame(thumb_f, fg_color="transparent")
        slider_frame.pack(fill="x", pady=(8, 4))
        self.slider_frame = slider_frame

        self.time_label = ctk.CTkLabel(slider_frame, text="0:00 / 0:00", font=ctk.CTkFont(size=10), text_color=TEXT_SECONDARY)
        self.time_label.pack(side="left", pady=(0, 4))

        self.duration_pct_label = ctk.CTkLabel(slider_frame, text="0%", font=ctk.CTkFont(size=10, weight="bold"), text_color=TEXT_PRIMARY)
        self.duration_pct_label.pack(side="right", pady=(0, 4))

        self.position_slider = ctk.CTkSlider(slider_frame, from_=0, to=100, number_of_steps=1000,
                                              fg_color="#333333", progress_color=ACCENT,
                                              button_color=ACCENT, button_hover_color=ACCENT_LIGHT,
                                              height=6, corner_radius=3, command=self.on_slider_moved)
        self.position_slider.pack(fill="x")
        self.position_slider.set(0)
        self.slider_drag_active = False
        
        # Bind mouse events for drag detection
        self.position_slider.bind("<Button-1>", self._on_slider_press)
        self.position_slider.bind("<B1-Motion>", self._on_slider_drag)
        self.position_slider.bind("<ButtonRelease-1>", self._on_slider_release)

        # Control buttons frame (bottom)
        buttons_frame = ctk.CTkFrame(thumb_f, fg_color="transparent")
        buttons_frame.pack(fill="x", pady=(6, 0))
        self.controls_frame = buttons_frame

        # Play button
        self.play_button = ctk.CTkButton(buttons_frame, text="▶ Play", font=ctk.CTkFont(size=12, weight="bold"),
                         height=32, fg_color="#05050a", hover_color="#1a1010", border_color=ACCENT,
                         border_width=2, text_color="#f3f3f3", corner_radius=0, command=self.play_current_video)
        self.play_button.pack(side="left", padx=(0, 4), fill="both", expand=True)

        # Pause button
        self.pause_button = ctk.CTkButton(buttons_frame, text="⏸ Pause", font=ctk.CTkFont(size=12, weight="bold"),
                          height=32, fg_color="#05050a", hover_color="#1a1010", border_color=ACCENT,
                          border_width=2, text_color=TEXT_PRIMARY, corner_radius=0, command=self.pause_video)
        self.pause_button.pack(side="left", padx=2, fill="both", expand=True)

        # Stop button
        self.stop_button = ctk.CTkButton(buttons_frame, text="⏹ Stop", font=ctk.CTkFont(size=12, weight="bold"),
                         height=32, fg_color="#05050a", hover_color="#1a1010", border_color=ACCENT,
                         border_width=2, text_color=TEXT_PRIMARY, corner_radius=0, command=self.stop_video)
        self.stop_button.pack(side="left", padx=(4, 0), fill="both", expand=True)

        self.fullscreen_video_button = ctk.CTkButton(buttons_frame, text="⛶ Full Video", font=ctk.CTkFont(size=12, weight="bold"),
                 height=32, width=84, fg_color="#05050a", hover_color="#1a1010", border_color=ACCENT,
                 border_width=2, text_color=TEXT_PRIMARY, corner_radius=0, command=self.toggle_video_fullscreen)
        self.fullscreen_video_button.pack(side="left", padx=(4, 0))

        volume_row = ctk.CTkFrame(thumb_f, fg_color="transparent")
        volume_row.pack(fill="x", pady=(4, 2))
        self.volume_row = volume_row
        ctk.CTkLabel(volume_row, text="🔊", font=ctk.CTkFont(size=13)).pack(side="left", padx=(0, 6))
        self.volume_slider = ctk.CTkSlider(volume_row, from_=0, to=100, number_of_steps=100,
                           fg_color="#333333", progress_color=ACCENT,
                           button_color=ACCENT, button_hover_color=ACCENT_LIGHT,
                           height=6, corner_radius=3, command=self.on_volume_changed)
        self.volume_slider.pack(side="left", fill="x", expand=True)
        self.volume_slider.set(80)
        self.volume_label = ctk.CTkLabel(volume_row, text="80%", font=ctk.CTkFont(size=10), text_color=TEXT_SECONDARY)
        self.volume_label.pack(side="left", padx=(8, 0))

        # Stream status label
        self.stream_status = ctk.CTkLabel(content, text="", font=ctk.CTkFont(size=11), text_color=SUCCESS)
        self.stream_status.pack(anchor="w", pady=(2, 4))

        ctk.CTkFrame(content, fg_color=ACCENT, height=2).pack(fill="x", pady=(10, 8))

        # Details section
        det = ctk.CTkFrame(content, fg_color="transparent")
        det.pack(fill="both", expand=True, pady=(0, 4))
        self.details_container = det

        self.preview_details = ctk.CTkTextbox(det, height=170, corner_radius=0,
                              fg_color="#101114", border_color=BORDER_COLOR, border_width=1,
                              text_color=TEXT_PRIMARY, font=ctk.CTkFont(size=12), wrap="word")
        self.preview_details.pack(fill="both", expand=True)
        self.preview_details.insert("1.0", "Details\nAlbum\nArtist\nYear\nDate")
        self.preview_details.configure(state="disabled")

        # Right navigation button
        ctk.CTkButton(carousel, text="▶", font=ctk.CTkFont(size=24, weight="bold"), width=36, height=100,
                      fg_color="transparent", hover_color=BG_TERTIARY, text_color=ACCENT_LIGHT,
                      corner_radius=0, command=self.next_item).pack(side="right", padx=8, pady=20)

        # RIGHT – Queue + Progress
        self.right_panel = ctk.CTkFrame(self, fg_color="#1f1f22", border_color="#2b2f35", border_width=1, corner_radius=0)
        self.right_panel.grid(row=1, column=2, sticky="nsew", padx=12, pady=12)
        self.right_panel.grid_rowconfigure(1, weight=1)
        self.right_panel.grid_rowconfigure(5, weight=1)
        right = self.right_panel

        # Queue section (top half)
        ctk.CTkLabel(right, text="◉ Download Queue", font=ctk.CTkFont(size=15, weight="bold"), text_color=SUCCESS)\
            .grid(row=0, column=0, pady=16, padx=16, sticky="w")

        self.queue_scroll = ctk.CTkScrollableFrame(right, fg_color="#050607", corner_radius=0)
        self.queue_scroll.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 8))

        # Queue count label
        self.queue_count = ctk.CTkLabel(right, text="Items: 0", font=ctk.CTkFont(size=11), text_color=TEXT_SECONDARY)
        self.queue_count.grid(row=2, column=0, pady=(8, 0), padx=16, sticky="w")

        # Download speed indicators
        mini_stats = ctk.CTkFrame(right, fg_color="transparent")
        mini_stats.grid(row=3, column=0, sticky="ew", padx=16, pady=(10, 4))
        for metric_text in ["Now", "Peak", "Average"]:
            row = ctk.CTkFrame(mini_stats, fg_color="transparent")
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text="⚡", text_color=ACCENT, font=ctk.CTkFont(size=14, weight="bold")).pack(side="left", padx=(0, 6))
            lbl = ctk.CTkLabel(row, text=f"{metric_text}: 0.00 Mbps", text_color=TEXT_PRIMARY, font=ctk.CTkFont(size=10, weight="bold"))
            lbl.pack(side="left")
            if metric_text == "Now":
                self.speed_now_label = lbl
            elif metric_text == "Peak":
                self.speed_peak_label = lbl
            else:
                self.speed_avg_label = lbl

        ctk.CTkLabel(right, text="Downloading progress", font=ctk.CTkFont(size=14), text_color=TEXT_PRIMARY)\
            .grid(row=4, column=0, pady=(8, 10), padx=16, sticky="w")

        det_frame = ctk.CTkFrame(right, fg_color="transparent", corner_radius=0)
        det_frame.grid(row=5, column=0, sticky="nsew", padx=12, pady=(0, 12))

        self.progress_label = ctk.CTkLabel(det_frame, text="Waiting...", font=ctk.CTkFont(size=12), text_color="#888888")
        self.progress_label.pack(anchor="w", pady=(12, 4), padx=12)

        self.progress_bar = ctk.CTkProgressBar(det_frame, mode="determinate", height=14, corner_radius=0,
                                               progress_color="#efefef", fg_color="#0a0d10")
        self.progress_bar.pack(fill="x", pady=(0, 12), padx=12)
        self.progress_bar.set(0)

        self.download_status = ctk.CTkLabel(det_frame, text="Ready", font=ctk.CTkFont(size=10), text_color=SUCCESS)
        self.download_status.pack(anchor="w", pady=(0, 12), padx=12)

        self._update_speed_widgets()
        self._update_queue_metrics()

        # Search bar (bottom)
        sb = ctk.CTkFrame(center, fg_color="transparent")
        sb.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        self.search_bar = sb

        self.search_entry = ctk.CTkEntry(sb, placeholder_text="Search YouTube... (Enter or click Search)",
                         font=ctk.CTkFont(size=12), height=52,
                         fg_color="#090a12", border_color="#1f3045", border_width=2, corner_radius=0)
        self.search_entry.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self.search_entry.bind("<Return>", lambda e: self.perform_search())

        ctk.CTkButton(sb, text="🔍 Search", width=120, height=52, font=ctk.CTkFont(size=13, weight="bold"),
                  fg_color=ACCENT, hover_color=ACCENT_LIGHT, text_color="#000000", corner_radius=0,
                      command=self.perform_search).pack(side="left")

    def toggle_settings(self):
        """Toggle settings panel on/off"""
        if self.settings_open:
            self.close_settings()
        else:
            self.show_settings()

    def show_main_menu(self):
        show_main_menu_view(self)

    def open_media_suite(self):
        open_media_suite_view(self)

    def open_settings_from_menu(self):
        open_settings_from_menu_view(self)

    def toggle_video_fullscreen(self):
        toggle_video_fullscreen_view(self)

    def _update_speed_widgets(self):
        update_speed_widgets_view(self)

    def show_settings(self):
        """Show settings panel"""
        if self.settings_open:
            return
            
        self.settings_open = True
        
        # Hide main UI widgets (except the top bar)
        for widget in self.winfo_children():
            if widget != self.top_bar:
                try:
                    widget.grid_remove()
                except:
                    pass
        
        BG_PRIMARY    = self.colors['BG_PRIMARY']
        BG_SECONDARY  = self.colors['BG_SECONDARY']
        BG_TERTIARY   = self.colors['BG_TERTIARY']
        ACCENT        = self.colors['ACCENT']
        TEXT_PRIMARY  = self.colors['TEXT_PRIMARY']
        TEXT_SECONDARY= self.colors['TEXT_SECONDARY']
        BORDER_COLOR  = self.colors['BORDER_COLOR']

        # Create settings frame
        self.settings_frame = ctk.CTkFrame(self, fg_color=BG_PRIMARY)
        self.settings_frame.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=0, pady=0)
        self.settings_frame.grid_rowconfigure(1, weight=1)
        self.settings_frame.grid_columnconfigure(0, weight=1)
        
        # Header
        header = ctk.CTkFrame(self.settings_frame, fg_color=BG_SECONDARY, border_color=BORDER_COLOR, border_width=1, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(header, text="⚙️ Settings", font=ctk.CTkFont(size=28, weight="bold"), text_color=ACCENT)\
            .grid(row=0, column=0, padx=24, pady=20, sticky="w")
        
        ctk.CTkButton(header, text="✕ Close", font=ctk.CTkFont(size=12, weight="bold"), height=40,
                      fg_color=BG_TERTIARY, hover_color="#3a3a3a", text_color=TEXT_PRIMARY,
                      corner_radius=2, command=self.close_settings)\
            .grid(row=0, column=1, padx=24, pady=20)
        
        # Settings content (scrollable)
        content = ctk.CTkScrollableFrame(self.settings_frame, fg_color=BG_PRIMARY)
        content.grid(row=1, column=0, sticky="nsew", padx=20, pady=20)
        content.grid_columnconfigure(0, weight=1)
        
        # ═══ Appearance Section ═══
        self._add_section_header(content, "🎨 Appearance", TEXT_SECONDARY)
        
        # Theme selection
        ctk.CTkLabel(content, text="Theme Mode", font=ctk.CTkFont(size=13, weight="bold"), text_color=TEXT_PRIMARY)\
            .pack(anchor="w", pady=(12, 6), padx=16)
        
        theme_frame = ctk.CTkFrame(content, fg_color="transparent")
        theme_frame.pack(fill="x", padx=16, pady=(0, 12))
        
        self.theme_var = tk.StringVar(value=app_settings.get('theme', 'dark'))
        for theme in ['dark', 'light', 'system']:
            ctk.CTkRadioButton(theme_frame, text=theme.capitalize(), variable=self.theme_var, value=theme,
                               text_color=TEXT_PRIMARY, fg_color=ACCENT, command=self.apply_theme_setting)\
                .pack(anchor="w", pady=4)
        
        # Color scheme selection
        ctk.CTkLabel(content, text="Color Scheme", font=ctk.CTkFont(size=13, weight="bold"), text_color=TEXT_PRIMARY)\
            .pack(anchor="w", pady=(12, 6), padx=16)
        
        color_frame = ctk.CTkFrame(content, fg_color="transparent")
        color_frame.pack(fill="x", padx=16, pady=(0, 12))
        
        self.color_var = tk.StringVar(value=app_settings.get('color_scheme', 'dark-blue'))
        # Valid CustomTkinter color themes
        valid_colors = [
            ('dark-blue', '🔵 Dark Blue'),
            ('dark-green', '🟢 Dark Green'),
            ('green', '🟢 Green'),
            ('blue', '🔵 Blue')
        ]
        for color_value, color_label in valid_colors:
            ctk.CTkRadioButton(color_frame, text=color_label, variable=self.color_var, value=color_value,
                               text_color=TEXT_PRIMARY, fg_color=ACCENT, command=self.apply_color_setting)\
                .pack(anchor="w", pady=4)
        
        # Accent color selection
        ctk.CTkLabel(content, text="Accent Color", font=ctk.CTkFont(size=13, weight="bold"), text_color=TEXT_PRIMARY)\
            .pack(anchor="w", pady=(12, 6), padx=16)
        
        accent_frame = ctk.CTkFrame(content, fg_color="transparent")
        accent_frame.pack(fill="x", padx=16, pady=(0, 12))
        
        self.accent_var = tk.StringVar(value=app_settings.get('accent_color', 'cyan'))
        accent_options = [
            ('cyan', '🌊 Cyan'),
            ('blue', '💙 Blue'),
            ('green', '💚 Green'),
            ('red', '❤️ Red'),
            ('purple', '💜 Purple'),
        ]
        
        # Create color preview frames
        color_map = {
            'cyan': '#00ccff',
            'blue': '#3b8ed0',
            'green': '#2fa572',
            'red': '#d03b3b',
            'purple': '#9b59b6',
        }
        
        for val, label in accent_options:
            color_row = ctk.CTkFrame(accent_frame, fg_color="transparent")
            color_row.pack(fill="x", pady=2)
            
            # Color preview box
            preview = ctk.CTkFrame(color_row, width=20, height=20, fg_color=color_map[val], corner_radius=3)
            preview.pack(side="left", padx=(0, 8))
            preview.pack_propagate(False)
            
            ctk.CTkRadioButton(color_row, text=label, variable=self.accent_var, value=val,
                               text_color=TEXT_PRIMARY, fg_color=color_map[val], 
                               command=self.apply_accent_color_setting).pack(side="left")
        
        # ═══ Download Section ═══
        self._add_section_header(content, "📥 Download Settings", TEXT_SECONDARY)
        
        # Default format
        ctk.CTkLabel(content, text="Default Download Format", font=ctk.CTkFont(size=13, weight="bold"), text_color=TEXT_PRIMARY)\
            .pack(anchor="w", pady=(12, 6), padx=16)
        
        format_frame = ctk.CTkFrame(content, fg_color="transparent")
        format_frame.pack(fill="x", padx=16, pady=(0, 12))
        
        self.default_format_var = tk.StringVar(value=app_settings.get('default_format', 'wav'))
        for fmt in [('mp4', '🎥 MP4 Video'), ('mp3', '🎵 MP3 Audio'), ('wav', '🎵 WAV Audio'), ('m4a', '🎵 M4A Audio')]:
            ctk.CTkRadioButton(format_frame, text=fmt[1], variable=self.default_format_var, value=fmt[0],
                               text_color=TEXT_PRIMARY, fg_color=ACCENT, command=self.apply_format_setting)\
                .pack(anchor="w", pady=4)
        
        # Default download directory
        ctk.CTkLabel(content, text="Default Download Directory", font=ctk.CTkFont(size=13, weight="bold"), text_color=TEXT_PRIMARY)\
            .pack(anchor="w", pady=(12, 6), padx=16)
        
        dir_frame = ctk.CTkFrame(content, fg_color=BG_TERTIARY, corner_radius=2)
        dir_frame.pack(fill="x", padx=16, pady=(0, 12))
        
        self.dir_label = ctk.CTkLabel(dir_frame, text=str(self.download_dir)[:60] + "...", 
                                      font=ctk.CTkFont(size=11), text_color=TEXT_SECONDARY)
        self.dir_label.pack(side="left", fill="both", expand=True, padx=12, pady=12)
        
        ctk.CTkButton(dir_frame, text="Browse", font=ctk.CTkFont(size=11, weight="bold"), width=100,
                      fg_color=ACCENT, hover_color=self._lighten_color(ACCENT), text_color="#000000",
                      corner_radius=2, command=self.set_download_dir)\
            .pack(side="right", padx=12, pady=12)
        
        # ═══ Playback Section ═══
        self._add_section_header(content, "▶️ Playback Settings", TEXT_SECONDARY)
        
        # Auto-play toggle
        self.autoplay_var = tk.BooleanVar(value=app_settings.get('auto_play_enabled', True))
        ctk.CTkCheckBox(content, text="Enable Auto-Play", variable=self.autoplay_var,
                        text_color=TEXT_PRIMARY, fg_color=ACCENT, checkmark_color="#000000",
                        command=self.apply_autoplay_setting)\
            .pack(anchor="w", padx=16, pady=6)
        
        # ═══ Logging Section ═══
        self._add_section_header(content, "📝 Logging Settings", TEXT_SECONDARY)
        
        # Verbose logging toggle
        self.verbose_var = tk.BooleanVar(value=app_settings.get('verbose_logging', True))
        ctk.CTkCheckBox(content, text="Verbose Logging", variable=self.verbose_var,
                        text_color=TEXT_PRIMARY, fg_color=ACCENT, checkmark_color="#000000",
                        command=self.apply_verbose_setting)\
            .pack(anchor="w", padx=16, pady=6)
        
        # Search results count
        ctk.CTkLabel(content, text="Search Results Count", font=ctk.CTkFont(size=13, weight="bold"), text_color=TEXT_PRIMARY)\
            .pack(anchor="w", pady=(12, 6), padx=16)
        
        count_frame = ctk.CTkFrame(content, fg_color="transparent")
        count_frame.pack(fill="x", padx=16, pady=(0, 20))
        
        self.search_count_var = tk.StringVar(value=str(app_settings.get('search_results_count', 10)))
        count_menu = ctk.CTkComboBox(count_frame, values=["5", "10", "15", "20", "25", "30"],
                                     variable=self.search_count_var, state="readonly",
                                     fg_color=BG_TERTIARY, border_color=BORDER_COLOR,
                                     button_color=ACCENT, text_color=TEXT_PRIMARY,
                                     command=self.apply_search_count_setting)
        count_menu.pack(anchor="w", padx=0)
        
        logger.info("Settings panel opened")

    def close_settings(self):
        """Close settings panel and show main UI"""
        self.settings_open = False
        
        if self.settings_frame:
            self.settings_frame.destroy()
            self.settings_frame = None
        
        # Show all main UI widgets again
        for widget in self.winfo_children():
            if widget == self.main_menu_frame:
                continue
            try:
                widget.grid()
            except:
                pass
        
        logger.info("Settings panel closed")

    def _add_section_header(self, parent, title, color):
        """Add a section header with divider"""
        ctk.CTkLabel(parent, text=title, font=ctk.CTkFont(size=14, weight="bold"), text_color=color)\
            .pack(anchor="w", pady=(20, 10), padx=16)
        ctk.CTkFrame(parent, fg_color="#333333", height=1).pack(fill="x", padx=16, pady=(0, 12))

    def apply_theme_setting(self):
        """Apply theme setting"""
        new_theme = self.theme_var.get()
        app_settings['theme'] = new_theme
        save_settings()
        ctk.set_appearance_mode(new_theme)
        logger.info(f"Theme changed to: {new_theme}")

    def apply_color_setting(self):
        """Apply color scheme setting"""
        new_color = self.color_var.get()
        app_settings['color_scheme'] = new_color
        save_settings()
        
        # Valid CustomTkinter themes
        valid_themes = ['dark-blue', 'dark-green', 'green', 'blue']
        
        if new_color in valid_themes:
            try:
                # The correct way to set built-in themes
                ctk.set_default_color_theme(new_color)
                logger.info(f"Color scheme changed to: {new_color}")
                messagebox.showinfo("Restart Required", 
                                   "Color scheme changes require an application restart to take full effect.")
            except Exception as e:
                logger.error(f"Failed to set color theme: {e}")
                messagebox.showerror("Error", f"Failed to set color theme: {e}")
        else:
            logger.warning(f"Invalid color theme: {new_color}")

    def apply_accent_color_setting(self):
        """Apply accent color setting"""
        new_accent = self.accent_var.get()
        app_settings['accent_color'] = new_accent
        save_settings()
        
        # Define accent color mappings
        accent_colors = {
            'cyan': '#00ccff',
            'blue': '#3b8ed0',
            'green': '#2fa572',
            'red': '#d03b3b',
            'purple': '#9b59b6',
        }
        
        new_color = accent_colors.get(new_accent, '#00ccff')
        self.colors['ACCENT'] = new_color
        self.colors['ACCENT_LIGHT'] = self._lighten_color(new_color)
        
        # Update UI elements that use accent color
        messagebox.showinfo("Accent Updated", 
                           f"Accent color changed to {new_accent}. Some elements may require restart.")
        logger.info(f"Accent color changed to: {new_accent}")

    def apply_format_setting(self):
        """Apply default format setting"""
        new_format = self.default_format_var.get()
        app_settings['default_format'] = new_format
        self.format_var.set(new_format)
        save_settings()
        logger.info(f"Default format changed to: {new_format}")

    def set_download_dir(self):
        """Set custom download directory"""
        new_dir = filedialog.askdirectory(initialdir=str(self.download_dir))
        if new_dir:
            self.download_dir = Path(new_dir)
            app_settings['download_dir'] = str(self.download_dir)
            save_settings()
            if hasattr(self, 'dir_label') and self.dir_label:
                self.dir_label.configure(text=str(self.download_dir)[:60] + "...")
            logger.info(f"Download directory changed to: {self.download_dir}")

    def apply_autoplay_setting(self):
        """Apply auto-play setting"""
        new_value = self.autoplay_var.get()
        app_settings['auto_play_enabled'] = new_value
        save_settings()
        logger.info(f"Auto-play enabled: {new_value}")

    def apply_verbose_setting(self):
        """Apply verbose logging setting"""
        global verbose_mode
        new_value = self.verbose_var.get()
        app_settings['verbose_logging'] = new_value
        verbose_mode = new_value
        save_settings()
        logger.info(f"Verbose logging enabled: {new_value}")

    def apply_search_count_setting(self, choice=None):
        """Apply search results count setting"""
        try:
            new_count = int(self.search_count_var.get())
            if 1 <= new_count <= 50:  # Sanity check
                app_settings['search_results_count'] = new_count
                save_settings()
                logger.info(f"Search results count changed to: {new_count}")
        except (ValueError, TypeError):
            pass

    def show_loading(self):
        self.is_searching = True
        self.thumb_label.configure(image=None, text="")
        if self.loading_frames:
            self.loading_label = ctk.CTkLabel(self.thumb_label, image=self.loading_frames[0], text="")
            self.loading_label.place(relx=0.5, rely=0.5, anchor="center")
            self.animate_loading()
        else:
            self.thumb_label.configure(text="Searching...", text_color="#666666")

    def animate_loading(self):
        if not self.is_searching: return
        if self.loading_frames and self.loading_label:
            self.current_frame = (self.current_frame + 1) % len(self.loading_frames)
            self.loading_label.configure(image=self.loading_frames[self.current_frame])
        self.after(80, self.animate_loading)

    def hide_loading(self):
        self.is_searching = False
        if self.loading_label:
            self.loading_label.destroy()
            self.loading_label = None
        self.thumb_label.configure(text="")

    def perform_search(self):
        q = self.search_entry.get().strip()
        if not q: return

        # Stop any playing video
        self.stop_video()

        self.show_loading()
        self.last_search_results = []
        self.current_index = 0

        def worker():
            try:
                res = search_youtube(q)
                self.after(0, lambda: self._search_done(res))
            except Exception as e:
                logger.error(f"Search thread error: {e}")
                self.after(0, lambda: self._search_done([]))

        threading.Thread(target=worker, daemon=True).start()

    def _search_done(self, results):
        self.hide_loading()
        self.last_search_results = results
        if results:
            self.display_current()
        else:
            self.thumb_label.configure(text="No results found", image=None)

    def display_current(self):
        if not self.last_search_results:
            self.thumb_label.configure(text="No results", image=None)
            return
        item = self.last_search_results[self.current_index]
        self.update_preview(item)

    def get_thumbnail_image(self, url: str, size=(520, 292)):
        if not url:
            p = Image.new("RGB", size, "#1a1a1a")
            return ctk.CTkImage(p, size=size)
        try:
            r = requests.get(url, timeout=8, headers={'User-Agent': 'Mozilla/5.0'})
            if r.status_code != 200: 
                raise Exception("Failed to retrieve image")
            img = Image.open(BytesIO(r.content))
            if img.mode != 'RGB': 
                img = img.convert('RGB')
            img = img.resize(size, Image.Resampling.LANCZOS)
            return ctk.CTkImage(img, size=size)
        except Exception as e:
            logger.debug(f"Could not load thumbnail: {e}")
            p = Image.new("RGB", size, "#1a1a1a")
            return ctk.CTkImage(p, size=size)

    def update_preview(self, item):
        title = item['title'][:85] + "…" if len(item['title']) > 85 else item['title']
        self.preview_name.configure(text=title)

        # Clear any video playback
        self.stop_video()
        
        self.current_image = self.get_thumbnail_image(item.get('thumbnail', ''))
        self.thumb_label.configure(image=self.current_image, text="")

        uploader = item['uploader'][:40] + "…" if len(item['uploader']) > 40 else item['uploader']
        publish_date = item.get('publish_date', '')
        year = str(publish_date)[:4] if publish_date else "-"
        duration = item.get('duration', '-')
        views = item.get('views', '-')

        details_text = (
            "Details\n"
            f"Album: {item.get('title', 'Unknown')}\n"
            f"Artist: {uploader}\n"
            f"Year: {year}\n"
            f"Date: {publish_date or '-'}\n"
            f"Duration: {duration}\n"
            f"Views: {views}"
        )
        
        self.preview_details.configure(state="normal")
        self.preview_details.delete("1.0", "end")
        self.preview_details.insert("1.0", details_text)
        self.preview_details.configure(state="disabled")
        
        # Reset stream status
        self.stream_url = None
        self.stream_status.configure(text="")

    def play_current_video(self):
        """Play the current video"""
        if not self.last_search_results:
            messagebox.showinfo("No Video", "Please search for videos first")
            return
        
        if self.streaming:
            self.stop_video()
            return
        
        item = self.last_search_results[self.current_index]
        self.stream_status.configure(text="🔄 Loading stream...", text_color="#ffaa00")
        
        def get_stream():
            try:
                url = get_stream_url(item['url'])
                self.after(0, lambda: self._stream_ready(url, item))
            except Exception as e:
                logger.error(f"Stream error: {e}")
                self.after(0, lambda: self.stream_status.configure(
                    text="❌ Stream failed", text_color="#ff6b6b"))
        
        threading.Thread(target=get_stream, daemon=True).start()
    
    def _stream_ready(self, stream_url, item):
        """Called when stream URL is ready"""
        if not stream_url:
            self.stream_status.configure(text="❌ Cannot get stream URL", text_color="#ff6b6b")
            return
        
        self.stream_url = stream_url
        self.stream_status.configure(text="▶️ Playing...", text_color="#00ff85")
        
        # Try to play embedded
        success = self.video_player.play(stream_url, self.display_frame)
        
        if success and getattr(self.video_player, 'player', None):
            self.streaming = True
            self.thumb_label.pack_forget()  # Hide thumbnail
            self.stream_status.configure(text="▶️ Playing (embedded)", text_color="#00ff85")
            self.on_volume_changed(self.volume_slider.get() if hasattr(self, 'volume_slider') else 80)
            self.slider_warmup_attempts = 0
            self._update_slider()  # Start updating slider
        else:
            # Fallback to system player
            self.stream_status.configure(text="▶️ Playing (external)", text_color="#00ff85")
            self.streaming = True
    
    def pause_video(self):
        """Pause/unpause video"""
        if self.video_player:
            self.video_player.pause()
            if self.video_player.is_playing():
                self.stream_status.configure(text="▶️ Playing")
                self._update_slider()
            else:
                self.stream_status.configure(text="⏸️ Paused")
                self._stop_slider_update()
    
    def stop_video(self):
        """Stop video playback"""
        if self.video_player:
            self.video_player.stop()
        
        self.streaming = False
        self.stream_status.configure(text="")
        
        # Show thumbnail again
        if hasattr(self, 'current_image') and self.current_image:
            self.thumb_label.pack(fill="both", expand=True)
            self.thumb_label.configure(image=self.current_image)
        
        # Reset slider
        self.position_slider.set(0)
        self.time_label.configure(text="0:00 / 0:00")
        if self.duration_pct_label:
            self.duration_pct_label.configure(text="0%")
        self.slider_warmup_attempts = 0
        self._stop_slider_update()

    def _ms_to_time(self, ms):
        """Convert milliseconds to MM:SS or HH:MM:SS format"""
        if ms <= 0:
            return "0:00"
        s = ms / 1000
        h = int(s // 3600)
        m = int((s % 3600) // 60)
        sec = int(s % 60)
        if h > 0:
            return f"{h}:{m:02d}:{sec:02d}"
        return f"{m}:{sec:02d}"
    
    def on_slider_moved(self, value):
        """Handle slider movement"""
        self.slider_drag_active = True
        duration = self.video_player.get_duration()
        if duration > 0:
            position_ms = (value / 100.0) * duration
            self.video_player.set_position(position_ms)
            self.time_label.configure(text=f"{self._ms_to_time(position_ms)} / {self._ms_to_time(duration)}")
            if self.duration_pct_label:
                self.duration_pct_label.configure(text=f"{int(value)}%")

    def on_volume_changed(self, value):
        """Set playback volume for embedded VLC playback when available."""
        vol = max(0, min(100, int(float(value))))
        if hasattr(self, 'volume_label') and self.volume_label:
            self.volume_label.configure(text=f"{vol}%")

        if getattr(self.video_player, 'player', None):
            try:
                self.video_player.player.audio_set_volume(vol)
            except Exception as e:
                logger.debug(f"Could not set volume: {e}")
    
    def _update_slider(self):
        """Update slider position during playback"""
        if not self.streaming:
            self._stop_slider_update()
            return

        if not self.video_player.is_playing():
            # VLC can take a moment to report playing state; keep polling briefly.
            if self.slider_warmup_attempts < 20:
                self.slider_warmup_attempts += 1
                self.update_slider_timer = self.after(250, self._update_slider)
                return
            self._stop_slider_update()
            return

        self.slider_warmup_attempts = 0
        
        position = self.video_player.get_position()
        duration = self.video_player.get_duration()
        
        if duration > 0:
            slider_value = (position / duration) * 100
            if not self.slider_drag_active:
                self.position_slider.set(slider_value)
            self.time_label.configure(text=f"{self._ms_to_time(position)} / {self._ms_to_time(duration)}")
            if self.duration_pct_label:
                self.duration_pct_label.configure(text=f"{int(max(0, min(100, slider_value)))}%")
        
        self.update_slider_timer = self.after(500, self._update_slider)

    def clear_cache_history(self):
        """Clear app cache/temp data and local history artifacts."""
        if not messagebox.askyesno("Clear Cache / History", "Clear cache/temp files, queue history, and local logs?"):
            return

        summary = clear_cache_and_history()
        self.last_search_results = []
        self.current_index = 0
        self.refresh_queue()

        messagebox.showinfo(
            "Cache Cleared",
            f"Removed files: {summary['removed_files']}\nFreed: {summary['freed_mb']} MB\nCache: {summary['cache_dir']}"
        )
        self.stream_status.configure(text="Cache/history cleared", text_color=self.colors['SUCCESS'])
    
    def _stop_slider_update(self):
        """Stop the slider update timer"""
        if self.update_slider_timer:
            self.after_cancel(self.update_slider_timer)
            self.update_slider_timer = None

    def _on_slider_press(self, event):
        """Handle slider press"""
        self.slider_drag_active = True
    
    def _on_slider_drag(self, event):
        """Handle slider drag"""
        pass  # Slider command callback handles the actual seeking
    
    def _on_slider_release(self, event):
        """Handle slider release"""
        self.slider_drag_active = False

    def prev_item(self):
        if self.last_search_results:
            self.stop_video()
            self.current_index = (self.current_index - 1) % len(self.last_search_results)
            self.display_current()

    def next_item(self):
        if self.last_search_results:
            self.stop_video()
            self.current_index = (self.current_index + 1) % len(self.last_search_results)
            self.display_current()

    def add_current_media(self):
        self._sync_queue_reference()
        if not self.last_search_results:
            messagebox.showinfo("No media", "Search first")
            return
        item = self.last_search_results[self.current_index]
        if any(q['url'] == item['url'] for q in queue):
            messagebox.showinfo("Duplicate", "Already in queue")
            return
        queue.append({**item, 'selected': True})
        save_queue()
        self.refresh_queue()

    def refresh_queue(self):
        self._sync_queue_reference()
        BG_TERTIARY = self.colors['BG_TERTIARY']
        for w in self.queue_scroll.winfo_children():
            w.destroy()
        if not queue:
            ctk.CTkLabel(self.queue_scroll, text="Queue empty", text_color="#555555", font=ctk.CTkFont(size=13))\
                .pack(pady=80)
            self.queue_count.configure(text="Items: 0")
            self._update_queue_metrics()
            return
        for i, item in enumerate(queue, 1):
            row = ctk.CTkFrame(self.queue_scroll, fg_color=BG_TERTIARY, border_color="#444444", border_width=1, corner_radius=2)
            row.pack(fill="x", padx=6, pady=6)

            is_selected = item.get('selected', True)
            var = tk.BooleanVar(value=is_selected)
            ctk.CTkCheckBox(row, text="", variable=var, width=20,
                            command=lambda idx=i, v=var: self.toggle_item_selection(idx, v))\
                .pack(side="left", padx=10, pady=12)

            txt = item['title'][:38] + "…" if len(item['title']) > 38 else item['title']
            lbl = ctk.CTkLabel(row, text=txt, font=ctk.CTkFont(size=12, weight="bold"), anchor="w")
            lbl.pack(side="left", fill="x", expand=True, padx=8, pady=12)
            lbl.bind("<Button-1>", lambda e, it=item: self.update_preview(it))

            ctk.CTkButton(row, text="❌", width=28, height=28, font=ctk.CTkFont(size=12),
                          fg_color="#ff3b30", hover_color="#ff5c52", corner_radius=1,
                          command=lambda idx=i: self.remove_from_queue_gui(idx))\
                .pack(side="right", padx=10, pady=12)
        
        # Update queue count
        self.queue_count.configure(text=f"Items: {len(queue)}")
        self._update_queue_metrics()

    def _update_queue_metrics(self):
        """Update right-panel metric bars based on queue and download progress."""
        self._update_speed_widgets()

    def toggle_item_selection(self, idx, var=None):
        if 1 <= idx <= len(queue):
            new_state = var.get() if var else not queue[idx-1].get('selected', True)
            queue[idx-1]['selected'] = new_state
            save_queue()
            self._update_queue_metrics()

    def remove_from_queue_gui(self, idx):
        remove_from_queue([idx])
        self.refresh_queue()

    def clear_queue(self):
        if queue and messagebox.askyesno("Clear", "Remove all items?"):
            queue.clear()
            save_queue()
            self.refresh_queue()

    def choose_download_dir(self):
        d = filedialog.askdirectory(initialdir=str(self.download_dir))
        if d:
            self.download_dir = Path(d)

    def pause_downloads(self):
        """Pause active downloads between hook callbacks."""
        if not self.downloading:
            messagebox.showinfo("Pause Downloads", "No active downloads to pause.")
            return
        self.download_paused = True
        self.download_status.configure(text="Paused", text_color="#ffaa00")
        self.progress_label.configure(text="Download paused")

    def resume_downloads(self):
        """Resume paused downloads."""
        if self.downloading:
            self.download_paused = False
            self.download_status.configure(text="Downloading", text_color=self.colors['SUCCESS'])
            return
        if not queue:
            messagebox.showinfo("Resume Downloads", "Queue is empty.")
            return
        self.start_download()

    def start_download(self):
        self._sync_queue_reference()
        selected = [it for it in queue if it.get('selected', False)]
        if not selected:
            if queue:
                for it in queue:
                    it['selected'] = True
                save_queue()
                self.refresh_queue()
                selected = [it for it in queue if it.get('selected', False)]
                messagebox.showinfo("Selection Updated", "No items were selected, so all queue items were selected automatically.")
            else:
                messagebox.showinfo("Nothing selected", "Please select items")
                return
        if self.downloading:
            return

        self.total_to_download = len(selected)
        self.downloaded_count = 0
        self.current_file_progress = 0.0
        self.current_speed_mbps = 0.0
        self.peak_speed_mbps = 0.0
        self.avg_speed_mbps = 0.0
        self.speed_sample_count = 0
        self.speed_sample_total = 0.0
        self.download_paused = False
        self.progress_bar.set(0)
        self.progress_label.configure(text=f"0 / {self.total_to_download} – Starting...", text_color=self.colors['SUCCESS'])
        self.download_status.configure(text="Downloading", text_color=self.colors['SUCCESS'])
        self._update_queue_metrics()

        self.downloading = True
        fmt = self.format_var.get()
        self.download_indicator.configure(text="⬇️ Downloading...")
        threading.Thread(target=self._download_worker, args=(fmt,), daemon=True).start()

    def _download_worker(self, fmt):
        def wrapped_hook(d):
            while self.download_paused and self.downloading:
                time.sleep(0.2)

            progress_hook(d)
            if d.get('status') == 'downloading':
                downloaded_bytes = d.get('downloaded_bytes', 0) or 0
                total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate') or 0

                file_progress = (downloaded_bytes / total_bytes) if total_bytes else 0.0
                if not total_bytes:
                    percent_str = str(d.get('_percent_str', '')).strip()
                    clean_percent = re.sub(r'\x1b\[[0-9;]*m', '', percent_str)
                    match = re.search(r'(\d+(?:\.\d+)?)\s*%', clean_percent)
                    if match:
                        file_progress = float(match.group(1)) / 100.0

                file_progress = max(0.0, min(1.0, file_progress))
                self.current_file_progress = file_progress

                overall_progress = ((self.downloaded_count + file_progress) / self.total_to_download) if self.total_to_download else 0
                overall_progress = max(0.0, min(1.0, overall_progress))

                speed = d.get('speed')
                eta = d.get('eta')
                speed_text = f"{speed / 1024 / 1024:.2f} MB/s" if speed else "--"
                eta_text = f"{int(eta)}s" if isinstance(eta, (int, float)) else "--"

                if speed:
                    speed_mbps = (float(speed) * 8.0) / 1_000_000.0
                    self.current_speed_mbps = speed_mbps
                    if speed_mbps > self.peak_speed_mbps:
                        self.peak_speed_mbps = speed_mbps
                    self.speed_sample_count += 1
                    self.speed_sample_total += speed_mbps
                    self.avg_speed_mbps = self.speed_sample_total / self.speed_sample_count

                self.after(0, lambda p=overall_progress: self.progress_bar.set(p))
                self.after(0, lambda fp=file_progress, op=overall_progress, sp=speed_text, et=eta_text: self.progress_label.configure(
                    text=f"File {int(fp*100)}% | Overall {int(op*100)}% | Speed {sp} | ETA {et}"))
                self.after(0, self._update_queue_metrics)

            if d['status'] == 'finished':
                self.downloaded_count += 1
                self.current_file_progress = 0.0
                pct = self.downloaded_count / self.total_to_download if self.total_to_download else 0
                self.after(0, lambda p=pct: self.progress_bar.set(p))
                self.after(0, lambda: self.progress_label.configure(
                    text=f"{self.downloaded_count} / {self.total_to_download} – {int(pct*100)}%"))
                self.after(0, self._update_queue_metrics)

        try:
            download_queue_with_hook(fmt, str(self.download_dir), wrapped_hook)
        except Exception as e:
            logger.error(f"Download crashed: {e}")
            self.after(0, lambda: messagebox.showerror("Error", str(e)))
        finally:
            self.after(0, self._download_finished)

    def _download_finished(self):
        self.downloading = False
        self.download_paused = False
        self.current_file_progress = 0.0
        self.current_speed_mbps = 0.0
        self.download_indicator.configure(text="✅ Complete")
        self.progress_bar.set(1)
        self.progress_label.configure(text=f"{self.downloaded_count} / {self.total_to_download} – Done")
        self.download_status.configure(text="Ready", text_color=self.colors['SUCCESS'])
        self._update_queue_metrics()
        self.after(5000, lambda: (self.progress_label.configure(text="Waiting..."), self.progress_bar.set(0)))
        self.refresh_queue()

# ──────────────────────────────────────────────────────────────
# LAUNCH
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        import customtkinter
    except ImportError:
        print("Missing dependency: pip install customtkinter")
        sys.exit(1)
    
    try:
        import yt_dlp
    except ImportError:
        print("Missing dependency: pip install yt-dlp")
        sys.exit(1)
    
    if not shutil.which('ffmpeg'):
        print("FFmpeg is missing – install from https://ffmpeg.org")
        print("Downloads will not work without FFmpeg, but streaming may still work.")
    
    # Check VLC availability (will be printed by VideoPlayer class if needed)

    try:
        app = YouRipApp()
        app.mainloop()
    except Exception as e:
        print(f"Failed to launch application: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")