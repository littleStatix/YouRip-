"""View and layout flow helpers for YouRip main UI."""

import customtkinter as ctk


def show_main_menu(app):
    """Show a lightweight main menu view."""
    if app.settings_open:
        app.close_settings()

    for widget in app.winfo_children():
        if widget != app.top_bar:
            try:
                widget.grid_remove()
            except Exception:
                pass

    if app.main_menu_frame and app.main_menu_frame.winfo_exists():
        app.main_menu_frame.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=20, pady=20)
        return

    accent = app.colors['ACCENT']
    bg_secondary = app.colors['BG_SECONDARY']
    text_primary = app.colors['TEXT_PRIMARY']
    text_secondary = app.colors['TEXT_SECONDARY']

    app.main_menu_frame = ctk.CTkFrame(app, fg_color=bg_secondary, border_color=accent, border_width=2, corner_radius=0)
    app.main_menu_frame.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=20, pady=20)
    app.main_menu_frame.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(app.main_menu_frame, text="Main Menu", text_color=accent,
                 font=ctk.CTkFont(size=28, weight="bold")).pack(anchor="w", padx=24, pady=(24, 8))
    ctk.CTkLabel(app.main_menu_frame, text="Main menu scaffold is active. We can expand this next.",
                 text_color=text_secondary, font=ctk.CTkFont(size=13)).pack(anchor="w", padx=24, pady=(0, 20))

    ctk.CTkButton(app.main_menu_frame, text="Open Media Suite", height=38,
                  fg_color=accent, hover_color=app.colors['ACCENT_LIGHT'], text_color="#000000",
                  corner_radius=0, command=app.open_media_suite).pack(anchor="w", padx=24, pady=6)
    ctk.CTkButton(app.main_menu_frame, text="Settings", height=34,
                  fg_color="#23262b", hover_color="#2f343b", text_color=text_primary,
                  corner_radius=0, command=app.open_settings_from_menu).pack(anchor="w", padx=24, pady=6)


def open_media_suite(app):
    """Return from main menu to the main application layout."""
    if app.main_menu_frame and app.main_menu_frame.winfo_exists():
        app.main_menu_frame.grid_remove()

    for widget in app.winfo_children():
        if widget != app.top_bar and widget != app.main_menu_frame:
            try:
                widget.grid()
            except Exception:
                pass


def open_settings_from_menu(app):
    """Open settings from main menu context."""
    if app.main_menu_frame and app.main_menu_frame.winfo_exists():
        app.main_menu_frame.grid_remove()
    app.show_settings()


def toggle_video_fullscreen(app):
    """Toggle proper window fullscreen plus center-focused panel mode."""
    if not app.center_panel:
        return

    if not app.video_fullscreen_mode:
        if getattr(app, 'top_bar', None):
            app.top_bar.grid_remove()
        if app.left_panel:
            app.left_panel.grid_remove()
        if app.right_panel:
            app.right_panel.grid_remove()

        app.center_panel.grid(row=0, column=0, columnspan=3, rowspan=2, sticky="nsew", padx=0, pady=0)

        for attr_name in ('search_bar', 'details_container', 'slider_frame', 'controls_frame', 'volume_row'):
            widget = getattr(app, attr_name, None)
            if widget is not None:
                try:
                    widget.pack_forget()
                except Exception:
                    try:
                        widget.grid_remove()
                    except Exception:
                        pass

        if getattr(app, 'stream_status', None):
            try:
                app.stream_status.pack_forget()
            except Exception:
                pass

        if getattr(app, 'display_frame', None):
            app.display_frame.configure(height=max(360, app.winfo_screenheight() - 80))
            app.display_frame.pack(fill="both", expand=True, pady=(0, 0))

        if hasattr(app, 'fullscreen_video_button') and app.fullscreen_video_button:
            app.fullscreen_video_button.configure(text="⛶ Exit")

        try:
            app.attributes('-fullscreen', True)
        except Exception:
            pass

        app.video_fullscreen_mode = True
    else:
        if getattr(app, 'top_bar', None):
            app.top_bar.grid(row=0, column=0, columnspan=3, sticky="ew")

        if app.left_panel:
            app.left_panel.grid(row=1, column=0, sticky="nsew", padx=12, pady=12)
        app.center_panel.grid(row=1, column=1, columnspan=1, sticky="nsew", padx=12, pady=12)
        if app.right_panel:
            app.right_panel.grid(row=1, column=2, sticky="nsew", padx=12, pady=12)

        if getattr(app, 'display_frame', None):
            app.display_frame.configure(height=220)
            app.display_frame.pack(fill="x", expand=False, pady=(0, 8))

        if getattr(app, 'slider_frame', None):
            app.slider_frame.pack(fill="x", pady=(8, 4))
        if getattr(app, 'controls_frame', None):
            app.controls_frame.pack(fill="x", pady=(6, 0))
        if getattr(app, 'volume_row', None):
            app.volume_row.pack(fill="x", pady=(4, 2))
        if getattr(app, 'stream_status', None):
            app.stream_status.pack(anchor="w", pady=(2, 4))
        if getattr(app, 'details_container', None):
            app.details_container.pack(fill="both", expand=True, pady=(0, 4))
        if getattr(app, 'search_bar', None):
            app.search_bar.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(10, 0))

        if hasattr(app, 'fullscreen_video_button') and app.fullscreen_video_button:
            app.fullscreen_video_button.configure(text="⛶ Full Video")

        app.video_fullscreen_mode = False


def update_speed_widgets(app):
    """Update download speed labels shown in the right panel."""
    if app.speed_now_label:
        app.speed_now_label.configure(text=f"Now: {app.current_speed_mbps:.2f} Mbps")
    if app.speed_peak_label:
        app.speed_peak_label.configure(text=f"Peak: {app.peak_speed_mbps:.2f} Mbps")
    if app.speed_avg_label:
        app.speed_avg_label.configure(text=f"Average: {app.avg_speed_mbps:.2f} Mbps")
