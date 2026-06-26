"""
AI Image Generation Service for MoneyPrinterTurbo

Generates scene-specific images for the ``video_source="ai_image"`` pipeline.
Uses Cloudflare Workers AI with FLUX.1-schnell — free, no GPU needed.
"""

import base64
import json
import os
from pathlib import Path
from typing import List, Optional

import requests
from loguru import logger

from app.config import config

# ─── Defaults ────────────────────────────────────────────────────────────────

DEFAULT_OUTPUT_DIR = "./comfyui_output"

_CF_MODEL = "@cf/black-forest-labs/flux-1-schnell"
_CF_WIDTH = 1024
_CF_HEIGHT = 1024

# Style suffix appended to every visual prompt for photorealistic output.
_STYLE_SUFFIX = (
    "Style: photorealistic, professional advertising photography, "
    "high quality, sharp focus, cinematic lighting."
)


# ══════════════════════════════════════════════════════════════════════════════
# Cloudflare Workers AI (free, no credit card)
# ══════════════════════════════════════════════════════════════════════════════

class CloudflareImageGen:
    """Generates images via Cloudflare Workers AI (FLUX.1-schnell).

    Truly free: ~230 images/day, no credit card required.
    Uses plain REST — no SDK needed.
    """

    def __init__(
        self,
        account_id: str = "",
        api_token: str = "",
        model: str = "",
        timeout: int = 120,
    ):
        self.timeout = timeout
        self.model = model or _CF_MODEL
        self.account_id = account_id
        self.api_token = api_token
        self.output_dir = Path(
            config.app.get("comfyui_output_dir", "") or DEFAULT_OUTPUT_DIR
        ).resolve()
        os.makedirs(self.output_dir, exist_ok=True)

        if not self.account_id or not self.api_token:
            raise ValueError(
                "Cloudflare Account ID and API Token are required. "
                "Set cloudflare_account_id + cloudflare_api_token in [app] config, "
                "or CLOUDFLARE_ACCOUNT_ID + CLOUDFLARE_API_TOKEN env vars. "
                "Get them at https://dash.cloudflare.com/ → AI → Workers AI → Use REST API."
            )

        self._url = (
            f"https://api.cloudflare.com/client/v4/accounts/"
            f"{self.account_id}/ai/run/{self.model}"
        )

    def _try_generate(self, prompt: str) -> bytes:
        full_prompt = f"{prompt.strip()}\n\n{_STYLE_SUFFIX}"
        payload = {
            "prompt": full_prompt,
            "width": _CF_WIDTH,
            "height": _CF_HEIGHT,
        }
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

        logger.info(
            f"[Cloudflare] generating with {self.model} "
            f"({_CF_WIDTH}x{_CF_HEIGHT})"
        )
        resp = requests.post(self._url, json=payload, headers=headers, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()

        b64 = data.get("result", {}).get("image")
        if not b64:
            errors = data.get("errors", [])
            raise RuntimeError(
                f"Cloudflare AI returned no image. errors={errors}"
            )
        return base64.b64decode(b64)

    def generate(self, prompt: str, prefix: str = "mpt_scene") -> Path:
        image_bytes = self._try_generate(prompt)
        output_path = self.output_dir / f"{prefix}.png"
        output_path.write_bytes(image_bytes)
        logger.success(
            f"[Cloudflare] done: {output_path.name} "
            f"({output_path.stat().st_size / 1024:.0f} KB)"
        )
        return output_path

    def generate_scenes(
        self, scene_prompts: List[dict], prefix_base: str = "mpt_scene"
    ) -> List[Optional[Path]]:
        """Generate images for multiple scenes.

        A scene that fails produces ``None`` in its slot.
        """
        results: List[Optional[Path]] = []
        for scene in scene_prompts:
            idx = scene.get("index", len(results))
            prompt = scene.get("visual_prompt", scene.get("description", ""))
            prefix = f"{prefix_base}_{idx:02d}"
            try:
                path = self.generate(prompt=prompt, prefix=prefix)
                results.append(path)
            except Exception as e:
                logger.error(f"[ImageGen] scene {idx} failed: {e}")
                results.append(None)
        return results
