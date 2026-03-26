"""Configuration settings for YouRip."""

import os

APP_NAME = "YouRip"
APP_VERSION = "1.0.0"

DEFAULT_DOWNLOAD_DIR = os.path.join(os.path.expanduser("~"), "Music", "YouRip")

AUDIO_FORMATS = ["mp3", "m4a", "wav", "flac", "opus"]
VIDEO_FORMATS = ["mp4", "webm", "mkv"]

DEFAULT_AUDIO_FORMAT = "mp3"
DEFAULT_VIDEO_FORMAT = "mp4"

DEFAULT_AUDIO_QUALITY = "192"

WINDOW_WIDTH = 700
WINDOW_HEIGHT = 520
WINDOW_TITLE = f"{APP_NAME} – Music Downloader"
