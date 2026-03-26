"""Playback core for YouRip."""

import os
import sys
import subprocess
import logging

logger = logging.getLogger("YouRip")


class VideoPlayer:
    """Simple video player using VLC or fallback to system player."""

    def __init__(self):
        self.instance = None
        self.player = None
        self.current_url = None
        self.playing = False

        try:
            import vlc
            self.VLC_AVAILABLE = True
            try:
                self.instance = vlc.Instance()
                self.player = self.instance.media_player_new()
            except Exception as e:
                logger.error(f"Failed to initialize VLC: {e}")
                self.player = None
        except ImportError:
            self.VLC_AVAILABLE = False
            self.player = None
            print("VLC python bindings not installed. Streaming will be disabled.")
            print("Install with: pip install python-vlc")

    def play(self, url, embed_frame=None):
        """Play video from URL."""
        self.current_url = url

        if self.player and embed_frame and self.VLC_AVAILABLE:
            try:
                if sys.platform == "win32":
                    self.player.set_hwnd(embed_frame.winfo_id())
                elif sys.platform == "darwin":
                    self.player.set_nsobject(embed_frame.winfo_id())
                else:
                    self.player.set_xwindow(embed_frame.winfo_id())

                media = self.instance.media_new(url)
                self.player.set_media(media)
                self.player.play()
                self.playing = True
                return True
            except Exception as e:
                logger.error(f"VLC embedded playback failed: {e}")

        try:
            if sys.platform == 'win32':
                os.startfile(url)
            elif sys.platform == 'darwin':
                subprocess.run(['open', url])
            else:
                subprocess.run(['xdg-open', url])
            return True
        except Exception as e:
            logger.error(f"Failed to open system player: {e}")
            return False

    def stop(self):
        """Stop playback."""
        if self.player and self.playing:
            self.player.stop()
            self.playing = False

    def pause(self):
        """Pause/resume playback."""
        if self.player and self.playing:
            self.player.pause()

    def is_playing(self):
        """Check if player is playing."""
        if self.player:
            try:
                return self.player.is_playing()
            except Exception:
                return False
        return False

    def get_position(self):
        """Get current playback position in milliseconds."""
        if self.player:
            try:
                return self.player.get_time()
            except Exception as e:
                logger.debug(f"Could not get position: {e}")
        return 0

    def get_duration(self):
        """Get total duration in milliseconds."""
        if self.player and self.player.get_media():
            try:
                return self.player.get_media().get_duration()
            except Exception as e:
                logger.debug(f"Could not get duration: {e}")
        return 0

    def set_position(self, position_ms):
        """Seek to position in milliseconds."""
        if self.player and self.playing:
            try:
                self.player.set_time(int(position_ms))
            except Exception as e:
                logger.debug(f"Could not set position: {e}")
