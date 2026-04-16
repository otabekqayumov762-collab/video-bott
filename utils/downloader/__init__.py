import logging
from dataclasses import dataclass
from typing import Optional

from .ytdlp import (
    download_media as download_ytdlp,
    detect_platform,
    is_supported_url,
    probe_media,
    DownloadResult,
)

logger = logging.getLogger(__name__)


async def download_media(url: str) -> DownloadResult:
    """Platform-aware downloader with Python-library fallbacks.

    Strategy:
      • youtube    → pytubefix → yt-dlp
      • instagram  → instaloader → yt-dlp
      • anything else → yt-dlp
    """
    platform = detect_platform(url)

    if platform == "youtube":
        result = await _try_pytube(url, platform)
        if result:
            return result
        logger.info("pytubefix failed, falling back to yt-dlp")

    elif platform == "instagram":
        result = await _try_instaloader(url, platform)
        if result:
            return result
        logger.info("instaloader failed, falling back to yt-dlp")

    return await download_ytdlp(url)


async def _try_pytube(url: str, platform: str) -> Optional[DownloadResult]:
    try:
        from .pytube_yt import download_youtube_pytube
        info = await download_youtube_pytube(url)
        return DownloadResult(
            ok=True,
            file_path=info["file_path"],
            title=info["title"],
            duration=info["duration"],
            width=None,
            height=None,
            is_audio=False,
            platform=platform,
            filesize_mb=info["filesize_mb"],
        )
    except Exception as e:
        logger.warning(f"pytubefix failed for {url}: {e}")
        return None


async def _try_instaloader(url: str, platform: str) -> Optional[DownloadResult]:
    try:
        from .insta import download_instagram
        info = await download_instagram(url)
        return DownloadResult(
            ok=True,
            file_path=info["file_path"],
            title=info["title"],
            duration=info["duration"],
            width=None,
            height=None,
            is_audio=False,
            platform=platform,
            filesize_mb=info["filesize_mb"],
        )
    except Exception as e:
        logger.warning(f"instaloader failed for {url}: {e}")
        return None
