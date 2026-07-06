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

    Returns a dict mapped to the MoneyPrinterTurbo pipeline stages:

        prompt
            Concise topic + style (80-200 chars, English).
            Used as ``video_subject`` → feeds the script generator LLM.

        script_prompt
            Detailed creative direction (200-1000 chars, English).
            Used as ``video_script_prompt`` — controls narrative structure,
            hook approach, pacing, tone, and speaker persona.

        reference
            Why the original video was effective (1-2 sentences, English).

        keywords
            5-8 English search terms for Pexels / Pixabay / Coverr stock
            footage.  Each term 1-3 words, ordered by visual importance.

        visual_style
            One of: cinematic | documentary | bold_text | animation |
            product_demo | talking_head | text_overlay | lifestyle

        bgm_mood
            One of: energetic | calm | dramatic | upbeat | lofi | none
    """
    if not transcript or len(transcript) < 50:
        logger.warning("[VideoAnalyzer] transcript too short for prompt extraction")
        return _default_prompt(topic_hint)

    from app.services.llm import _generate_response

    hint_line = ""
    if topic_hint:
        hint_line = "The video is broadly about: {}".format(topic_hint)

    llm_prompt = """You reverse-engineer viral TikTok videos into structured creative briefs for an automated video generator.

The generator pipeline works like this:
  1. Script LLM writes narration from a topic + style hint
  2. Stock footage (Pexels/Pixabay/Coverr) is searched by English keywords
  3. TTS voiceover + burned-in subtitles on the video
  4. Clips are concatenated (random or sequential) with optional transitions + background music

{}
TRANSCRIPT:
{}

Analyze this TikTok transcript. Figure out what made it work, then design a SIMILAR BUT DIFFERENT video spec. Return ONLY valid JSON:

{{
  "prompt": "Concise topic + style description (80-200 chars, English). This is the video_subject for the script generator. Encode: what the video is about, the visual vibe, the hook style, and the emotional tone. Make it specific and self-contained.",
  "script_prompt": "Detailed creative direction (200-1000 chars, English). This is the video_script_prompt. Describe: narrative structure (hook → body → CTA), pacing, speaker persona, what beats to hit, how to open, how to close. Also mention what visual footage should accompany each narrative beat so search keywords can match.",
  "reference": "What made the original video effective (1-2 sentences, English)",
  "keywords": ["keyword1", "keyword2", ...],
  "visual_style": "cinematic|documentary|bold_text|animation|product_demo|talking_head|text_overlay|lifestyle",
  "bgm_mood": "energetic|calm|dramatic|upbeat|lofi|none"
}}

Rules:
- prompt: 80-200 chars. Write in English. Encode topic + hook style + visual vibe. Example: "A dramatic reveal of eco-friendly sneakers made from ocean plastic — fast cuts, bold text overlays, urgent tone targeting Gen Z sustainability shoppers"
- script_prompt: 200-1000 chars. Write in English. Be a director's brief — specify the narrative arc, pacing, speaker energy level, what makes the hook work, how to structure the body, what CTA to end with.
- reference: 1-2 sentences analyzing the original's viral mechanics
- keywords: 5-8 English terms (1-3 words each) for stock footage searches on Pexels/Pixabay. Order by visual importance — earlier terms match opening scenes. Use concrete visual nouns: "ocean plastic pollution" not "sustainability".
- visual_style: pick the closest match from the list above based on the original's editing style
- bgm_mood: pick the closest match based on the original's audio energy

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
        # Ensure backward-compatible minimum fields
        result.setdefault("reference", "")
        result.setdefault("script_prompt", "")
        result.setdefault("visual_style", "cinematic")
        result.setdefault("bgm_mood", "energetic")
        return result
    except Exception as exc:
        logger.error("[VideoAnalyzer] prompt extraction failed: {}".format(exc))
        return _default_prompt(topic_hint)


def _default_prompt(topic_hint: str = "") -> dict:
    """Fallback when LLM extraction fails."""
    fallback = topic_hint or "trending video"
    return {
        "prompt": "Create a short video about \"{}\" with tight pacing, a hook in the first 3 seconds, real footage, and concise text overlays — optimized for TikTok-style short-form video platforms.".format(fallback),
        "script_prompt": "Hook the viewer in the first 3 seconds with a bold statement or question about {}. Keep pacing fast — short sentences, high energy. Use a problem → solution narrative arc. End with a clear call to action.".format(fallback),
        "reference": "",
        "keywords": [topic_hint] if topic_hint else [],
        "visual_style": "cinematic",
        "bgm_mood": "energetic",
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


def score_alignment(research_brief: dict, generated_script: str,
                    generated_terms: list, video_duration: float = 0) -> dict:
    """Score how well a generated video matches the TikTok research brief.

    Uses the LLM as a judge to compare the creative intent (from
    :func:`extract_prompt`) against the actual pipeline output.

    Args:
        research_brief: Dict returned by :func:`extract_prompt` with keys
            ``prompt``, ``script_prompt``, ``keywords``, ``visual_style``,
            ``bgm_mood``, ``reference``.
        generated_script: The narration script produced by the pipeline.
        generated_terms: The search terms used for stock footage.
        video_duration: Actual video duration in seconds (0 = unknown).

    Returns:
        A dict with alignment scores and a summary:
        ::
            {
                "overall": 0-100,
                "topic_match": 0-100,
                "tone_match": 0-100,
                "structure_match": 0-100,
                "visual_match": 0-100,
                "summary": "2-3 sentence verdict",
                "gaps": ["what's missing", "..."],
            }
    """
    if not generated_script or len(generated_script) < 20:
        logger.warning("[VideoAnalyzer] script too short for alignment scoring")
        return _empty_alignment()

    from app.services.llm import _generate_response

    brief_prompt = research_brief.get("prompt", "")
    brief_script_dir = research_brief.get("script_prompt", "")
    brief_keywords = research_brief.get("keywords", [])
    brief_visual = research_brief.get("visual_style", "")
    brief_bgm = research_brief.get("bgm_mood", "")

    llm_prompt = """You score how well a generated video script matches a creative brief.

CREATIVE BRIEF:
Topic/Style: {brief_prompt}
Director's Notes: {brief_script_dir}
Intended Keywords: {brief_keywords}
Visual Style: {brief_visual}
BGM Mood: {brief_bgm}

GENERATED SCRIPT:
{generated_script}

SEARCH TERMS USED:
{generated_terms}

VIDEO DURATION: {video_duration}s

Score alignment on 5 dimensions (0-100 each). Return ONLY valid JSON:

{{
  "topic_match": 85,
  "tone_match": 70,
  "structure_match": 80,
  "visual_match": 65,
  "overall": 75,
  "summary": "The script captures the core topic but the tone is more casual than the brief intended. Visual keyword coverage is partial — missing the opening hook imagery.",
  "gaps": ["tone is casual instead of urgent", "no keywords matching the opening hook scene"]
}}

Scoring guide:
- topic_match: Does the script address the same subject/theme as the brief? (0-100)
- tone_match: Does the script's energy/persona/emotion match the brief? (0-100)
- structure_match: Does the narrative arc (hook→body→CTA) match the director's notes? (0-100)
- visual_match: Do the search terms cover the visual needs described in the brief? (0-100)
- overall: Weighted average. 90+ = excellent match. 70-89 = good match. 50-69 = partial match. <50 = mismatch.
- summary: 2-3 sentences. What worked, what didn't. Actionable.
- gaps: Concrete things missing from the generated output vs the brief.

Output ONLY the JSON object, no markdown, no explanation.""".format(
        brief_prompt=brief_prompt,
        brief_script_dir=brief_script_dir[:1500],
        brief_keywords=", ".join(brief_keywords) if brief_keywords else "(none)",
        brief_visual=brief_visual or "unspecified",
        brief_bgm=brief_bgm or "unspecified",
        generated_script=generated_script[:4000],
        generated_terms=", ".join(generated_terms) if generated_terms else "(none)",
        video_duration="{:.1f}".format(video_duration) if video_duration else "unknown",
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
        # Clamp scores
        for key in ("overall", "topic_match", "tone_match", "structure_match", "visual_match"):
            if key in result:
                result[key] = max(0, min(100, int(result[key])))
        result.setdefault("summary", "")
        result.setdefault("gaps", [])
        logger.info("[VideoAnalyzer] alignment overall={}, gaps={}".format(
            result.get("overall", "?"),
            len(result.get("gaps", [])),
        ))
        return result
    except Exception as exc:
        logger.error("[VideoAnalyzer] alignment scoring failed: {}".format(exc))
        return _empty_alignment()


def _empty_alignment() -> dict:
    return {
        "overall": 0,
        "topic_match": 0,
        "tone_match": 0,
        "structure_match": 0,
        "visual_match": 0,
        "summary": "",
        "gaps": [],
    }


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
