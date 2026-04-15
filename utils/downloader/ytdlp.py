import asyncio
import logging
import os
import re
import uuid
from dataclasses import dataclass
from typing import Optional

from yt_dlp import YoutubeDL

from data.config import DOWNLOAD_DIR, MAX_FILE_SIZE_MB

logger = logging.getLogger(__name__)

URL_REGEX = re.compile(
    r"https?://[^\s]+",
    re.IGNORECASE,
)

PLATFORM_PATTERNS = {
    "youtube": re.compile(r"(youtube\.com|youtu\.be)", re.I),
    "instagram": re.compile(r"instagram\.com", re.I),
    "tiktok": re.compile(r"tiktok\.com", re.I),
    "facebook": re.compile(r"(facebook\.com|fb\.watch)", re.I),
    "twitter": re.compile(r"(twitter\.com|x\.com)", re.I),
}


@dataclass
class DownloadResult:
    ok: bool
    file_path: Optional[str] = None
    title: Optional[str] = None
    duration: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    is_audio: bool = False
    error: Optional[str] = None
    platform: Optional[str] = None


def detect_platform(url: str) -> str:
    for name, pattern in PLATFORM_PATTERNS.items():
        if pattern.search(url):
            return name
    return "other"


def is_supported_url(text: str) -> Optional[str]:
    if not text:
        return None
    match = URL_REGEX.search(text)
    return match.group(0) if match else None


def _ydl_opts(out_template: str) -> dict:
    return {
        "outtmpl": out_template,
        "format": (
            f"bestvideo[filesize<{MAX_FILE_SIZE_MB}M]+bestaudio/"
            f"best[filesize<{MAX_FILE_SIZE_MB}M]/"
            f"best"
        ),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
        "concurrent_fragment_downloads": 4,
        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 30,
        "geo_bypass": True,
        "ignoreerrors": False,
    }


def _blocking_download(url: str, out_template: str) -> DownloadResult:
    platform = detect_platform(url)
    try:
        with YoutubeDL(_ydl_opts(out_template)) as ydl:
            info = ydl.extract_info(url, download=True)

        if info is None:
            return DownloadResult(ok=False, error="Ma'lumot olinmadi.", platform=platform)

        if "entries" in info and info["entries"]:
            info = info["entries"][0]

        file_path = None
        try:
            file_path = ydl.prepare_filename(info)
            if not os.path.exists(file_path):
                base, _ = os.path.splitext(file_path)
                for ext in (".mp4", ".mkv", ".webm", ".mov", ".m4a", ".mp3"):
                    candidate = base + ext
                    if os.path.exists(candidate):
                        file_path = candidate
                        break
        except Exception as e:
            logger.warning(f"prepare_filename failed: {e}")

        if not file_path or not os.path.exists(file_path):
            return DownloadResult(ok=False, error="Yuklab olingan fayl topilmadi.", platform=platform)

        size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            try:
                os.remove(file_path)
            except OSError:
                pass
            return DownloadResult(
                ok=False,
                error=f"Fayl hajmi juda katta ({size_mb:.1f} MB). Maksimal: {MAX_FILE_SIZE_MB} MB.",
                platform=platform,
            )

        is_audio = file_path.lower().endswith((".mp3", ".m4a", ".aac", ".ogg", ".wav"))

        return DownloadResult(
            ok=True,
            file_path=file_path,
            title=(info.get("title") or "")[:200],
            duration=int(info.get("duration") or 0),
            width=info.get("width"),
            height=info.get("height"),
            is_audio=is_audio,
            platform=platform,
        )

    except Exception as e:
        msg = str(e)
        logger.exception(f"Download failed for {url}: {msg}")
        if "Unsupported URL" in msg:
            err = "Bu havola qo'llab-quvvatlanmaydi."
        elif "Private" in msg or "login" in msg.lower():
            err = "Video shaxsiy yoki kirish talab qiladi."
        elif "not available" in msg.lower() or "removed" in msg.lower():
            err = "Video mavjud emas yoki o'chirilgan."
        else:
            err = "Yuklab bo'lmadi. Havolani tekshiring va qaytadan urinib ko'ring."
        return DownloadResult(ok=False, error=err, platform=platform)


async def download_media(url: str) -> DownloadResult:
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    file_id = uuid.uuid4().hex[:12]
    out_template = os.path.join(DOWNLOAD_DIR, f"{file_id}.%(ext)s")

    return await asyncio.to_thread(_blocking_download, url, out_template)
