"""Instagram downloader using instaloader — anonymous/public posts without login."""

import logging
import os
import re
import uuid
from typing import Optional

import instaloader

from data.config import DOWNLOAD_DIR, MAX_FILE_SIZE_MB

logger = logging.getLogger(__name__)

SHORTCODE_RE = re.compile(r"instagram\.com/(?:reel|p|tv)/([A-Za-z0-9_-]+)", re.I)


def _extract_shortcode(url: str) -> Optional[str]:
    m = SHORTCODE_RE.search(url)
    return m.group(1) if m else None


def _blocking_insta_download(url: str):
    shortcode = _extract_shortcode(url)
    if not shortcode:
        raise RuntimeError("Instagram shortcode topilmadi")

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    work_id = uuid.uuid4().hex[:12]
    work_dir = os.path.join(DOWNLOAD_DIR, f"ig_{work_id}")
    os.makedirs(work_dir, exist_ok=True)

    L = instaloader.Instaloader(
        dirname_pattern=work_dir,
        save_metadata=False,
        download_comments=False,
        download_geotags=False,
        download_video_thumbnails=False,
        compress_json=False,
        quiet=True,
    )

    try:
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        L.download_post(post, target=".")
    except Exception as e:
        raise

    # Find the video file
    video_path = None
    title = ""
    for f in os.listdir(work_dir):
        full = os.path.join(work_dir, f)
        if f.lower().endswith(".mp4"):
            video_path = full
        elif f.lower().endswith(".txt") and not title:
            try:
                with open(full, "r", encoding="utf-8") as fh:
                    title = fh.read().strip()[:200]
            except OSError:
                pass

    if not video_path:
        raise RuntimeError("Videolik post emas (yoki yuklab olishda xato)")

    # Move to DOWNLOAD_DIR root with unique name, cleanup work_dir
    final_name = f"{work_id}.mp4"
    final_path = os.path.join(DOWNLOAD_DIR, final_name)
    os.rename(video_path, final_path)
    for f in os.listdir(work_dir):
        try:
            os.remove(os.path.join(work_dir, f))
        except OSError:
            pass
    try:
        os.rmdir(work_dir)
    except OSError:
        pass

    size_mb = os.path.getsize(final_path) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        try:
            os.remove(final_path)
        except OSError:
            pass
        raise RuntimeError(f"Fayl hajmi: {size_mb:.1f} MB > {MAX_FILE_SIZE_MB} MB")

    try:
        duration = int(post.video_duration or 0)
    except Exception:
        duration = 0

    return {
        "file_path": final_path,
        "title": title or f"Instagram {shortcode}",
        "duration": duration,
        "width": None,
        "height": None,
        "filesize_mb": size_mb,
    }


async def download_instagram(url: str):
    import asyncio
    return await asyncio.to_thread(_blocking_insta_download, url)
