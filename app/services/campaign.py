"""
Campaign Template Service for MoneyPrinterTurbo.

Loads, validates, and merges campaign templates into the video generation pipeline.
Each template defines LLM prompts, visual style, voice, BGM, keywords, platforms,
CTA, and analytics goals for a specific campaign type (B2C, B2B, NFT, NGO).
"""

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "campaigns"
_TEMPLATE_MAP = {
    "b2c_weight_loss": "b2c_weight_loss.json",
    "b2b_saas": "b2b_saas.json",
    "nft_metaverse": "nft_metaverse.json",
    "ngo_fundraising": "ngo_fundraising.json",
}


def _load_schema() -> Optional[Dict]:
    """Load the JSON Schema for template validation."""
    schema_path = _TEMPLATE_DIR / "_schema.json"
    if not schema_path.exists():
        logger.warning("[Campaign] schema file not found — skip validation")
        return None
    try:
        return json.loads(schema_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning(f"[Campaign] failed to load schema: {exc}")
        return None


def validate_template(template: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validate a template against the JSON Schema.

    Args:
        template: Loaded template dict.

    Returns:
        (is_valid, error_message).  ``error_message`` is None when valid.
    """
    schema = _load_schema()
    if schema is None:
        return True, None  # No schema → skip validation

    try:
        import jsonschema
    except ImportError:
        logger.debug("[Campaign] jsonschema not installed — skip validation")
        return True, None

    try:
        jsonschema.validate(template, schema)
        return True, None
    except jsonschema.ValidationError as exc:
        return False, str(exc)


def load_campaign_template(template_id: str) -> Optional[Dict[str, Any]]:
    """Load a campaign template by its ID.

    Args:
        template_id: One of ``b2c_weight_loss``, ``b2b_saas``,
            ``nft_metaverse``, ``ngo_fundraising``.

    Returns:
        Template dict on success, ``None`` if not found or invalid.
    """
    if not template_id or template_id not in _TEMPLATE_MAP:
        logger.warning(f"[Campaign] unknown template id: {template_id}")
        return None

    template_path = _TEMPLATE_DIR / _TEMPLATE_MAP[template_id]
    if not template_path.exists():
        logger.error(f"[Campaign] template file not found: {template_path}")
        return None

    try:
        template = json.loads(template_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.error(f"[Campaign] failed to parse template {template_id}: {exc}")
        return None

    is_valid, error = validate_template(template)
    if not is_valid:
        logger.error(f"[Campaign] template {template_id} validation failed: {error}")
        return None

    logger.info(f"[Campaign] loaded template: {template['name']} v{template['version']}")
    return template


def list_templates() -> List[Dict[str, Any]]:
    """List all available campaign templates with metadata.

    Returns:
        List of dicts with keys: ``id``, ``name``, ``version``,
        ``category``, ``description``, ``icon``, ``color``.
    """
    templates = []
    for template_id, filename in _TEMPLATE_MAP.items():
        path = _TEMPLATE_DIR / filename
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            templates.append({
                "id": template_id,
                "name": data.get("name", template_id),
                "version": data.get("version", "?"),
                "category": data.get("category", "?"),
                "description": data.get("description", ""),
                "icon": data.get("icon", "📋"),
                "color": data.get("color", "#666666"),
            })
        except Exception as exc:
            logger.warning(f"[Campaign] failed to read {filename}: {exc}")
    return templates


def merge_template_params(
    template: Dict[str, Any],
    params: Any,
) -> Any:
    """Merge template defaults into VideoParams.

    Template values are defaults — user-supplied values take precedence.
    Only merges fields the user hasn't explicitly set.

    Args:
        template: Loaded campaign template dict.
        params: Existing ``VideoParams`` object.

    Returns:
        Updated ``VideoParams`` with template defaults applied.
    """
    params = deepcopy(params)

    # ── LLM ──
    llm = template.get("llm", {})
    if llm.get("system_prompt") and not params.custom_system_prompt:
        params.custom_system_prompt = llm["system_prompt"]
    if llm.get("script_direction") and not params.video_script_prompt:
        params.video_script_prompt = llm["script_direction"]
    if llm.get("max_paragraphs") and params.paragraph_number == 1:
        params.paragraph_number = llm["max_paragraphs"]
    if llm.get("language") and not params.video_language:
        params.video_language = llm["language"]

    # ── Voice ──
    voice = template.get("voice", {})
    if voice.get("preset") and not params.voice_name:
        params.voice_name = voice["preset"]
    if voice.get("rate") and params.voice_rate == 1.0:
        params.voice_rate = voice["rate"]
    if voice.get("volume") and params.voice_volume == 1.0:
        params.voice_volume = voice["volume"]

    # ── BGM ──
    bgm = template.get("bgm", {})
    if bgm.get("volume") and params.bgm_volume == 0.2:
        params.bgm_volume = bgm["volume"]

    # ── SEO Keywords ──
    keywords = template.get("keywords", {})
    if keywords.get("seed") and not params.seo_keywords:
        params.seo_keywords = keywords["seed"]

    logger.info(
        f"[Campaign] merged template '{template.get('name', '?')}' "
        f"into params: voice={params.voice_name}, "
        f"paragraphs={params.paragraph_number}, "
        f"seo_keywords={len(params.seo_keywords or [])}"
    )
    return params


def get_template_preview(template_id: str) -> Optional[Dict[str, Any]]:
    """Get a lightweight preview of a template for the dashboard.

    Returns subset of template fields useful for UI preview:
    ``name``, ``version``, ``description``, ``icon``, ``color``,
    ``tone``, ``voice_name``, ``bgm_mood``, ``cta``, ``hook_examples``.
    """
    template = load_campaign_template(template_id)
    if not template:
        return None

    return {
        "id": template_id,
        "name": template.get("name", ""),
        "version": template.get("version", ""),
        "description": template.get("description", ""),
        "icon": template.get("icon", "📋"),
        "color": template.get("color", "#666666"),
        "tone": template.get("llm", {}).get("tone", ""),
        "voice_name": template.get("voice", {}).get("preset", ""),
        "bgm_mood": template.get("bgm", {}).get("mood", ""),
        "cta": template.get("cta", {}).get("primary", ""),
        "hook_examples": template.get("hook_examples", [])[:3],
        "keywords": template.get("keywords", {}).get("seed", [])[:5],
    }


def generate_seo_keywords(
    template_id: str,
    video_subject: str = "",
    count: int = 10,
) -> List[str]:
    """Generate SEO-optimized keyword suggestions from template seed + subject.

    Delegates to ``app.services.seo`` for full keyword research (volume
    estimates, difficulty, intent classification), then returns just the
    keyword strings for backward compatibility.

    Args:
        template_id: Which template to pull seed keywords from.
        video_subject: Topic to contextualize keywords.
        count: Number of keywords to generate.

    Returns:
        List of SEO keyword strings.
    """
    template = load_campaign_template(template_id)
    if not template:
        return []

    keywords_cfg = template.get("keywords", {})
    seed = keywords_cfg.get("seed", [])
    negative = keywords_cfg.get("negative", [])
    long_tail = keywords_cfg.get("long_tail", [])
    campaign_category = template.get("category", "")

    try:
        from app.services import seo

        report = seo.research_keywords(
            topic=video_subject or " ".join(seed[:3]),
            seed_keywords=seed,
            platform="tiktok",
            count=count,
            negative_keywords=negative,
            campaign_category=campaign_category,
        )

        if report.keywords:
            kw_strings = [k.keyword for k in report.keywords[:count]]
            logger.info(
                f"[Campaign] SEO research returned {len(kw_strings)} keywords "
                f"for template '{template_id}'"
            )
            return kw_strings
    except Exception as exc:
        logger.warning(f"[Campaign] SEO module failed, using fallback: {exc}")

    # Fallback: static expansion from template
    candidates = list(long_tail) if long_tail else list(seed)

    if video_subject and len(candidates) < count:
        try:
            from app.services.llm import generate_terms

            extra = generate_terms(
                video_subject=video_subject,
                video_script="",
                amount=count - len(candidates),
                match_script_order=False,
            )
            if isinstance(extra, list):
                candidates.extend(extra)
        except Exception as exc:
            logger.warning(f"[Campaign] LLM fallback also failed: {exc}")

    # Filter out negative keywords
    if negative:
        candidates = [
            kw for kw in candidates
            if not any(n.lower() in kw.lower() for n in negative)
        ]

    return candidates[:count]
