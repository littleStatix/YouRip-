# core.py
# Core backend logic for YouTube ripping

import os
import sys
import time
import logging
import json
from pathlib import Path
from datetime import datetime
import yt_dlp
import shutil
import subprocess
from player_core import VideoPlayer

# ──────────────────────────────────────────────────────────────
# CONFIG & GLOBALS
# ──────────────────────────────────────────────────────────────
try:
    SCRIPT_DIR = Path(__file__).parent
except NameError:
    SCRIPT_DIR = Path.cwd()

LOG_FILE = SCRIPT_DIR / "yourip_log.txt"
QUEUE_FILE = SCRIPT_DIR / "yourip_queue.json"
SETTINGS_FILE = SCRIPT_DIR / "yourip_settings.json"
DEFAULT_DOWNLOAD_DIR = Path.home() / "Documents" / "YouRip Media"
CACHE_DIR = SCRIPT_DIR / "cache"
TEMP_DIR = CACHE_DIR / "temp"
YTDLP_CACHE_DIR = CACHE_DIR / "yt-dlp"

# Default settings
DEFAULT_SETTINGS = {
    'theme': 'dark',
    'color_scheme': 'dark-blue',
    'accent_color': 'cyan',
    'download_dir': str(DEFAULT_DOWNLOAD_DIR),
    'default_format': 'wav',
    'verbose_logging': True,
    'search_results_count': 10,
    'auto_play_enabled': True,
    'quality_preset': 'best',
}

queue = []
verbose_mode = True
app_settings = DEFAULT_SETTINGS.copy()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)-7s | %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("YouRip")

def log_verbose(msg: str):
    if verbose_mode:
        logger.debug(f"[VERBOSE] {msg}")

def ensure_default_dir():
    try:
        DEFAULT_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        YTDLP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(f"Default download dir ready: {DEFAULT_DOWNLOAD_DIR}")
    except Exception as e:
        logger.error(f"Cannot create default directory: {e}")


def clear_cache_and_history():
    """Clear temp/cache artifacts and truncate local app history files."""
    removed_files = 0
    freed_bytes = 0

    for folder in [TEMP_DIR, YTDLP_CACHE_DIR]:
        if folder.exists():
            for p in folder.rglob('*'):
                if p.is_file():
                    removed_files += 1
                    try:
                        freed_bytes += p.stat().st_size
                    except Exception:
                        pass
            shutil.rmtree(folder, ignore_errors=True)

    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    YTDLP_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    queue.clear()
    save_queue()

    try:
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            f.write('')
    except Exception as e:
        logger.error(f"Failed to clear log file: {e}")

    logger.info(f"Cache/history cleared | removed_files={removed_files} | freed_mb={freed_bytes / (1024 * 1024):.2f}")
    return {
        'removed_files': removed_files,
        'freed_mb': round(freed_bytes / (1024 * 1024), 2),
        'cache_dir': str(CACHE_DIR),
    }

def load_queue():
    global queue
    if QUEUE_FILE.exists():
        try:
            with open(QUEUE_FILE, 'r', encoding='utf-8') as f:
                loaded_queue = json.load(f)

            # Keep list identity stable so imported references in other modules stay valid.
            queue.clear()
            if isinstance(loaded_queue, list):
                for item in loaded_queue:
                    if isinstance(item, dict):
                        item.setdefault('selected', True)
                        queue.append(item)
            logger.info(f"Loaded {len(queue)} items from queue")
        except Exception as e:
            logger.error(f"Failed to load queue: {e}")
            queue.clear()

def save_queue():
    try:
        with open(QUEUE_FILE, 'w', encoding='utf-8') as f:
            json.dump(queue, f, default=str, indent=2)
        log_verbose("Queue saved")
    except Exception as e:
        logger.error(f"Failed to save queue: {e}")

def load_settings():
    global app_settings, verbose_mode
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                app_settings.update(loaded)
            logger.info("Settings loaded")
        except Exception as e:
            logger.error(f"Failed to load settings: {e}")
    verbose_mode = app_settings.get('verbose_logging', True)

def save_settings():
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(app_settings, f, indent=2)
        log_verbose("Settings saved")
    except Exception as e:
        logger.error(f"Failed to save settings: {e}")

# ──────────────────────────────────────────────────────────────
# BACKEND LOGIC
# ──────────────────────────────────────────────────────────────

def search_youtube(query: str, count: int = None):
    if count is None:
        count = app_settings.get('search_results_count', 10)
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'default_search': 'ytsearch',
        'format': 'bestaudio/best',
        'extract_flat': True,
        'noplaylist': True,
    }
    try:
        logger.info(f"Searching YouTube: {query}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch{count}:{query}", download=False)
            if 'entries' not in info or not info['entries']:
                return []
            results = []
            for entry in info['entries']:
                if not entry: continue
                dur = entry.get('duration', 0)
                duration_str = time.strftime('%H:%M:%S', time.gmtime(dur)) if dur >= 3600 else time.strftime('%M:%S', time.gmtime(dur))
                upload_date = entry.get('upload_date')
                publish_date = datetime.strptime(upload_date, '%Y%m%d').strftime('%Y-%m-%d') if upload_date else 'Unknown'
                video_id = entry.get('id', '')
                thumbnail = f'https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg' if video_id else ''
                results.append({
                    'url': entry.get('url') or entry.get('webpage_url'),
                    'title': entry.get('title', 'Unknown Title'),
                    'duration': duration_str or "N/A",
                    'uploader': entry.get('uploader') or entry.get('channel', 'Unknown'),
                    'views': f"{entry.get('view_count', 0):,}" if entry.get('view_count') else "N/A",
                    'publish_date': publish_date,
                    'thumbnail': thumbnail,
                    'video_id': video_id,
                })
            logger.info(f"Search returned {len(results)} items")
            return results
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return []

def get_stream_url(video_url: str):
    """Extract direct stream URL for a video"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'format': 'best[ext=mp4]/best',
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            if 'url' in info:
                return info['url']
            elif 'formats' in info and len(info['formats']) > 0:
                for fmt in info['formats']:
                    if fmt.get('url'):
                        return fmt['url']
            return None
    except Exception as e:
        logger.error(f"Failed to get stream URL: {e}")
        return None

def add_to_queue(indices: list[int], search_results: list[dict]):
    added = 0
    for idx in indices:
        if not (1 <= idx <= len(search_results)): continue
        item = search_results[idx - 1]
        if any(q['url'] == item['url'] for q in queue): continue
        queue.append({**item, 'selected': True})
        added += 1
    if added:
        save_queue()
        logger.info(f"Added {added} item(s)")

def remove_from_queue(indices: list[int]):
    indices = sorted(set(indices), reverse=True)
    removed = 0
    for idx in indices:
        if 1 <= idx <= len(queue):
            queue.pop(idx - 1)
            removed += 1
    if removed:
        save_queue()

def toggle_selection(indices: list[int]):
    for idx in indices:
        if 1 <= idx <= len(queue):
            queue[idx - 1]['selected'] = not queue[idx - 1].get('selected', True)
    save_queue()

def find_ffmpeg():
    path = shutil.which('ffmpeg')
    if not path:
        logger.error("FFmpeg not found in PATH")
    return path

def download_queue(format_choice: str, out_dir: str = None):
    download_queue_with_hook(format_choice, out_dir, progress_hook)

def download_queue_with_hook(format_choice: str, out_dir: str = None, progress_hook_fn=None):
    global queue
    out_dir = Path(out_dir or DEFAULT_DOWNLOAD_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    to_download = [item for item in queue if item.get('selected', False)]
    if not to_download:
        logger.warning("No selected items for download")
        return

    if not find_ffmpeg():
        logger.error("FFmpeg is required for downloads")
        raise RuntimeError("FFmpeg not found in PATH")

    hook_fn = progress_hook_fn or progress_hook
    ydl_opts = {
        'outtmpl': str(out_dir / '%(title)s.%(ext)s'),
        'paths': {'temp': str(TEMP_DIR), 'home': str(out_dir)},
        'cachedir': str(YTDLP_CACHE_DIR),
        'continuedl': True,
        'retries': 10,
        'fragment_retries': 10,
        'quiet': not verbose_mode,
        'no_warnings': True,
        'progress_hooks': [hook_fn],
        'postprocessors': [],
        'ffmpeg_location': find_ffmpeg(),
    }

    fmt = format_choice.lower()
    if fmt in ['mp3', 'wav', 'm4a', 'opus']:
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'].append({
            'key': 'FFmpegExtractAudio',
            'preferredcodec': fmt,
            'preferredquality': '0'
        })
    elif fmt == 'mp4':
        ydl_opts['format'] = 'bestvideo+bestaudio/best'
    else:
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'].append({
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '0'
        })

    for item in to_download:
        try:
            logger.info(f"Starting: {item['title']}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([item['url']])
        except Exception as e:
            logger.error(f"Failed {item['title']}: {e}")

    queue.clear()
    save_queue()
    logger.info("All downloads finished – queue cleared")

def progress_hook(d):
    if d['status'] == 'downloading':
        logger.info(f"Progress: {d.get('_percent_str', '??%')} | ETA: {d.get('_eta_str', '??')}")
    elif d['status'] == 'finished':
        logger.info("File finished – moving to next")