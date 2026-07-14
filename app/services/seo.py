"""
SEO Service for MoneyPrinterTurbo.

Keyword research, content optimization, platform-specific SEO strategies,
hashtag intelligence, and performance tracking — all LLM-powered, no external
API dependency.

Covers: TikTok, Instagram, YouTube Shorts, Facebook Reels, Pinterest, Web/Blog.

Integration points:
- ``task.py`` — keyword research runs after script generation
- ``campaign.py`` — ``generate_seo_keywords()`` delegates here
- ``dashboard.py`` — SEO panel displays keyword reports

Usage::

    from app.services.seo import research_keywords, generate_hashtags, score_content

    report = research_keywords("weight loss tea", seed_keywords=["diet", "slim"])
    for kw in report.keywords:
        print(f"{kw.keyword} — difficulty: {kw.difficulty}, volume: {kw.volume}")
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PLATFORM_SPECS: Dict[str, Dict[str, Any]] = {
    "tiktok": {
        "label": "TikTok",
        "hashtag_count": 5,
        "hashtag_strategy": "mix_trending_niche",
        "caption_max_chars": 2200,
        "title_max_chars": 100,
        "keyword_priority": ["trending", "challenge", "niche"],
        "description": "Short-form vertical video. Hashtags drive discovery more than captions.",
    },
    "instagram": {
        "label": "Instagram",
        "hashtag_count": 10,
        "hashtag_strategy": "ladder",
        "caption_max_chars": 2200,
        "title_max_chars": 125,
        "keyword_priority": ["broad", "medium", "niche"],
        "description": "Reels + feed posts. Hashtag ladder (3 broad + 4 medium + 3 niche) for max reach.",
    },
    "youtube_shorts": {
        "label": "YouTube Shorts",
        "hashtag_count": 3,
        "hashtag_strategy": "focused",
        "caption_max_chars": 5000,
        "title_max_chars": 100,
        "keyword_priority": ["search_optimized", "category", "branded"],
        "description": "Title is primary SEO surface. Description provides context for search indexing.",
    },
    "facebook_reels": {
        "label": "Facebook Reels",
        "hashtag_count": 5,
        "hashtag_strategy": "broad_focused",
        "caption_max_chars": 2200,
        "title_max_chars": 125,
        "keyword_priority": ["broad", "community", "niche"],
        "description": "Broader demographic. Mix trending + community hashtags.",
    },
    "pinterest": {
        "label": "Pinterest",
        "hashtag_count": 4,
        "hashtag_strategy": "search_focused",
        "caption_max_chars": 500,
        "title_max_chars": 100,
        "keyword_priority": ["search_optimized", "seasonal", "niche"],
        "description": "Visual search engine. Long-tail keywords in pin title + description critical.",
    },
    "web_blog": {
        "label": "Web / Blog",
        "hashtag_count": 0,
        "hashtag_strategy": "none",
        "caption_max_chars": 320,
        "title_max_chars": 70,
        "keyword_priority": ["primary", "secondary", "long_tail"],
        "description": "Google SEO. Title tag 50-70 chars, meta description 150-160 chars, H1/H2 structure.",
    },
}


class KeywordIntent(str, Enum):
    informational = "informational"
    commercial = "commercial"
    transactional = "transactional"
    navigational = "navigational"


class Difficulty(str, Enum):
    very_low = "very_low"
    low = "low"
    medium = "medium"
    high = "high"
    very_high = "very_high"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class SEOKeyword:
    """A single keyword with SEO metadata."""

    keyword: str
    volume_estimate: int = 0  # Monthly search volume (LLM-estimated)
    difficulty: Difficulty = Difficulty.medium
    intent: KeywordIntent = KeywordIntent.informational
    cpc_estimate: float = 0.0  # Estimated CPC in USD
    trend: str = "stable"  # rising | stable | declining | seasonal
    seasonality: Optional[str] = None  # e.g. "Q4 holiday", "summer"
    platforms: List[str] = field(default_factory=list)  # Best platforms for this keyword
    parent_topic: Optional[str] = None  # Broader topic this falls under


@dataclass
class SEOKeywordGroup:
    """Themed group of related keywords."""

    theme: str  # e.g. "fat burning", "metabolism", "weight loss motivation"
    keywords: List[SEOKeyword] = field(default_factory=list)
    total_volume: int = 0
    avg_difficulty: Difficulty = Difficulty.medium


@dataclass
class PlatformSEO:
    """Platform-specific SEO recommendations."""

    platform: str
    label: str
    title: str = ""
    description: str = ""
    hashtags: List[str] = field(default_factory=list)
    alt_text: str = ""  # Image alt text (Instagram, Pinterest)
    url_slug: str = ""  # Web/blog
    meta_description: str = ""  # Web/blog
    recommended_posting_time: str = ""
    strategy_notes: str = ""


@dataclass
class ContentScore:
    """Content optimization score against target keywords."""

    overall: float = 0.0  # 0-100
    keyword_density: float = 0.0  # percentage
    title_score: float = 0.0  # 0-100
    description_score: float = 0.0  # 0-100
    readability: float = 0.0  # 0-100
    missing_keywords: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


@dataclass
class SEOReport:
    """Full keyword research report."""

    topic: str
    generated_at: str = ""
    seed_keywords: List[str] = field(default_factory=list)
    keywords: List[SEOKeyword] = field(default_factory=list)
    groups: List[SEOKeywordGroup] = field(default_factory=list)
    negative_keywords: List[str] = field(default_factory=list)
    platform_seo: List[PlatformSEO] = field(default_factory=list)
    trending_topics: List[str] = field(default_factory=list)
    content_score: Optional[ContentScore] = None
    raw_response: str = ""  # For debugging


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _call_llm(prompt: str, temperature: float = 0.7) -> str:
    """Call the LLM via the existing llm service. Returns raw text."""
    from app.services.llm import _generate_response

    return _generate_response(prompt)


def _parse_json_response(raw: str) -> Dict[str, Any]:
    """Extract JSON from an LLM response that may contain markdown fences."""
    # Try to find a JSON block
    json_match = re.search(r"\{[\s\S]*\}", raw)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    # Try to find a JSON array
    arr_match = re.search(r"\[[\s\S]*\]", raw)
    if arr_match:
        try:
            parsed = json.loads(arr_match.group(0))
            if isinstance(parsed, list):
                return {"items": parsed}
        except json.JSONDecodeError:
            pass

    logger.warning(f"[SEO] failed to parse JSON from LLM response: {raw[:200]}")
    return {}


def _estimate_difficulty(
    volume: int, competition_hint: str = ""
) -> Difficulty:
    """Map volume + competition hint to a difficulty level."""
    hint_lower = (competition_hint or "").lower()
    if "very high" in hint_lower or volume > 100000:
        return Difficulty.very_high
    if "high" in hint_lower or volume > 50000:
        return Difficulty.high
    if "medium" in hint_lower or volume > 10000:
        return Difficulty.medium
    if "low" in hint_lower or volume > 1000:
        return Difficulty.low
    return Difficulty.very_low


# ---------------------------------------------------------------------------
# Core: Keyword Research
# ---------------------------------------------------------------------------


def research_keywords(
    topic: str,
    seed_keywords: Optional[List[str]] = None,
    platform: str = "tiktok",
    count: int = 15,
    language: str = "en",
    negative_keywords: Optional[List[str]] = None,
    campaign_category: str = "",
) -> SEOReport:
    """Research SEO keywords for a video topic.

    Uses LLM to expand seed keywords into long-tail variants with volume
    estimates, difficulty, intent classification, and platform recommendations.

    Args:
        topic: The video/product subject (e.g. "weight loss tea").
        seed_keywords: Known keywords to expand from.
        platform: Primary target platform.
        count: Number of keywords to generate.
        language: Target language for keywords.
        negative_keywords: Terms to exclude.
        campaign_category: B2C, B2B, NFT, NGO — tunes keyword intent mix.

    Returns:
        ``SEOReport`` with keywords, groups, and platform recommendations.
    """
    seed = seed_keywords or []
    negative = negative_keywords or []
    spec = _PLATFORM_SPECS.get(platform, _PLATFORM_SPECS["tiktok"])
    platform_label = spec["label"]

    # Build intent guidance based on campaign category
    intent_guidance = _intent_guidance_for_category(campaign_category)

    prompt = f"""You are a world-class SEO strategist specializing in {platform_label} content discovery.
Your task: research {count} high-value keywords for a video about:

TOPIC: {topic}
PLATFORM: {platform_label} ({spec['description']})
LANGUAGE: {language}
CATEGORY: {campaign_category or 'general'}
SEED KEYWORDS: {json.dumps(seed) if seed else 'none provided'}
NEGATIVE KEYWORDS (exclude these): {json.dumps(negative) if negative else 'none'}

INTENT GUIDANCE:
{intent_guidance}

Return a JSON object with exactly this structure:
{{
  "keywords": [
    {{
      "keyword": "exact search phrase",
      "volume_estimate": 0,
      "difficulty_hint": "low|medium|high|very_high",
      "intent": "informational|commercial|transactional|navigational",
      "cpc_estimate": 0.0,
      "trend": "rising|stable|declining|seasonal",
      "seasonality": null or "Q4 holiday" etc,
      "best_platforms": ["tiktok", "instagram"],
      "parent_topic": "broader category"
    }}
  ],
  "groups": [
    {{
      "theme": "theme name e.g. fat burning",
      "keyword_indices": [0, 2, 5],
      "total_volume_estimate": 0
    }}
  ],
  "trending_topics": ["currently trending subtopic 1", "currently trending subtopic 2"],
  "strategy_notes": "1-2 sentence SEO strategy summary for this topic on {platform_label}"
}}

RULES:
1. volume_estimate = realistic monthly search volume (integer, 0-500000)
2. difficulty_hint based on how competitive this keyword is to rank for
3. 60% long-tail (3+ words), 30% medium-tail (2 words), 10% short-tail (1 word)
4. Keywords must be in {language}; use native speaker phrasing for {language}
5. Include question-based keywords ("how to...", "why does...", "what is...")
6. Include action keywords ("best X for Y", "X vs Y", "X review")
7. Exclude any keyword containing negative keyword terms
8. trending_topics = real currently-popular subtopics that a video could ride
9. Do NOT invent brand names or trademarked terms
10. Return ONLY the JSON object, no markdown, no explanation

Generate exactly {count} keywords."""

    logger.info(f"[SEO] researching {count} keywords for '{topic}' on {platform_label}")

    report = SEOReport(
        topic=topic,
        generated_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        seed_keywords=seed,
        negative_keywords=negative,
    )

    try:
        raw = _call_llm(prompt, temperature=0.6)
        report.raw_response = raw

        data = _parse_json_response(raw)
        if not data:
            logger.warning("[SEO] LLM returned unparseable response, using fallback")
            return _fallback_keyword_report(topic, seed, platform, count)

        # Parse keywords
        kw_list = data.get("keywords", [])
        if isinstance(kw_list, list):
            for item in kw_list:
                if not isinstance(item, dict):
                    continue
                kw_text = str(item.get("keyword", "")).strip().lower()
                if not kw_text:
                    continue
                # Filter negatives
                if any(n.lower() in kw_text for n in negative):
                    continue

                volume = int(item.get("volume_estimate", 0) or 0)
                diff = _estimate_difficulty(
                    volume, str(item.get("difficulty_hint", ""))
                )
                intent_str = str(item.get("intent", "informational")).lower()
                try:
                    intent = KeywordIntent(intent_str)
                except ValueError:
                    intent = KeywordIntent.informational

                report.keywords.append(
                    SEOKeyword(
                        keyword=kw_text,
                        volume_estimate=volume,
                        difficulty=diff,
                        intent=intent,
                        cpc_estimate=float(item.get("cpc_estimate", 0) or 0),
                        trend=str(item.get("trend", "stable")),
                        seasonality=item.get("seasonality"),
                        platforms=list(item.get("best_platforms", [platform])),
                        parent_topic=item.get("parent_topic"),
                    )
                )

        # Parse groups
        groups_data = data.get("groups", [])
        if isinstance(groups_data, list):
            for g in groups_data:
                if not isinstance(g, dict):
                    continue
                theme = str(g.get("theme", "")).strip()
                indices = g.get("keyword_indices", [])
                group_kws = []
                for idx in indices:
                    if isinstance(idx, int) and 0 <= idx < len(report.keywords):
                        group_kws.append(report.keywords[idx])
                if theme:
                    total_vol = sum(k.volume_estimate for k in group_kws)
                    diffs = [k.difficulty for k in group_kws]
                    avg_diff = (
                        max(diffs, key=lambda d: list(Difficulty).index(d))
                        if diffs
                        else Difficulty.medium
                    )
                    report.groups.append(
                        SEOKeywordGroup(
                            theme=theme,
                            keywords=group_kws,
                            total_volume=total_vol,
                            avg_difficulty=avg_diff,
                        )
                    )

        # Trending topics
        report.trending_topics = data.get("trending_topics", [])
        if isinstance(report.trending_topics, list):
            report.trending_topics = [
                str(t) for t in report.trending_topics if isinstance(t, str)
            ]

        logger.info(
            f"[SEO] research complete: {len(report.keywords)} keywords, "
            f"{len(report.groups)} groups, "
            f"{len(report.trending_topics)} trending topics"
        )

    except Exception as exc:
        logger.error(f"[SEO] keyword research failed: {exc}")
        return _fallback_keyword_report(topic, seed, platform, count)

    # If we got too few keywords, supplement with fallback
    if len(report.keywords) < max(5, count // 2):
        logger.warning(
            f"[SEO] only got {len(report.keywords)}/{count} keywords, supplementing"
        )
        fallback = _fallback_keyword_report(topic, seed, platform, count)
        existing = {k.keyword for k in report.keywords}
        for kw in fallback.keywords:
            if kw.keyword not in existing:
                report.keywords.append(kw)
                existing.add(kw.keyword)

    return report


def _intent_guidance_for_category(category: str) -> str:
    """Return intent mix guidance based on campaign category."""
    if category == "b2c":
        return (
            "- 40% commercial (product comparison, review, best X for Y)\n"
            "- 30% transactional (buy, discount, deal, coupon)\n"
            "- 20% informational (how to, what is, why)\n"
            "- 10% navigational (brand/product names)"
        )
    elif category == "b2b":
        return (
            "- 40% informational (how to, guide, what is, why)\n"
            "- 35% commercial (comparison, review, best, top, vs)\n"
            "- 15% transactional (pricing, demo, trial, sign up)\n"
            "- 10% navigational (brand/software names)"
        )
    elif category == "nft":
        return (
            "- 30% informational (what is, how to, guide)\n"
            "- 30% commercial (best NFT, top projects, review)\n"
            "- 20% transactional (mint, buy, sell, trade)\n"
            "- 20% navigational (project names, marketplaces)"
        )
    elif category == "ngo":
        return (
            "- 35% informational (cause awareness, statistics, stories)\n"
            "- 30% transactional (donate, support, volunteer, sign petition)\n"
            "- 20% commercial (impact comparison, charity rating)\n"
            "- 15% navigational (organization names)"
        )
    return (
        "- 35% informational (how to, what is, why, guide)\n"
        "- 30% commercial (best, top, comparison, review, vs)\n"
        "- 25% transactional (buy, price, discount, deal)\n"
        "- 10% navigational (brand names)"
    )


def _fallback_keyword_report(
    topic: str,
    seed_keywords: List[str],
    platform: str,
    count: int,
) -> SEOReport:
    """Generate a simple keyword report without LLM, as fallback."""
    logger.info("[SEO] generating fallback keyword report")

    report = SEOReport(
        topic=topic,
        generated_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        seed_keywords=seed_keywords,
    )

    # Build simple long-tail variants from seed + topic modifiers
    modifiers = [
        "best", "top", "how to", "what is", "why", "review",
        "2026", "tips", "guide", "tutorial", "for beginners",
        "vs", "benefits", "results", "before and after",
        "easy", "fast", "natural", "effective",
    ]
    topic_words = topic.lower().split()
    used = set()

    # Seed keywords first
    for sk in seed_keywords:
        kw = sk.lower().strip()
        if kw and kw not in used:
            used.add(kw)
            report.keywords.append(
                SEOKeyword(
                    keyword=kw,
                    volume_estimate=5000,
                    difficulty=Difficulty.medium,
                    intent=KeywordIntent.commercial,
                    platforms=[platform],
                )
            )

    # Generate long-tail variants
    for modifier in modifiers:
        if len(report.keywords) >= count:
            break
        kw = f"{modifier} {topic}".lower().strip()
        if kw not in used:
            used.add(kw)
            report.keywords.append(
                SEOKeyword(
                    keyword=kw,
                    volume_estimate=2000,
                    difficulty=Difficulty.low,
                    intent=KeywordIntent.informational,
                    platforms=[platform],
                )
            )

    # Question variants
    question_prefixes = ["how to", "what is", "why does", "when to", "where to buy"]
    for prefix in question_prefixes:
        if len(report.keywords) >= count:
            break
        kw = f"{prefix} {topic}".lower().strip()
        if kw not in used:
            used.add(kw)
            report.keywords.append(
                SEOKeyword(
                    keyword=kw,
                    volume_estimate=3000,
                    difficulty=Difficulty.low,
                    intent=KeywordIntent.informational,
                    platforms=[platform],
                )
            )

    return report


# ---------------------------------------------------------------------------
# Hashtag Generation
# ---------------------------------------------------------------------------


def generate_hashtags(
    topic: str,
    platform: str = "tiktok",
    keywords: Optional[List[str]] = None,
    count: Optional[int] = None,
    strategy: str = "mix",
) -> List[str]:
    """Generate platform-optimized hashtags for a video.

    Args:
        topic: Video subject.
        platform: Target platform (tiktok, instagram, youtube_shorts, etc.).
        keywords: Optional SEO keywords to incorporate.
        count: Number of hashtags. Uses platform default if None.
        strategy: "mix" (trending + niche), "ladder" (broad → niche),
                  "focused" (niche only), "trending" (trending only).

    Returns:
        List of hashtag strings (with # prefix).
    """
    spec = _PLATFORM_SPECS.get(platform, _PLATFORM_SPECS["tiktok"])
    platform_label = spec["label"]
    n = count or spec["hashtag_count"]

    if n <= 0:
        return []

    _strategies = {
        "mix": "Mix trending/high-volume hashtags with niche-specific ones. "
               "2-3 broad trending + 2-3 niche.",
        "ladder": "Hashtag ladder: 30% broad (1M+ posts), 40% medium (100K-1M), "
                  "30% niche (<100K). Maximizes reach across audience sizes.",
        "focused": "Niche-specific hashtags only. Target engaged community, "
                   "not broad reach. Good for B2B and specialized content.",
        "trending": "Trending/popular hashtags only. Ride current trends. "
                    "Good for entertainment and viral content.",
    }
    strategy_desc = _strategies.get(strategy, _strategies["mix"])

    prompt = f"""You are a social media hashtag expert for {platform_label}.

TOPIC: {topic}
PLATFORM: {platform_label}
HASHTAG COUNT: {n}
STRATEGY: {strategy_desc}
REFERENCE KEYWORDS: {json.dumps(keywords or [])}

Return a JSON object:
{{
  "hashtags": ["#example1", "#example2", ...]
}}

RULES:
1. Return exactly {n} hashtags
2. Each must start with "#", contain no spaces, use CamelCase or lowercase
3. Mix sizes: some with 1M+ posts, some with 10K-500K, some niche <10K
4. Include at least one community/niche hashtag specific to the topic
5. No banned/hidden hashtags (no #follow4follow, #like4like, NSFW, etc.)
6. Hashtags must be relevant to the actual topic
7. Include one branded-style hashtag that a creator could "own"
8. Return ONLY the JSON object."""

    try:
        raw = _call_llm(prompt, temperature=0.8)
        data = _parse_json_response(raw)
        hashtags = data.get("hashtags", [])

        if isinstance(hashtags, list) and len(hashtags) > 0:
            # Normalize
            result = []
            for h in hashtags:
                h_str = str(h).strip()
                if not h_str.startswith("#"):
                    h_str = f"#{h_str}"
                # Remove spaces and special chars
                h_str = re.sub(r"[^\w#]", "", h_str)
                if h_str and h_str != "#":
                    result.append(h_str)
            return result[:n]
    except Exception as exc:
        logger.warning(f"[SEO] hashtag generation failed: {exc}")

    # Fallback: generate from topic + keywords
    return _fallback_hashtags(topic, keywords or [], n)


def _fallback_hashtags(topic: str, keywords: List[str], count: int) -> List[str]:
    """Generate simple hashtags from topic and keywords."""
    hashtags = []

    # From topic
    topic_tag = re.sub(r"[^\w]", "", topic.replace(" ", ""))
    if topic_tag:
        hashtags.append(f"#{topic_tag}")

    # From keywords
    for kw in keywords:
        tag = re.sub(r"[^\w]", "", kw.replace(" ", ""))
        if tag and f"#{tag}" not in hashtags:
            hashtags.append(f"#{tag}")
        if len(hashtags) >= count:
            break

    # Generic platform-specific fallbacks
    generic = ["#viral", "#fyp", "#trending", "#content", "#explore"]
    for g in generic:
        if len(hashtags) >= count:
            break
        if g not in hashtags:
            hashtags.append(g)

    return hashtags[:count]


# ---------------------------------------------------------------------------
# Title & Description Optimization
# ---------------------------------------------------------------------------


def generate_seo_title(
    topic: str,
    keywords: Optional[List[str]] = None,
    platform: str = "tiktok",
    max_chars: Optional[int] = None,
    style: str = "engaging",
) -> str:
    """Generate an SEO-optimized title incorporating target keywords.

    Args:
        topic: Video subject.
        keywords: Target keywords to incorporate.
        platform: Platform to optimize for.
        max_chars: Max title length. Uses platform default if None.
        style: "engaging" (click-worthy), "informative" (search-optimized),
               "curious" (curiosity gap), "urgent" (FOMO/scarcity).

    Returns:
        Optimized title string.
    """
    spec = _PLATFORM_SPECS.get(platform, _PLATFORM_SPECS["tiktok"])
    max_len = max_chars or spec["title_max_chars"]
    platform_label = spec["label"]

    _styles = {
        "engaging": "Emotionally compelling, uses power words, promises value "
                     "(e.g., 'You Won't Believe This Weight Loss Trick')",
        "informative": "Search-optimized, directly answers a query, uses "
                        "primary keyword near the start (e.g., 'How to Lose "
                        "Belly Fat: 5 Science-Backed Tips')",
        "curious": "Creates curiosity gap, makes viewer need to watch "
                   "(e.g., 'I Tried Every Fat Burner — #3 Shocked Me')",
        "urgent": "Creates urgency/FOMO, limited-time framing "
                  "(e.g., 'LAST CHANCE: 50% Off Weight Loss Deal')",
    }
    style_desc = _styles.get(style, _styles["engaging"])

    prompt = f"""You are an SEO copywriting expert for {platform_label}.

Generate ONE optimized title for a video about:
TOPIC: {topic}
PLATFORM: {platform_label}
MAX LENGTH: {max_len} characters
STYLE: {style_desc}
TARGET KEYWORDS (incorporate 1-2 naturally): {json.dumps(keywords or [])}

Return JSON:
{{"title": "The optimized title string"}}

RULES:
1. Primary keyword near the beginning if possible
2. Under {max_len} characters ABSOLUTELY — count carefully
3. No clickbait that misleads — promise must be deliverable
4. Use power words: ultimate, proven, secret, shocking, exclusive, etc.
5. For {platform_label}: {'use short, punchy titles' if platform in ('tiktok', 'instagram') else 'use descriptive, search-friendly titles'}
6. Return ONLY the JSON object."""

    try:
        raw = _call_llm(prompt, temperature=0.8)
        data = _parse_json_response(raw)
        title = str(data.get("title", "")).strip()
        if title:
            return title[:max_len]
    except Exception as exc:
        logger.warning(f"[SEO] title generation failed: {exc}")

    # Fallback
    return topic[:max_len]


def generate_seo_description(
    topic: str,
    script: str = "",
    keywords: Optional[List[str]] = None,
    platform: str = "tiktok",
    max_chars: Optional[int] = None,
    include_cta: str = "",
) -> str:
    """Generate an SEO-optimized description/caption.

    Args:
        topic: Video subject.
        script: The video script (used to extract key points).
        keywords: Target keywords to incorporate.
        platform: Target platform.
        max_chars: Max description length.
        include_cta: Optional CTA to append (e.g., "Link in bio!").

    Returns:
        Optimized description string.
    """
    spec = _PLATFORM_SPECS.get(platform, _PLATFORM_SPECS["tiktok"])
    max_len = max_chars or min(spec["caption_max_chars"], 500)
    platform_label = spec["label"]

    script_excerpt = script[:300] if script else "(no script provided)"

    prompt = f"""You are a social media copywriter optimizing for {platform_label} SEO.

Generate an engaging video description/caption for:
TOPIC: {topic}
PLATFORM: {platform_label}
MAX LENGTH: {max_len} characters
TARGET KEYWORDS: {json.dumps(keywords or [])}
CTA: {include_cta or 'none'}
SCRIPT EXCERPT: {script_excerpt}

Return JSON:
{{"description": "The optimized description text"}}

RULES:
1. First line is the hook — most visible in feeds
2. Naturally incorporate 2-3 keywords (don't keyword-stuff)
3. Use line breaks for readability
4. Include a call-to-action at the end{f' — specifically: {include_cta}' if include_cta else ''}
5. For {platform_label}: {'emojis OK, keep it casual and engaging' if platform in ('tiktok', 'instagram') else 'professional tone, emojis sparingly'}
6. Under {max_len} characters — count carefully
7. Return ONLY the JSON object."""

    try:
        raw = _call_llm(prompt, temperature=0.7)
        data = _parse_json_response(raw)
        desc = str(data.get("description", "")).strip()
        if desc:
            return desc[:max_len]
    except Exception as exc:
        logger.warning(f"[SEO] description generation failed: {exc}")

    # Fallback
    kw_str = " ".join(keywords[:3]) if keywords else topic
    return f"{topic}\n\nLearn more about {kw_str}. Follow for more!{chr(10) + include_cta if include_cta else ''}"[
        :max_len
    ]


# ---------------------------------------------------------------------------
# Content Scoring
# ---------------------------------------------------------------------------


def score_content(
    title: str = "",
    description: str = "",
    script: str = "",
    target_keywords: Optional[List[str]] = None,
    platform: str = "tiktok",
) -> ContentScore:
    """Score content optimization against target keywords.

    Checks keyword density, placement, readability, and gives
    actionable improvement suggestions.

    Args:
        title: Video title or headline.
        description: Caption or meta description.
        script: Full script/text content.
        target_keywords: Keywords the content should rank for.
        platform: Platform context for scoring weights.

    Returns:
        ``ContentScore`` with detailed breakdown and suggestions.
    """
    keywords = target_keywords or []
    spec = _PLATFORM_SPECS.get(platform, _PLATFORM_SPECS["tiktok"])

    content_lower = f"{title} {description} {script}".lower()
    word_count = len(content_lower.split())

    score = ContentScore()

    if not keywords or word_count < 10:
        score.overall = 50.0
        score.suggestions = ["Add target keywords to analyze content optimization."]
        return score

    # 1. Keyword density
    found_count = 0
    missing = []
    for kw in keywords:
        kw_lower = kw.lower()
        occurrences = content_lower.count(kw_lower)
        if occurrences > 0:
            found_count += 1
        else:
            missing.append(kw)

    density = (found_count / len(keywords)) * 100 if keywords else 0
    score.keyword_density = round(density, 1)
    score.missing_keywords = missing

    # 2. Title score
    title_lower = title.lower()
    title_kw_found = sum(
        1 for kw in keywords if kw.lower() in title_lower
    )
    title_has_primary = title_kw_found > 0
    title_length_ok = (
        10 < len(title) <= spec["title_max_chars"]
    )
    title_has_number = bool(re.search(r"\d", title))
    title_has_power = bool(
        re.search(
            r"ultimate|proven|secret|best|top|essential|complete|"
            r"shocking|exclusive|free|guaranteed|instant",
            title_lower,
        )
    )
    score.title_score = round(
        (title_has_primary * 40)
        + (title_length_ok * 25)
        + (title_has_number * 15)
        + (title_has_power * 20)
    )

    # 3. Description score
    desc_lower = description.lower()
    desc_kw_found = sum(
        1 for kw in keywords if kw.lower() in desc_lower
    )
    desc_has_cta = bool(
        re.search(
            r"link in bio|click|tap|follow|subscribe|comment|share|save|"
            r"shop now|learn more|sign up|get started|try free",
            desc_lower,
        )
    )
    desc_length_ok = 20 < len(description) <= spec["caption_max_chars"]
    score.description_score = round(
        (min(desc_kw_found, 5) / 5 * 50)
        + (desc_has_cta * 25)
        + (desc_length_ok * 25)
    )

    # 4. Readability (simplified Flesch-like heuristic)
    sentences = re.split(r"[.!?]+", script) if script else [title]
    avg_words_per_sentence = (
        sum(len(s.split()) for s in sentences if s.strip()) / max(len(sentences), 1)
    )
    readability_ok = 8 <= avg_words_per_sentence <= 25
    score.readability = 100 if readability_ok else max(0, 100 - abs(avg_words_per_sentence - 15) * 4)

    # 5. Overall
    score.overall = round(
        (score.title_score * 0.25)
        + (score.description_score * 0.25)
        + (density * 0.35)
        + (score.readability * 0.15)
    )

    # 6. Suggestions
    if title_has_primary and not title_has_number:
        score.suggestions.append(
            "Add a number to the title (e.g., '5 Ways to...') for higher CTR."
        )
    if not title_has_primary:
        score.suggestions.append(
            f"Include primary keyword '{keywords[0]}' in the title."
        )
    if not desc_has_cta:
        score.suggestions.append(
            "Add a call-to-action in the description (e.g., 'Link in bio!')."
        )
    if missing:
        score.suggestions.append(
            f"Incorporate missing keywords: {', '.join(missing[:3])}"
        )
    if avg_words_per_sentence > 25:
        score.suggestions.append(
            f"Sentences too long (avg {avg_words_per_sentence:.0f} words). "
            "Shorten for better readability on mobile."
        )
    if not score.suggestions:
        score.suggestions.append("Content is well-optimized! ✅")

    return score


# ---------------------------------------------------------------------------
# Platform SEO Generation
# ---------------------------------------------------------------------------


def generate_platform_seo(
    topic: str,
    script: str = "",
    seed_keywords: Optional[List[str]] = None,
    platforms: Optional[List[str]] = None,
    include_cta: str = "",
) -> List[PlatformSEO]:
    """Generate full platform-specific SEO packages for multiple platforms.

    For each platform: optimized title, description, hashtags, alt text,
    and posting time recommendation.

    Args:
        topic: Video subject.
        script: Video script for context.
        seed_keywords: Base keywords to optimize around.
        platforms: List of platform keys. Default: tiktok + instagram.
        include_cta: CTA to include in descriptions.

    Returns:
        List of ``PlatformSEO``, one per platform.
    """
    target_platforms = platforms or ["tiktok", "instagram"]
    results = []

    for plat in target_platforms:
        spec = _PLATFORM_SPECS.get(plat, _PLATFORM_SPECS["tiktok"])

        # Research keywords for this platform
        report = research_keywords(
            topic=topic,
            seed_keywords=seed_keywords,
            platform=plat,
            count=8,
        )

        kw_strings = [k.keyword for k in report.keywords[:8]]

        # Generate platform-optimized title
        title = generate_seo_title(
            topic=topic,
            keywords=kw_strings[:3],
            platform=plat,
        )

        # Generate description
        description = generate_seo_description(
            topic=topic,
            script=script,
            keywords=kw_strings,
            platform=plat,
            include_cta=include_cta,
        )

        # Generate hashtags
        hashtags = generate_hashtags(
            topic=topic,
            platform=plat,
            keywords=kw_strings,
        )

        # Alt text for image-heavy platforms
        alt_text = ""
        if plat in ("instagram", "pinterest"):
            alt_text = f"Video about {topic}. {script[:100] if script else ''}"

        # URL slug for web
        url_slug = ""
        if plat == "web_blog":
            url_slug = re.sub(r"[^\w-]", "", topic.lower().replace(" ", "-"))[:60]

        # Meta description for web
        meta_description = ""
        if plat == "web_blog":
            meta_description = generate_seo_description(
                topic=topic,
                script=script,
                keywords=kw_strings,
                platform=plat,
                max_chars=160,
            )

        # Best posting time
        posting_time = _recommend_posting_time(plat)

        results.append(
            PlatformSEO(
                platform=plat,
                label=spec["label"],
                title=title,
                description=description,
                hashtags=hashtags,
                alt_text=alt_text,
                url_slug=url_slug,
                meta_description=meta_description,
                recommended_posting_time=posting_time,
                strategy_notes=spec.get("description", ""),
            )
        )

    return results


def _recommend_posting_time(platform: str) -> str:
    """Return recommended posting time for a platform."""
    times = {
        "tiktok": "Tue/Thu 7-9 PM, Sat 10 AM-12 PM (EST)",
        "instagram": "Mon-Fri 11 AM-1 PM, Tue/Wed 7-9 PM (EST)",
        "youtube_shorts": "Thu/Fri 3-6 PM, Sat 9-11 AM (EST)",
        "facebook_reels": "Wed/Thu 1-4 PM, Sat 10 AM-12 PM (EST)",
        "pinterest": "Mon/Tue 8-10 PM, Sat 2-4 PM (EST)",
        "web_blog": "Tue/Thu morning (for Google indexing cycle)",
    }
    return times.get(platform, "Weekdays 6-9 PM (EST)")


# ---------------------------------------------------------------------------
# Keyword Gap Analysis
# ---------------------------------------------------------------------------


def analyze_keyword_gap(
    our_keywords: List[str],
    competitor_topic: str,
    platform: str = "tiktok",
) -> List[SEOKeyword]:
    """Find keywords competitors likely use that we don't.

    Given our current keywords and a competitor topic/niche, use LLM to
    identify missed opportunities.

    Args:
        our_keywords: Keywords we already target.
        competitor_topic: What competitors are focusing on.
        platform: Target platform.

    Returns:
        List of ``SEOKeyword`` opportunities we should also target.
    """
    spec = _PLATFORM_SPECS.get(platform, _PLATFORM_SPECS["tiktok"])
    platform_label = spec["label"]

    prompt = f"""You are a competitive SEO analyst for {platform_label}.

OUR CURRENT KEYWORDS: {json.dumps(our_keywords)}
COMPETITOR FOCUS: {competitor_topic}
PLATFORM: {platform_label}

Identify 8 keyword opportunities that competitors are likely targeting
but we are missing. Focus on:
1. Adjacent topics we haven't covered
2. Long-tail variants we're missing
3. Question-based keywords competitors answer
4. Emerging/trending keywords in this space

Return JSON:
{{
  "gap_keywords": [
    {{
      "keyword": "keyword phrase",
      "volume_estimate": 0,
      "difficulty_hint": "low|medium|high|very_high",
      "intent": "informational|commercial|transactional|navigational",
      "gap_reason": "why competitors rank for this but we don't",
      "action": "how to target this keyword"
    }}
  ]
}}

RULES:
1. Keywords must be genuinely different from our current list
2. Explain WHY each is a gap (not just "we don't have it")
3. Suggest concrete action for each
4. Return ONLY the JSON object."""

    try:
        raw = _call_llm(prompt, temperature=0.6)
        data = _parse_json_response(raw)
        gap_kws = data.get("gap_keywords", [])

        result = []
        for item in gap_kws:
            if not isinstance(item, dict):
                continue
            kw_text = str(item.get("keyword", "")).strip().lower()
            if not kw_text or kw_text in {k.lower() for k in our_keywords}:
                continue

            volume = int(item.get("volume_estimate", 0) or 0)
            diff = _estimate_difficulty(
                volume, str(item.get("difficulty_hint", ""))
            )
            intent_str = str(item.get("intent", "informational")).lower()
            try:
                intent = KeywordIntent(intent_str)
            except ValueError:
                intent = KeywordIntent.informational

            result.append(
                SEOKeyword(
                    keyword=kw_text,
                    volume_estimate=volume,
                    difficulty=diff,
                    intent=intent,
                )
            )

        logger.info(f"[SEO] gap analysis found {len(result)} opportunities")
        return result

    except Exception as exc:
        logger.error(f"[SEO] gap analysis failed: {exc}")
        return []


# ---------------------------------------------------------------------------
# Export & Serialization
# ---------------------------------------------------------------------------


def export_keyword_report(report: SEOReport, format: str = "dict") -> Dict[str, Any]:
    """Export a keyword report as a dictionary for JSON serialization.

    Args:
        report: The ``SEOReport`` to export.
        format: Output format — "dict" only for now.

    Returns:
        JSON-serializable dict.
    """
    return {
        "topic": report.topic,
        "generated_at": report.generated_at,
        "seed_keywords": report.seed_keywords,
        "negative_keywords": report.negative_keywords,
        "trending_topics": report.trending_topics,
        "keywords": [
            {
                "keyword": k.keyword,
                "volume_estimate": k.volume_estimate,
                "difficulty": k.difficulty.value,
                "intent": k.intent.value,
                "cpc_estimate": k.cpc_estimate,
                "trend": k.trend,
                "seasonality": k.seasonality,
                "platforms": k.platforms,
                "parent_topic": k.parent_topic,
            }
            for k in report.keywords
        ],
        "groups": [
            {
                "theme": g.theme,
                "keywords": [k.keyword for k in g.keywords],
                "total_volume": g.total_volume,
                "avg_difficulty": g.avg_difficulty.value,
            }
            for g in report.groups
        ],
        "platform_seo": [
            {
                "platform": p.platform,
                "label": p.label,
                "title": p.title,
                "description": p.description,
                "hashtags": p.hashtags,
                "alt_text": p.alt_text,
                "url_slug": p.url_slug,
                "meta_description": p.meta_description,
                "recommended_posting_time": p.recommended_posting_time,
                "strategy_notes": p.strategy_notes,
            }
            for p in report.platform_seo
        ],
    }


def save_seo_report(report: SEOReport, task_dir: Path) -> Path:
    """Save an SEO report to a task directory as seo_report.json.

    Args:
        report: The report to save.
        task_dir: Task output directory.

    Returns:
        Path to the saved file.
    """
    task_dir = Path(task_dir)
    task_dir.mkdir(parents=True, exist_ok=True)

    output_path = task_dir / "seo_report.json"
    data = export_keyword_report(report)
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    logger.info(f"[SEO] report saved to {output_path}")
    return output_path


def load_seo_report(task_dir: Path) -> Optional[SEOReport]:
    """Load a previously saved SEO report from a task directory.

    Args:
        task_dir: Task directory to load from.

    Returns:
        ``SEOReport`` if found, ``None`` otherwise.
    """
    path = Path(task_dir) / "seo_report.json"
    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        report = SEOReport(
            topic=data.get("topic", ""),
            generated_at=data.get("generated_at", ""),
            seed_keywords=data.get("seed_keywords", []),
            negative_keywords=data.get("negative_keywords", []),
            trending_topics=data.get("trending_topics", []),
        )
        for kd in data.get("keywords", []):
            report.keywords.append(
                SEOKeyword(
                    keyword=kd.get("keyword", ""),
                    volume_estimate=kd.get("volume_estimate", 0),
                    difficulty=Difficulty(kd.get("difficulty", "medium")),
                    intent=KeywordIntent(kd.get("intent", "informational")),
                    cpc_estimate=kd.get("cpc_estimate", 0.0),
                    trend=kd.get("trend", "stable"),
                    seasonality=kd.get("seasonality"),
                    platforms=kd.get("platforms", []),
                    parent_topic=kd.get("parent_topic"),
                )
            )
        # Restore groups
        for gd in data.get("groups", []):
            group_kws = []
            for kw_name in gd.get("keywords", []):
                for k in report.keywords:
                    if k.keyword == kw_name:
                        group_kws.append(k)
                        break
            if group_kws:
                total_vol = sum(k.volume_estimate for k in group_kws)
                diffs = [k.difficulty for k in group_kws]
                avg_diff = (
                    max(diffs, key=lambda d: list(Difficulty).index(d))
                    if diffs
                    else Difficulty.medium
                )
                report.groups.append(
                    SEOKeywordGroup(
                        theme=gd.get("theme", ""),
                        keywords=group_kws,
                        total_volume=total_vol or gd.get("total_volume", 0),
                        avg_difficulty=avg_diff,
                    )
                )
        # Restore platform SEO
        for pd in data.get("platform_seo", []):
            report.platform_seo.append(
                PlatformSEO(
                    platform=pd.get("platform", ""),
                    label=pd.get("label", ""),
                    title=pd.get("title", ""),
                    description=pd.get("description", ""),
                    hashtags=pd.get("hashtags", []),
                    alt_text=pd.get("alt_text", ""),
                    url_slug=pd.get("url_slug", ""),
                    meta_description=pd.get("meta_description", ""),
                    recommended_posting_time=pd.get("recommended_posting_time", ""),
                    strategy_notes=pd.get("strategy_notes", ""),
                )
            )
        return report
    except Exception as exc:
        logger.warning(f"[SEO] failed to load report from {path}: {exc}")
        return None


# ---------------------------------------------------------------------------
# Quick Access: Full SEO Workflow
# ---------------------------------------------------------------------------


def run_seo_workflow(
    topic: str,
    script: str = "",
    seed_keywords: Optional[List[str]] = None,
    negative_keywords: Optional[List[str]] = None,
    platforms: Optional[List[str]] = None,
    campaign_category: str = "",
    primary_platform: str = "tiktok",
) -> SEOReport:
    """Run the full SEO workflow: research + platform optimization + scoring.

    This is the main entry point called from ``task.py``. It:
    1. Researches keywords for the primary platform
    2. Generates platform-specific SEO packages
    3. Scores the content against target keywords
    4. Saves everything to the task directory

    Args:
        topic: Video subject.
        script: Generated video script.
        seed_keywords: Template seed keywords.
        negative_keywords: Keywords to exclude.
        platforms: Platforms to generate SEO for.
        campaign_category: B2C/B2B/NFT/NGO.
        primary_platform: Primary target platform for keyword research.

    Returns:
        ``SEOReport`` with full keyword research + platform recommendations.
    """
    target_platforms = platforms or ["tiktok", "instagram"]

    logger.info(
        f"[SEO] workflow started for '{topic}' "
        f"(primary={primary_platform}, platforms={target_platforms})"
    )

    # Step 1: Keyword research
    report = research_keywords(
        topic=topic,
        seed_keywords=seed_keywords,
        platform=primary_platform,
        count=15,
        negative_keywords=negative_keywords,
        campaign_category=campaign_category,
    )

    # Step 2: Platform-specific SEO for all target platforms
    kw_strings = [k.keyword for k in report.keywords[:10]]
    report.platform_seo = generate_platform_seo(
        topic=topic,
        script=script,
        seed_keywords=kw_strings,
        platforms=target_platforms,
    )

    # Step 3: Score content if we have a script
    if script:
        primary_ps = report.platform_seo[0] if report.platform_seo else None
        if primary_ps:
            report.content_score = score_content(
                title=primary_ps.title,
                description=primary_ps.description,
                script=script,
                target_keywords=kw_strings[:5],
                platform=primary_platform,
            )

    logger.info(
        f"[SEO] workflow complete: {len(report.keywords)} keywords, "
        f"{len(report.platform_seo)} platform packages, "
        f"content score: {report.content_score.overall if report.content_score else 'N/A'}"
    )

    return report
