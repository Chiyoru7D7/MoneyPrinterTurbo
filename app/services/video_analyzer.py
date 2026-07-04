"""
Video Analyzer Service — Extract creative brief from TikTok videos.

Flow:
  1. Search: ``yt-dlp "tiktoksearchN:topic"`` to find trending videos
  2. Download: ``yt-dlp <url>`` to get the video (or audio-only)
  3. Transcribe: faster-whisper (shared model from app.services.subtitle)
  4. Extract prompt: LLM generates a creative brief for a similar-but-different video
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

from loguru import logger

from app.config import config
from app.utils import utils


def _yt_dlp_binary() -> str:
    """Return the yt-dlp executable path."""
    return "yt-dlp"


def search_videos(topic: str, count: int = 5) -> List[dict]:
    """Search TikTok for trending videos on a topic.

    Returns a list of dicts with keys: id, title, duration, url, channel, view_count.
    """
    if not topic or not topic.strip():
        return []

    query = "tiktoksearch{}:{}".format(min(count, 20), topic.strip())
    logger.info("[VideoAnalyzer] searching TikTok: {}".format(query))

    try:
        result = subprocess.run(
            [
                _yt_dlp_binary(),
                query,
                "--dump-json",
                "--no-playlist",
                "--flat-playlist",
                "--skip-download",
                "--quiet",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.error("[VideoAnalyzer] TikTok search failed: {}".format(exc))
        return []

    if result.returncode != 0:
        logger.error("[VideoAnalyzer] TikTok search error: {}".format(
            (result.stderr or "").strip()
        ))
        return []

    videos = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        try:
            info = json.loads(line)
            videos.append({
                "id": info.get("id", ""),
                "title": info.get("title", "")[:80],
                "duration": info.get("duration", 0),
                "url": info.get("webpage_url", info.get("url", "")),
                "channel": info.get("uploader", info.get("channel", "")),
                "view_count": info.get("view_count", 0),
            })
        except json.JSONDecodeError:
            continue

    logger.info("[VideoAnalyzer] found {} TikTok(s) for '{}'".format(len(videos), topic))
    return videos


def download_audio(url: str, output_dir: str | None = None) -> Tuple[Optional[str], Optional[str]]:
    """Download audio from a TikTok video URL.

    Returns (path, error). path is the MP3 file path or None; error is a
    human-readable message or None.
    """
    if not url or not url.strip():
        return None, "empty URL"

    if output_dir:
        out_dir = Path(output_dir)
    else:
        out_dir = Path(tempfile.mkdtemp(prefix="mpt_audio_"))
    out_dir.mkdir(parents=True, exist_ok=True)

    output_template = str(out_dir / "%(id)s.%(ext)s")
    logger.info("[VideoAnalyzer] downloading audio from: {}".format(url))

    try:
        result = subprocess.run(
            [
                _yt_dlp_binary(),
                url,
                "-x",
                "--audio-format", "mp3",
                "--audio-quality", "128K",
                "-o", output_template,
                "--no-playlist",
                "--no-progress",
            ],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except subprocess.TimeoutExpired:
        msg = "yt-dlp timed out after 300s downloading: {}".format(url)
        logger.error("[VideoAnalyzer] {}".format(msg))
        return None, msg
    except OSError as exc:
        msg = "yt-dlp not found or failed to start: {}".format(exc)
        logger.error("[VideoAnalyzer] {}".format(msg))
        return None, msg

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        error_lines = [l for l in stderr.split("\n") if l.strip()]
        short_err = ""
        for line in reversed(error_lines):
            if "ERROR:" in line:
                short_err = line[line.index("ERROR:"):]
                break
        if not short_err and error_lines:
            short_err = error_lines[-1]
        msg = short_err or "yt-dlp exit code {}".format(result.returncode)
        logger.error("[VideoAnalyzer] TikTok download error: {}".format(msg))
        return None, msg

    # Find the downloaded MP3
    mp3_files = list(out_dir.glob("*.mp3"))
    if not mp3_files:
        msg = "no MP3 found after download in {}".format(out_dir)
        logger.error("[VideoAnalyzer] {}".format(msg))
        return None, msg

    audio_path = str(mp3_files[0])
    logger.info("[VideoAnalyzer] audio saved: {}".format(audio_path))
    return audio_path, None


def download_video(url: str, output_dir: str | None = None) -> Tuple[Optional[str], Optional[str]]:
    """Download full TikTok video (with audio).

    Returns (path, error). path is the MP4 file path or None.
    """
    if not url or not url.strip():
        return None, "empty URL"

    if output_dir:
        out_dir = Path(output_dir)
    else:
        out_dir = Path(tempfile.mkdtemp(prefix="mpt_video_"))
    out_dir.mkdir(parents=True, exist_ok=True)

    output_template = str(out_dir / "%(id)s.%(ext)s")
    logger.info("[VideoAnalyzer] downloading video from: {}".format(url))

    try:
        result = subprocess.run(
            [
                _yt_dlp_binary(),
                url,
                "-f", "best[ext=mp4]",
                "-o", output_template,
                "--no-playlist",
                "--no-progress",
            ],
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
    except subprocess.TimeoutExpired:
        msg = "yt-dlp timed out downloading: {}".format(url)
        logger.error("[VideoAnalyzer] {}".format(msg))
        return None, msg
    except OSError as exc:
        msg = "yt-dlp not found: {}".format(exc)
        logger.error("[VideoAnalyzer] {}".format(msg))
        return None, msg

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        msg = "TikTok download error: {}".format(stderr[:300] if stderr else "unknown")
        logger.error("[VideoAnalyzer] {}".format(msg))
        return None, msg

    mp4_files = list(out_dir.glob("*.mp4"))
    if not mp4_files:
        return None, "no MP4 found after download"

    video_path = str(mp4_files[0])
    logger.info("[VideoAnalyzer] video saved: {}".format(video_path))
    return video_path, None


def transcribe_audio(audio_path: str) -> str:
    """Transcribe an audio file to text using faster-whisper.

    Returns the full transcript text, or empty string on failure.
    """
    if not audio_path or not os.path.isfile(audio_path):
        logger.error("[VideoAnalyzer] audio file not found: {}".format(audio_path))
        return ""

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        logger.error("[VideoAnalyzer] faster_whisper not installed")
        return ""

    # Render starter = 512MB RAM, large-v3 = 3GB → OOM
    # Use WHISPER_MODEL_SIZE env var override, or fall back to base when low-memory
    _low_mem = os.getenv("LOW_MEMORY_MODE", "").lower() in ("1", "true", "yes")
    model_size = os.getenv("WHISPER_MODEL_SIZE", "")
    if not model_size:
        model_size = "base" if _low_mem else config.whisper.get("model_size", "large-v3")
    device = config.whisper.get("device", "cpu")
    compute_type = config.whisper.get("compute_type", "int8")

    model_path = "{}/models/whisper-{}".format(utils.root_dir(), model_size)
    if not os.path.isdir(model_path) or not os.path.isfile("{}/model.bin".format(model_path)):
        model_path = model_size

    logger.info("[VideoAnalyzer] loading whisper model: {}".format(model_path))
    try:
        model = WhisperModel(
            model_size_or_path=model_path,
            device=device,
            compute_type=compute_type,
        )
    except Exception as exc:
        logger.error("[VideoAnalyzer] failed to load whisper: {}".format(exc))
        return ""

    logger.info("[VideoAnalyzer] transcribing: {}".format(audio_path))
    segments, info = model.transcribe(
        audio_path,
        beam_size=5,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500),
    )

    language = info.language
    logger.info("[VideoAnalyzer] detected language: {} (prob={:.2f})".format(
        language, info.language_probability
    ))

    transcript_parts = []
    for segment in segments:
        text = segment.text.strip()
        if text:
            transcript_parts.append(text)

    transcript = " ".join(transcript_parts)
    logger.info("[VideoAnalyzer] transcript length: {} chars".format(len(transcript)))
    return transcript


def extract_prompt(transcript: str, topic_hint: str = "") -> dict:
    """Extract a video generation prompt from a TikTok transcript using LLM.

    Returns a dict with:
      - prompt: full creative brief for dashboard generation (Chinese)
      - reference: what made the original video effective
      - keywords: search terms for stock footage (English, for Pexels/Pixabay)
    """
    if not transcript or len(transcript) < 50:
        logger.warning("[VideoAnalyzer] transcript too short for prompt extraction")
        return _default_prompt(topic_hint)

    from app.services.llm import _generate_response

    hint_line = ""
    if topic_hint:
        hint_line = "The video is broadly about: {}".format(topic_hint)

    llm_prompt = """You reverse-engineer viral TikTok videos into creative briefs.

{}
TRANSCRIPT:
{}

Analyze this TikTok transcript and produce a creative brief for making a SIMILAR BUT DIFFERENT video. Return ONLY valid JSON:

{{
  "prompt": "A detailed creative brief in Chinese (80-200 chars). Describe: what topic to cover, what visual style, what opening hook style, what emotional tone, what pacing. Make it specific enough to generate a new original video in the same genre but NOT a copy.",
  "reference": "What made the original video effective (1-2 sentences in Chinese)",
  "keywords": ["keyword1", "keyword2", ...]
}}

Rules:
- prompt: write in Chinese. Be specific — mention visual style, hook style, pacing, tone.
  This will be pasted directly into a video generator. Make it self-contained and actionable.
- reference: explain the original's success formula so the creator understands the strategy
- keywords: 5-8 English search terms for stock footage sites (Pexels/Pixabay)

Output ONLY the JSON object, no markdown, no explanation.""".format(
        hint_line,
        transcript[:8000],
    )

    try:
        response = _generate_response(llm_prompt)
        response = response.strip()
        if response.startswith("```"):
            response = response.split("\n", 1)[-1]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()

        result = json.loads(response)
        logger.info("[VideoAnalyzer] prompt extracted ({} chars), {} keywords".format(
            len(result.get("prompt", "")),
            len(result.get("keywords", [])),
        ))
        return result
    except Exception as exc:
        logger.error("[VideoAnalyzer] prompt extraction failed: {}".format(exc))
        return _default_prompt(topic_hint)


def _default_prompt(topic_hint: str = "") -> dict:
    """Fallback when LLM extraction fails."""
    fallback = topic_hint or "热门视频创作"
    return {
        "prompt": "创作一个关于「{}」的短视频，节奏紧凑，开头3秒抓住注意力，使用真实素材和简洁文案，适合抖音平台。".format(fallback),
        "reference": "",
        "keywords": [topic_hint] if topic_hint else [],
    }


def analyze_video(url_or_topic: str, is_topic: bool = False) -> dict:
    """Full analysis pipeline: search (if topic) -> download -> transcribe -> extract.

    Args:
        url_or_topic: A TikTok video URL, or a topic string if is_topic=True.
        is_topic: If True, search for the top video on this topic first.

    Returns:
        {
            "prompt": str,
            "reference": str,
            "keywords": [str, ...],
            "transcript": str,
            "source_url": str,
            "source_title": str,
            "error": str or None,
        }
    """
    source_url = url_or_topic
    source_title = ""
    error = None

    if is_topic:
        videos = search_videos(url_or_topic, count=1)
        if not videos:
            error = "No TikTok videos found for topic: {}".format(url_or_topic)
            return {"prompt": "", "reference": "", "keywords": [],
                    "transcript": "", "source_url": "", "source_title": "", "error": error}
        source_url = videos[0]["url"]
        source_title = videos[0]["title"]

    # Download audio
    audio_path, dl_error = download_audio(source_url)
    if not audio_path:
        error = "Failed to download TikTok audio: {}".format(dl_error or source_url)
        return {"prompt": "", "reference": "", "keywords": [],
                "transcript": "", "source_url": source_url, "source_title": source_title,
                "error": error}

    # Transcribe
    transcript = transcribe_audio(audio_path)
    if not transcript:
        error = "Failed to transcribe audio"
        _cleanup(audio_path)
        return {"prompt": "", "reference": "", "keywords": [],
                "transcript": "", "source_url": source_url, "source_title": source_title,
                "error": error}

    # Extract prompt
    result = extract_prompt(transcript, topic_hint=url_or_topic if is_topic else "")
    result["transcript"] = transcript
    result["source_url"] = source_url
    result["source_title"] = source_title
    result["error"] = None

    _cleanup(audio_path)
    return result


def _cleanup(audio_path: str):
    """Remove temporary audio file and its directory."""
    try:
        path = Path(audio_path)
        if path.exists():
            path.unlink()
        # Remove parent dir if empty
        if path.parent.exists() and not any(path.parent.iterdir()):
            path.parent.rmdir()
    except Exception:
        pass
