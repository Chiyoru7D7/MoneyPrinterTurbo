"""
Video Analyzer Service — Extract keywords from competitor/source videos.

Flow:
  1. Search: ``yt-dlp "ytsearchN:topic"`` to find trending videos on a topic
  2. Download audio: ``yt-dlp -x --audio-format mp3 <url>``
  3. Transcribe: faster-whisper (shared model from app.services.subtitle)
  4. Extract keywords: LLM call to pull out search terms, topics, hooks
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

from loguru import logger

from app.config import config
from app.utils import utils


def _yt_dlp_binary() -> str:
    """Return the yt-dlp executable path (module or standalone)."""
    return "yt-dlp"


def search_videos(topic: str, count: int = 5) -> List[dict]:
    """Search for trending videos on a topic using yt-dlp's YouTube search.

    Returns a list of dicts with keys: id, title, duration, url, channel, view_count.
    """
    if not topic or not topic.strip():
        return []

    query = "ytsearch{}:{}".format(min(count, 20), topic.strip())
    logger.info("[VideoAnalyzer] searching: {}".format(query))

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
        logger.error("[VideoAnalyzer] yt-dlp search failed: {}".format(exc))
        return []

    if result.returncode != 0:
        logger.error("[VideoAnalyzer] yt-dlp search error: {}".format(
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
                "title": info.get("title", ""),
                "duration": info.get("duration", 0),
                "url": info.get("webpage_url", info.get("url", "")),
                "channel": info.get("channel", info.get("uploader", "")),
                "view_count": info.get("view_count", 0),
            })
        except json.JSONDecodeError:
            continue

    logger.info("[VideoAnalyzer] found {} video(s) for '{}'".format(len(videos), topic))
    return videos


def download_audio(url: str, output_dir: str | None = None) -> Optional[str]:
    """Download audio-only from a video URL using yt-dlp.

    Returns the path to the extracted MP3 file, or None on failure.
    """
    if not url or not url.strip():
        return None

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
                "-x",                      # extract audio
                "--audio-format", "mp3",
                "--audio-quality", "128K",
                "-o", output_template,
                "--no-playlist",
                "--no-progress",
                "--quiet",
            ],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.error("[VideoAnalyzer] audio download failed: {}".format(exc))
        return None

    if result.returncode != 0:
        logger.error("[VideoAnalyzer] yt-dlp download error: {}".format(
            (result.stderr or "").strip()
        ))
        return None

    # Find the downloaded MP3
    mp3_files = list(out_dir.glob("*.mp3"))
    if not mp3_files:
        logger.error("[VideoAnalyzer] no MP3 found after download in {}".format(out_dir))
        return None

    audio_path = str(mp3_files[0])
    logger.info("[VideoAnalyzer] audio saved: {}".format(audio_path))
    return audio_path


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

    model_size = config.whisper.get("model_size", "large-v3")
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


def extract_keywords(transcript: str, topic_hint: str = "") -> dict:
    """Extract video-making keywords from a transcript using LLM.

    Returns a dict with:
      - subject: a concise video subject line (for video_subject param)
      - keywords: list of search terms (for material download)
      - hooks: list of attention-grabbing phrases found in the source
      - tone: detected tone (professional/urgent/casual/humorous/emotional)
    """
    if not transcript or len(transcript) < 50:
        logger.warning("[VideoAnalyzer] transcript too short for keyword extraction")
        return _default_keywords(topic_hint)

    from app.services.llm import _generate_response

    hint_line = ""
    if topic_hint:
        hint_line = "The video is broadly about: {}".format(topic_hint)

    prompt = """You are a content strategist analyzing a competitor's video transcript.

{}
TRANSCRIPT:
{}

Extract the following from this video transcript. Return ONLY valid JSON:

{{
  "subject": "A compelling Chinese video subject line (for Douyin/TikTok style, 10-30 chars)",
  "keywords": ["keyword1", "keyword2", ...],
  "hooks": ["attention hook 1", "attention hook 2", ...],
  "tone": "one of: professional/urgent/casual/humorous/emotional"
}}

Rules:
- subject: write in Chinese, make it catchy like a short-video title
- keywords: 5-8 specific search terms that would find stock footage for THIS topic.
  Include both broad and specific terms. Write in English for Pexels/Pixabay search.
- hooks: 3-5 attention-grabbing opening lines or phrases found in the video
- tone: pick the dominant emotional tone

Output ONLY the JSON object, no markdown, no explanation.""".format(
        hint_line,
        transcript[:8000],  # Truncate to avoid token limits
    )

    try:
        response = _generate_response(prompt)
        # Strip markdown code fences if present
        response = response.strip()
        if response.startswith("```"):
            response = response.split("\n", 1)[-1]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()

        result = json.loads(response)
        logger.info("[VideoAnalyzer] extracted {} keywords, {} hooks".format(
            len(result.get("keywords", [])),
            len(result.get("hooks", [])),
        ))
        return result
    except Exception as exc:
        logger.error("[VideoAnalyzer] keyword extraction failed: {}".format(exc))
        return _default_keywords(topic_hint)


def _default_keywords(topic_hint: str = "") -> dict:
    """Fallback when LLM extraction fails."""
    subject = topic_hint or "热门视频创作"
    return {
        "subject": subject,
        "keywords": [topic_hint] if topic_hint else [],
        "hooks": [],
        "tone": "professional",
    }


def analyze_video(url_or_topic: str, is_topic: bool = False) -> dict:
    """Full analysis pipeline: search (if topic) → download → transcribe → extract.

    Args:
        url_or_topic: A video URL, or a topic string if is_topic=True.
        is_topic: If True, search for the top video on this topic first.

    Returns:
        {
            "subject": str,
            "keywords": [str, ...],
            "hooks": [str, ...],
            "tone": str,
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
            error = "No videos found for topic: {}".format(url_or_topic)
            return {"subject": "", "keywords": [], "hooks": [], "tone": "",
                    "transcript": "", "source_url": "", "source_title": "", "error": error}
        source_url = videos[0]["url"]
        source_title = videos[0]["title"]

    # Download audio
    audio_path = download_audio(source_url)
    if not audio_path:
        error = "Failed to download audio from: {}".format(source_url)
        return {"subject": "", "keywords": [], "hooks": [], "tone": "",
                "transcript": "", "source_url": source_url, "source_title": source_title,
                "error": error}

    # Transcribe
    transcript = transcribe_audio(audio_path)
    if not transcript:
        error = "Failed to transcribe audio"
        _cleanup(audio_path)
        return {"subject": "", "keywords": [], "hooks": [], "tone": "",
                "transcript": "", "source_url": source_url, "source_title": source_title,
                "error": error}

    # Extract keywords
    result = extract_keywords(transcript, topic_hint=url_or_topic if is_topic else "")
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
