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

URL_REGEX = re.compile(r"https?://[^\s]+", re.IGNORECASE)

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
    filesize_mb: float = 0.0


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


def _format_selector() -> str:
    """
    Size-aware format picker. Prefers pre-merged MP4 (no re-muxing needed),
    falls back to best-video + best-audio under size cap.
    """
    size_mb = MAX_FILE_SIZE_MB
    # Tiers tried in order:
    # 1. Pre-merged MP4 under cap (fastest — no merge/re-encode)
    # 2. Best MP4 video + best m4a audio under cap
    # 3. Best any under cap
    # 4. Best available (last-resort, may exceed cap but at least returns)
    return (
        f"best[ext=mp4][filesize<{size_mb}M]/"
        f"best[ext=mp4][filesize_approx<{size_mb}M]/"
        f"bestvideo[ext=mp4][filesize<{size_mb}M]+bestaudio[ext=m4a]/"
        f"bestvideo[filesize<{size_mb}M]+bestaudio/"
        f"best[filesize<{size_mb}M]/"
        f"best"
    )


COOKIES_FILE = os.environ.get("YT_COOKIES_FILE", "/app/cookies/cookies.txt")

UA_DESKTOP = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def _ydl_opts(out_template: str, platform: str) -> dict:
    opts = {
        "outtmpl": out_template,
        "format": _format_selector(),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
        "concurrent_fragment_downloads": 16,
        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 30,
        "geo_bypass": True,
        "ignoreerrors": False,
        "http_chunk_size": 10 * 1024 * 1024,
        "noprogress": True,
        "user_agent": UA_DESKTOP,
    }
    # Use cookies if file exists (best bypass for YouTube bot-check)
    if os.path.exists(COOKIES_FILE):
        opts["cookiefile"] = COOKIES_FILE

    if platform == "youtube":
        # Multi-client strategy bypasses "Sign in to confirm you're not a bot".
        # tv_embedded + ios + web_safari work without authentication in most cases.
        opts["extractor_args"] = {
            "youtube": {
                "player_client": ["tv_embedded", "ios", "web_safari", "mweb"],
                "player_skip": ["configs"],
            }
        }
        opts["format"] = (
            f"best[ext=mp4][height<=720][filesize<{MAX_FILE_SIZE_MB}M]/"
            f"best[height<=720][filesize<{MAX_FILE_SIZE_MB}M]/"
            f"bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/"
            f"best[ext=mp4][filesize<{MAX_FILE_SIZE_MB}M]/"
            f"best[filesize<{MAX_FILE_SIZE_MB}M]/"
            f"best[height<=720]/best"
        )
    return opts


def _blocking_probe(url: str) -> Optional[dict]:
    """Extract info without downloading (fast)."""
    platform = detect_platform(url)
    probe_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "user_agent": UA_DESKTOP,
    }
    if os.path.exists(COOKIES_FILE):
        probe_opts["cookiefile"] = COOKIES_FILE
    if platform == "youtube":
        probe_opts["extractor_args"] = {
            "youtube": {
                "player_client": ["tv_embedded", "ios", "web_safari", "mweb"],
                "player_skip": ["configs"],
            }
        }
    try:
        with YoutubeDL(probe_opts) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as e:
        logger.debug(f"Probe failed: {e}")
        return None


def _blocking_download(url: str, out_template: str) -> DownloadResult:
    platform = detect_platform(url)
    try:
        with YoutubeDL(_ydl_opts(out_template, platform)) as ydl:
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
                error=(
                    f"❌ Fayl hajmi: <b>{size_mb:.1f} MB</b>\n"
                    f"Telegram limiti: <b>{MAX_FILE_SIZE_MB} MB</b>\n\n"
                    f"Iltimos, qisqaroq video yuboring yoki admin bilan bog'laning."
                ),
                platform=platform,
                filesize_mb=size_mb,
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
            filesize_mb=size_mb,
        )

    except Exception as e:
        msg = str(e)
        logger.exception(f"Download failed for {url}: {msg}")
        low = msg.lower()
        has_cookies = os.path.exists(COOKIES_FILE)
        cookies_hint = "" if has_cookies else (
            "\n\n💡 Admin: cookies yuklansa bu videolar ham ishlaydi. "
            "<code>/admin</code> → 🍪 Cookies (YT/Insta)"
        )
        if "sign in to confirm" in low or "not a bot" in low:
            err = (
                "⚠️ YouTube tasdiqlash so'rayapti (server IP'si bloklangan)." + cookies_hint
            )
        elif "rate-limit" in low or ("login required" in low and "instagram" in low):
            err = (
                "⚠️ Instagram login talab qilyapti (server IP'si bloklangan)." + cookies_hint
            )
        elif "Unsupported URL" in msg:
            err = "Bu havola qo'llab-quvvatlanmaydi."
        elif "Private" in msg or ("login" in low and "required" in low):
            err = "Video shaxsiy yoki kirish talab qiladi." + cookies_hint
        elif "not available" in low or "removed" in low:
            err = "Video mavjud emas yoki o'chirilgan."
        elif "filesize" in low:
            err = f"Video {MAX_FILE_SIZE_MB} MB dan katta."
        else:
            err = "Yuklab bo'lmadi. Havolani tekshiring va qaytadan urinib ko'ring."
        return DownloadResult(ok=False, error=err, platform=platform)


async def probe_media(url: str) -> Optional[dict]:
    return await asyncio.to_thread(_blocking_probe, url)


async def download_media(url: str) -> DownloadResult:
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    file_id = uuid.uuid4().hex[:12]
    out_template = os.path.join(DOWNLOAD_DIR, f"{file_id}.%(ext)s")

    return await asyncio.to_thread(_blocking_download, url, out_template)
