"""YouTube downloader using pytubefix — different extraction path than yt-dlp,
often bypasses 'Sign in to confirm' bot-check on datacenter IPs.

Tries multiple clients in order: WEB_EMBED, IOS, ANDROID_EMBED. Falls back to
bgutil PoToken provider if bot-check hits."""

import logging
import os
import uuid
from typing import Optional, Tuple

import requests
from pytubefix import YouTube
from pytubefix.exceptions import BotDetection, VideoUnavailable

from data.config import DOWNLOAD_DIR, MAX_FILE_SIZE_MB

logger = logging.getLogger(__name__)

CLIENTS = ["WEB_EMBED", "IOS", "ANDROID_EMBED", "TV_EMBED", "WEB"]
BGUTIL_URL = os.environ.get("POT_PROVIDER_URL", "http://bgutil:4416")


def _bgutil_token(video_id: str) -> Optional[Tuple[str, str]]:
    """Fetch (visitor_data, po_token) from bgutil provider."""
    try:
        r = requests.post(
            f"{BGUTIL_URL}/get_pot",
            json={"content_binding": video_id},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        po_token = data.get("po_token") or data.get("poToken")
        visitor_data = data.get("visitor_identifier") or data.get("visitorData", "")
        if po_token:
            return (visitor_data or "", po_token)
    except Exception as e:
        logger.warning(f"bgutil PoToken fetch failed: {e}")
    return None


def _pick_stream(yt: YouTube, max_bytes: int):
    stream = (
        yt.streams.filter(progressive=True, file_extension="mp4")
        .filter(res="720p").order_by("resolution").desc().first()
        or yt.streams.filter(progressive=True, file_extension="mp4").filter(res="480p").first()
        or yt.streams.filter(progressive=True, file_extension="mp4").filter(res="360p").first()
        or yt.streams.filter(progressive=True, file_extension="mp4")
            .order_by("resolution").desc().first()
    )
    if stream and stream.filesize and stream.filesize > max_bytes:
        stream = (
            yt.streams.filter(progressive=True, file_extension="mp4")
            .order_by("resolution").asc().first()
        )
    return stream


def _try_client(url: str, client: str, video_id: str) -> Optional[YouTube]:
    """Try a specific client, with optional bgutil PoToken."""
    try:
        yt = YouTube(url, client=client)
        _ = yt.title  # trigger extraction
        return yt
    except BotDetection:
        logger.info(f"pytubefix bot-check on client={client}, trying with PoToken")
    except VideoUnavailable as e:
        logger.warning(f"pytubefix video unavailable ({client}): {e}")
        return None
    except Exception as e:
        logger.debug(f"pytubefix client={client} failed: {e}")

    # Retry with bgutil PoToken
    tok = _bgutil_token(video_id)
    if not tok:
        return None
    visitor_data, po_token = tok

    def _verifier():
        return visitor_data, po_token

    try:
        yt = YouTube(
            url,
            use_po_token=True,
            po_token_verifier=_verifier,
            client=client,
        )
        _ = yt.title
        return yt
    except Exception as e:
        logger.debug(f"pytubefix client={client} with PoToken failed: {e}")
        return None


def _blocking_pytube_download(url: str):
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    # extract video_id for PoToken binding
    video_id = ""
    for sep in ("v=", "youtu.be/", "/shorts/"):
        if sep in url:
            video_id = url.split(sep, 1)[1].split("&")[0].split("?")[0].split("/")[0]
            break

    yt = None
    last_err = None
    for client in CLIENTS:
        try:
            yt = _try_client(url, client, video_id)
            if yt:
                logger.info(f"pytubefix succeeded with client={client}")
                break
        except Exception as e:
            last_err = e
            continue

    if not yt:
        raise RuntimeError(f"Barcha client'lar muvaffaqiyatsiz. Oxirgi xato: {last_err}")

    title = yt.title or "youtube_video"
    duration = yt.length or 0
    max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024

    stream = _pick_stream(yt, max_bytes)
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
