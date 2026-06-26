"""
AI Image Generation Service for MoneyPrinterTurbo

Generates scene-specific images for the ``video_source="ai_image"`` pipeline.
Supports two backends:

- **comfyui** — local ComfyUI with Flux.1-dev (free, requires GPU)
- **openrouter** — OpenRouter API with FLUX.2 Pro (no GPU, ~$0.04/image)
"""

import base64
import json
import os
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import List, Optional

from loguru import logger

from app.config import config

# ─── ComfyUI defaults ────────────────────────────────────────────────────────

COMFYUI_URL = "http://localhost:8188"
DEFAULT_OUTPUT_DIR = "./comfyui_output"

UNET_NAME = "flux1-dev-fp8.safetensors"
CLIP_NAME1 = "clip_l.safetensors"
CLIP_NAME2 = "t5xxl_fp8.safetensors"
VAE_NAME = "flux1-vae.safetensors"
NEGATIVE_PROMPT = (
    "blurry, noisy, low quality, distorted, ugly, bad anatomy, "
    "extra limbs, watermark, signature, deformed, disfigured, "
    "poorly drawn, childish, amateur, pixelated, out of focus"
)

# ─── OpenRouter defaults ─────────────────────────────────────────────────────

_OPENROUTER_IMAGE_MODEL = "black-forest-labs/flux.2-pro"
_OPENROUTER_FALLBACK_MODEL = "black-forest-labs/flux.1-dev"
_OPENROUTER_IMAGE_WIDTH = 1792
_OPENROUTER_IMAGE_HEIGHT = 1024
_DEFAULT_PROVIDER = "comfyui"

# Style suffix appended to every visual prompt for photorealistic output.
_STYLE_SUFFIX = (
    "Style: photorealistic, professional advertising photography, "
    "high quality, sharp focus, cinematic lighting."
)


# ══════════════════════════════════════════════════════════════════════════════
# Provider factory
# ══════════════════════════════════════════════════════════════════════════════

def create_image_gen(
    provider: str = "",
    width: int = 540,
    height: int = 960,
) -> "ImageGenProvider":
    """Return the right image generator based on config or explicit provider.

    Reads ``ai_material_provider`` from ``[app]`` config; falls back to
    ``"comfyui"`` when not set.
    """
    provider = (provider or config.app.get("ai_material_provider", "") or _DEFAULT_PROVIDER).strip().lower()

    if provider == "openrouter":
        api_key = config.app.get("openrouter_api_key", "") or os.getenv("OPENROUTER_API_KEY", "")
        return OpenRouterImageGen(api_key=api_key, width=width, height=height)

    # Default: local ComfyUI
    return ComfyUIImageGen(width=width, height=height)


# ══════════════════════════════════════════════════════════════════════════════
# Base interface
# ══════════════════════════════════════════════════════════════════════════════

class ImageGenProvider:
    """Protocol that both ComfyUIImageGen and OpenRouterImageGen satisfy."""

    def generate(self, prompt: str, prefix: str = "mpt_scene") -> Path:
        raise NotImplementedError

    def generate_scenes(
        self, scene_prompts: List[dict], prefix_base: str = "mpt_scene"
    ) -> List[Optional[Path]]:
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


# ══════════════════════════════════════════════════════════════════════════════
# ComfyUI (local GPU)
# ══════════════════════════════════════════════════════════════════════════════

class ComfyUIImageGen(ImageGenProvider):
    """Generates images via a local ComfyUI API using Flux.1-dev."""

    def __init__(
        self,
        width: int = 540,
        height: int = 960,
        steps: int = 28,
        guidance: float = 3.5,
        seed: int = 42,
        timeout: int = 300,
    ):
        self.width = width
        self.height = height
        self.steps = steps
        self.guidance = guidance
        self.seed = seed
        self.timeout = timeout
        self.comfyui_url = config.app.get("comfyui_url", COMFYUI_URL)
        raw_dir = config.app.get("comfyui_output_dir", "") or DEFAULT_OUTPUT_DIR
        self.output_dir = Path(raw_dir).resolve()

    def _build_workflow(self, prompt: str, prefix: str, seed: int) -> dict:
        return {
            "1": {"class_type": "UNETLoader", "inputs": {"unet_name": UNET_NAME, "weight_dtype": "default"}},
            "2": {"class_type": "DualCLIPLoader", "inputs": {"clip_name1": CLIP_NAME1, "clip_name2": CLIP_NAME2, "type": "flux"}},
            "11": {"class_type": "VAELoader", "inputs": {"vae_name": VAE_NAME}},
            "3": {"class_type": "KSampler", "inputs": {"seed": seed, "steps": self.steps, "cfg": 1.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0, "model": ["1", 0], "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["5", 0]}},
            "5": {"class_type": "EmptyLatentImage", "inputs": {"width": self.width, "height": self.height, "batch_size": 1}},
            "6": {"class_type": "CLIPTextEncodeFlux", "inputs": {"clip": ["2", 0], "clip_l": prompt, "t5xxl": prompt, "guidance": self.guidance}},
            "7": {"class_type": "CLIPTextEncodeFlux", "inputs": {"clip": ["2", 0], "clip_l": NEGATIVE_PROMPT, "t5xxl": NEGATIVE_PROMPT, "guidance": self.guidance}},
            "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["11", 0]}},
            "9": {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": prefix}},
        }

    def _queue_prompt(self, workflow: dict) -> str:
        data = json.dumps({"prompt": workflow}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.comfyui_url}/prompt", data=data,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
        prompt_id = result.get("prompt_id")
        if not prompt_id:
            raise RuntimeError(f"ComfyUI returned no prompt_id: {result}")
        return prompt_id

    def _wait_for_completion(self, prompt_id: str) -> dict:
        start = time.time()
        while time.time() - start < self.timeout:
            try:
                req = urllib.request.Request(f"{self.comfyui_url}/history/{prompt_id}", method="GET")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    history = json.loads(resp.read())
                if prompt_id in history:
                    return history[prompt_id]
            except (urllib.error.URLError, ConnectionResetError, TimeoutError):
                logger.debug("[ImageGen] ComfyUI not ready, retrying...")
            except json.JSONDecodeError as e:
                logger.warning(f"[ImageGen] unparseable ComfyUI response: {e}")
            time.sleep(3)
        raise TimeoutError(f"ComfyUI generation timed out after {self.timeout}s for {prompt_id}")

    def _get_output_path(self, history: dict, prefix: str) -> Optional[Path]:
        for node_data in history.get("outputs", {}).values():
            for img in node_data.get("images", []):
                fname = img["filename"]
                subfolder = img.get("subfolder", "")
                if fname.startswith(prefix) and (len(fname) == len(prefix) or fname[len(prefix)] in ("_", ".")):
                    path = self.output_dir / subfolder / fname if subfolder else self.output_dir / fname
                    if path.exists():
                        return path
        return None

    def generate(self, prompt: str, prefix: str = "mpt_scene", seed: Optional[int] = None) -> Path:
        if seed is None:
            seed = self.seed
            self.seed += 1
        logger.info(f"[ComfyUI] generating: {prefix} ({self.width}x{self.height})")
        workflow = self._build_workflow(prompt, prefix, seed)
        prompt_id = self._queue_prompt(workflow)
        logger.debug(f"[ComfyUI] prompt_id={prompt_id}, waiting...")
        history = self._wait_for_completion(prompt_id)
        output_path = self._get_output_path(history, prefix)
        if not output_path:
            raise RuntimeError(f"Image generated but could not find output file with prefix '{prefix}'")
        logger.success(f"[ComfyUI] done: {output_path.name} ({output_path.stat().st_size / 1024:.0f} KB)")
        return output_path


# ══════════════════════════════════════════════════════════════════════════════
# OpenRouter (cloud API, no GPU)
# ══════════════════════════════════════════════════════════════════════════════

class OpenRouterImageGen(ImageGenProvider):
    """Generates images via OpenRouter's FLUX.2 Pro API.

    Uses the standard OpenAI-compatible chat completions endpoint with
    ``modalities: ["image"]``.  No GPU or ComfyUI needed — works on Render
    and any cloud instance.
    """

    def __init__(
        self,
        api_key: str = "",
        width: int = 540,
        height: int = 960,
        model: str = "",
        timeout: int = 120,
    ):
        from openai import OpenAI

        self.width = width
        self.height = height
        self.timeout = timeout
        self.model = model or _OPENROUTER_IMAGE_MODEL
        self.api_key = api_key
        self.output_dir = Path(config.app.get("comfyui_output_dir", "") or DEFAULT_OUTPUT_DIR).resolve()
        os.makedirs(self.output_dir, exist_ok=True)

        if not self.api_key:
            raise ValueError(
                "OpenRouter API key is required for ai_material_provider='openrouter'. "
                "Set openrouter_api_key in [app] config or OPENROUTER_API_KEY env var."
            )

        self._client = OpenAI(
            api_key=self.api_key,
            base_url="https://openrouter.ai/api/v1",
        )

    def _extract_image_bytes(self, response) -> bytes:
        """Extract base64 image data from an OpenRouter image response.

        Handles the OpenRouter-specific response structure where images
        are returned in ``message.images`` as data-URL strings.
        """
        message = getattr(response.choices[0], "message", None)
        if message is None:
            raise ValueError("OpenRouter returned empty message")

        images = getattr(message, "images", None)
        if images is None:
            raise ValueError("OpenRouter returned no images in response")

        image_url = images[0]["image_url"]["url"]
        if image_url.startswith("data:"):
            # data:image/png;base64,<data>
            b64_part = image_url.split(",", 1)[1]
            return base64.b64decode(b64_part)
        raise ValueError(f"Unexpected image URL format: {image_url[:80]}")

    def _try_generate(self, prompt: str) -> bytes:
        """Call OpenRouter image API. Falls back to flux.1-dev on failure."""
        full_prompt = f"{prompt.strip()}\n\n{_STYLE_SUFFIX}"

        for attempt, model in enumerate((self.model, _OPENROUTER_FALLBACK_MODEL)):
            try:
                logger.info(
                    f"[OpenRouter] generating {self.width}x{self.height}"
                    f" with {model}" + (f" (attempt {attempt + 1})" if attempt else "")
                )
                response = self._client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": full_prompt}],
                    extra_body={
                        "modalities": ["image"],
                        "image_config": {
                            "width": _OPENROUTER_IMAGE_WIDTH,
                            "height": _OPENROUTER_IMAGE_HEIGHT,
                        },
                    },
                    timeout=self.timeout,
                )
                return self._extract_image_bytes(response)
            except Exception as e:
                logger.warning(f"[OpenRouter] {model} failed: {e}")
                if attempt == 1:
                    raise

    def generate(self, prompt: str, prefix: str = "mpt_scene") -> Path:
        image_bytes = self._try_generate(prompt)
        output_path = self.output_dir / f"{prefix}.png"
        output_path.write_bytes(image_bytes)
        logger.success(
            f"[OpenRouter] done: {output_path.name} "
            f"({output_path.stat().st_size / 1024:.0f} KB)"
        )
        return output_path


# ══════════════════════════════════════════════════════════════════════════════
# Convenience wrappers
# ══════════════════════════════════════════════════════════════════════════════

def generate_ai_images(
    scene_prompts: List[dict],
    width: int = 540,
    height: int = 960,
    provider: str = "",
) -> List[Optional[Path]]:
    """Generate AI images for video scenes.

    Args:
        scene_prompts: List of dicts with ``visual_prompt`` and optionally
            ``index`` keys.
        width: Image width (used by ComfyUI; OpenRouter uses its own preset).
        height: Image height (used by ComfyUI; OpenRouter uses its own preset).
        provider: ``"comfyui"`` (default) or ``"openrouter"``.  Reads
            ``ai_material_provider`` from config when empty.

    Returns:
        List of :class:`Path` to generated PNGs (``None`` per failed scene).
    """
    gen = create_image_gen(provider=provider, width=width, height=height)
    return gen.generate_scenes(scene_prompts)
