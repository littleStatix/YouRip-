"""Core download logic for YouRip using yt-dlp."""

import os
import threading
from typing import Callable, Optional

import yt_dlp

from config import (
    DEFAULT_DOWNLOAD_DIR,
    DEFAULT_AUDIO_FORMAT,
    DEFAULT_AUDIO_QUALITY,
    DEFAULT_VIDEO_FORMAT,
)


def _progress_hook(progress_callback: Optional[Callable[[dict], None]]):
    """Return a yt-dlp progress hook that forwards events to *progress_callback*."""

    def hook(d: dict) -> None:
        if progress_callback:
            progress_callback(d)

    return hook


def build_ydl_opts(
    output_dir: str,
    audio_only: bool = True,
    audio_format: str = DEFAULT_AUDIO_FORMAT,
    audio_quality: str = DEFAULT_AUDIO_QUALITY,
    video_format: str = DEFAULT_VIDEO_FORMAT,
    no_playlist: bool = False,
    progress_callback: Optional[Callable[[dict], None]] = None,
) -> dict:
    """Build yt-dlp options dictionary."""
    os.makedirs(output_dir, exist_ok=True)
    outtmpl = os.path.join(output_dir, "%(title)s.%(ext)s")

    opts: dict = {
        "outtmpl": outtmpl,
        "noplaylist": no_playlist,
        "quiet": True,
        "no_warnings": True,
    }

    if progress_callback:
        opts["progress_hooks"] = [_progress_hook(progress_callback)]

    if audio_only:
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": audio_format,
                "preferredquality": audio_quality,
            }
        ]
    else:
        opts["format"] = f"bestvideo[ext={video_format}]+bestaudio/best"
        opts["merge_output_format"] = video_format

    return opts


def get_info(url: str) -> dict:
    """Fetch metadata for *url* without downloading anything."""
    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
        info = ydl.extract_info(url, download=False)
    return info or {}


def download(
    url: str,
    output_dir: str = DEFAULT_DOWNLOAD_DIR,
    audio_only: bool = True,
    audio_format: str = DEFAULT_AUDIO_FORMAT,
    audio_quality: str = DEFAULT_AUDIO_QUALITY,
    video_format: str = DEFAULT_VIDEO_FORMAT,
    no_playlist: bool = False,
    progress_callback: Optional[Callable[[dict], None]] = None,
) -> str:
    """Download *url* and return the output file path.

    Raises ``yt_dlp.utils.DownloadError`` on failure.
    """
    opts = build_ydl_opts(
        output_dir=output_dir,
        audio_only=audio_only,
        audio_format=audio_format,
        audio_quality=audio_quality,
        video_format=video_format,
        no_playlist=no_playlist,
        progress_callback=progress_callback,
    )

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        if info is None:
            raise yt_dlp.utils.DownloadError(
                    f"No information returned for URL: {url}. "
                    "Please verify the URL is valid and accessible."
                )
        return ydl.prepare_filename(info)


def download_async(
    url: str,
    output_dir: str = DEFAULT_DOWNLOAD_DIR,
    audio_only: bool = True,
    audio_format: str = DEFAULT_AUDIO_FORMAT,
    audio_quality: str = DEFAULT_AUDIO_QUALITY,
    video_format: str = DEFAULT_VIDEO_FORMAT,
    no_playlist: bool = False,
    progress_callback: Optional[Callable[[dict], None]] = None,
    on_complete: Optional[Callable[[Optional[str], Optional[Exception]], None]] = None,
) -> threading.Thread:
    """Start *download* in a background thread and return the thread.

    *on_complete* is called with ``(filepath, None)`` on success or
    ``(None, exception)`` on failure.
    """

    def _run() -> None:
        try:
            path = download(
                url=url,
                output_dir=output_dir,
                audio_only=audio_only,
                audio_format=audio_format,
                audio_quality=audio_quality,
                video_format=video_format,
                no_playlist=no_playlist,
                progress_callback=progress_callback,
            )
            if on_complete:
                on_complete(path, None)
        except Exception as exc:  # noqa: BLE001
            if on_complete:
                on_complete(None, exc)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return thread
