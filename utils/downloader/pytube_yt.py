"""YouTube downloader using pytubefix — different extraction path than yt-dlp,
often bypasses 'Sign in to confirm' bot-check on datacenter IPs."""

import logging
import os
import uuid
from typing import Optional

from pytubefix import YouTube

from data.config import DOWNLOAD_DIR, MAX_FILE_SIZE_MB

logger = logging.getLogger(__name__)


def _blocking_pytube_download(url: str):
    """Download a YouTube video via pytubefix. Returns (file_path, info_dict) or raises."""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    yt = YouTube(url, use_po_token=False)

    # Trigger metadata fetch
    title = yt.title or "youtube_video"
    duration = yt.length or 0
    max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024

    # Prefer progressive MP4 streams (video+audio in one file — no merge needed)
    # capped at 720p for size, under file-size limit
    stream = (
        yt.streams
        .filter(progressive=True, file_extension="mp4")
        .filter(res="720p").order_by("resolution").desc().first()
        or yt.streams.filter(progressive=True, file_extension="mp4").filter(res="480p").first()
        or yt.streams.filter(progressive=True, file_extension="mp4").filter(res="360p").first()
        or yt.streams.filter(progressive=True, file_extension="mp4").order_by("resolution").desc().first()
    )

    # If progressive stream exceeds limit, try lower resolution
    if stream and stream.filesize and stream.filesize > max_bytes:
        stream = (
            yt.streams.filter(progressive=True, file_extension="mp4")
            .order_by("resolution").asc().first()
        )

    if not stream:
        raise RuntimeError("No suitable progressive MP4 stream found")

    file_id = uuid.uuid4().hex[:12]
    filename = f"{file_id}.mp4"
    out_path = stream.download(output_path=DOWNLOAD_DIR, filename=filename)

    if not os.path.exists(out_path):
        raise RuntimeError("Downloaded file missing")

    size_mb = os.path.getsize(out_path) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        try:
            os.remove(out_path)
        except OSError:
            pass
        raise RuntimeError(f"Fayl hajmi: {size_mb:.1f} MB > {MAX_FILE_SIZE_MB} MB")

    return {
        "file_path": out_path,
        "title": title[:200],
        "duration": duration,
        "width": stream.resolution,
        "height": None,
        "filesize_mb": size_mb,
    }


async def download_youtube_pytube(url: str):
    import asyncio
    return await asyncio.to_thread(_blocking_pytube_download, url)
