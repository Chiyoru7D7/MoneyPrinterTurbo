"""
Thumbnail generation service for MoneyPrinterTurbo.

Generates an eye-catching thumbnail image for each generated video.
Primary path: AI-generated cover via Cloudflare Workers AI (FLUX.1-schnell).
Fallback: extract a frame from the middle of the rendered video via FFmpeg.
"""

import os
import subprocess
from pathlib import Path
from typing import Optional

from loguru import logger

from app.config import config
from app.utils import utils


def _extract_frame_ffmpeg(
    video_path: str,
    output_path: str,
    time_offset: float = 0.0,
) -> bool:
    """Extract a single frame from a video using FFmpeg.

    Args:
        video_path: Path to the source MP4.
        output_path: Where to write the JPEG/PNG.
        time_offset: Timestamp in seconds (0 = auto-detect middle).

    Returns:
        True on success.
    """
    if not os.path.exists(video_path):
        logger.warning(f"[Thumbnail] video not found for frame extract: {video_path}")
        return False

    ffmpeg_bin = utils.get_ffmpeg_binary()

    # Probe duration if no specific offset given
    if time_offset <= 0:
        try:
            probe_cmd = [
                ffmpeg_bin,
                "-i", video_path,
                "-f", "null", "-",
            ]
            result = subprocess.run(
                probe_cmd,
                capture_output=True, text=True, timeout=30,
            )
            # Parse duration from stderr (ffmpeg writes info to stderr)
            import re
            match = re.search(
                r"Duration:\s*(\d+):(\d+):(\d+)\.(\d+)",
                result.stderr,
            )
            if match:
                h, m, s, cs = map(int, match.groups())
                duration = h * 3600 + m * 60 + s + cs / 100.0
                time_offset = duration * 0.4  # 40% into video — usually a good frame
            else:
                time_offset = 1.0  # fallback: 1 second in
        except Exception as exc:
            logger.warning(f"[Thumbnail] duration probe failed: {exc}")
            time_offset = 1.0

    cmd = [
        ffmpeg_bin, "-y",
        "-ss", str(time_offset),
        "-i", video_path,
        "-vframes", "1",
        "-q:v", "2",
        output_path,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            logger.error(
                f"[Thumbnail] ffmpeg frame extract failed: "
                f"{result.stderr[-300:]}"
            )
            return False
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.success(
                f"[Thumbnail] frame extracted at {time_offset:.1f}s → "
                f"{Path(output_path).name}"
            )
            return True
        return False
    except Exception as exc:
        logger.error(f"[Thumbnail] ffmpeg frame extract error: {exc}")
        return False


def _generate_ai_thumbnail(
    video_subject: str,
    video_script: str = "",
    output_path: str = "",
) -> bool:
    """Generate a thumbnail via Cloudflare Workers AI.

    Args:
        video_subject: The video topic/title.
        video_script: First 200 chars of narration for context.
        output_path: Where to write the PNG/JPG.

    Returns:
        True if the image was generated and saved.
    """
    account_id = (
        config.app.get("cloudflare_account_id", "")
        or os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
    )
    api_token = (
        config.app.get("cloudflare_api_token", "")
        or os.environ.get("CLOUDFLARE_API_TOKEN", "")
    )

    if not account_id or not api_token:
        logger.info("[Thumbnail] no Cloudflare credentials — skip AI thumbnail")
        return False

    try:
        from app.services.image_gen import CloudflareImageGen
    except ImportError as exc:
        logger.warning(f"[Thumbnail] cannot import CloudflareImageGen: {exc}")
        return False

    # Build a thumbnail-specific prompt
    script_snippet = (video_script or "")[:200].strip()
    prompt = (
        f"YouTube thumbnail for video titled: \"{video_subject}\". "
        f"Bold eye-catching composition, vibrant colors, "
        f"professional studio lighting, 16:9 cinematic poster style, "
        f"high contrast, click-worthy, no text overlay."
    )
    if script_snippet:
        prompt += f" Video context: {script_snippet}"

    try:
        gen = CloudflareImageGen(account_id=account_id, api_token=api_token)
        img_path = gen.generate(prompt=prompt, prefix="thumbnail")
        if img_path and img_path.exists():
            # Convert PNG → JPG for smaller file size in dashboard
            if output_path.lower().endswith((".jpg", ".jpeg")):
                from PIL import Image
                img = Image.open(img_path)
                # Convert RGBA → RGB for JPEG
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                img.save(output_path, "JPEG", quality=85)
                logger.success(
                    f"[Thumbnail] AI thumbnail saved: "
                    f"{Path(output_path).name} "
                    f"({Path(output_path).stat().st_size / 1024:.0f} KB)"
                )
            else:
                import shutil
                shutil.move(str(img_path), output_path)
                logger.success(
                    f"[Thumbnail] AI thumbnail saved: {Path(output_path).name}"
                )
            return True
        else:
            logger.warning("[Thumbnail] Cloudflare returned no image")
            return False
    except Exception as exc:
        logger.warning(f"[Thumbnail] AI thumbnail generation failed: {exc}")
        return False


def generate_thumbnail(
    task_id: str,
    video_subject: str,
    video_script: str = "",
    video_path: Optional[str] = None,
) -> Optional[str]:
    """Generate a thumbnail for a completed video.

    Tries AI generation first (Cloudflare Workers AI + FLUX.1-schnell),
    then falls back to extracting a frame from the rendered video.

    Args:
        task_id: Task UUID — thumbnail saved to ``tasks/<task_id>/thumbnail.jpg``.
        video_subject: Video topic used as the thumbnail prompt seed.
        video_script: Narration text for additional prompt context.
        video_path: Path to the final MP4 for frame-extraction fallback.

    Returns:
        Absolute path to ``thumbnail.jpg`` on success, ``None`` on failure.
    """
    task_dir = utils.task_dir(task_id)
    output_path = os.path.join(task_dir, "thumbnail.jpg")

    # Already exists? Skip regeneration
    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        logger.debug(f"[Thumbnail] already exists: {output_path}")
        return output_path

    logger.info(f"[Thumbnail] generating for task {task_id[:8]}...")

    # 1. Try AI thumbnail
    if _generate_ai_thumbnail(
        video_subject=video_subject,
        video_script=video_script,
        output_path=output_path,
    ):
        return output_path

    # 2. Fallback: extract frame from video
    if video_path and os.path.exists(video_path):
        logger.info("[Thumbnail] falling back to video frame extraction")
        if _extract_frame_ffmpeg(video_path, output_path):
            return output_path

    logger.error("[Thumbnail] all methods failed — no thumbnail generated")
    return None
