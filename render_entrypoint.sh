#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# Render Entrypoint — generate config.toml from env & launch
# ─────────────────────────────────────────────────────────────
set -e

CONFIG_FILE="/MoneyPrinterTurbo/config.toml"

# Only generate if config doesn't exist (allow mounting custom config)
if [ ! -f "$CONFIG_FILE" ]; then
    echo "[render_entrypoint] Generating config.toml from environment..."

    cat > "$CONFIG_FILE" << 'TOML'
[app]
video_source = "pexels"
hide_config = false
edge_tts_timeout = 30
tls_verify = true

pexels_api_keys = []
pixabay_api_keys = []
coverr_api_keys = []

llm_provider = "deepseek"
deepseek_model_name = "deepseek-chat"
deepseek_base_url = "https://api.deepseek.com"

voice_name = "en-US-JennyNeural"

subtitle_enabled = true
subtitle_provider = "edge"
font_name = "STHeitiMedium.ttc"
font_size = 60
text_fore_color = "#FFFFFF"
text_background_color = true
stroke_color = "#000000"
stroke_width = 1.5
subtitle_position = "bottom"

material_directory = ""

[whisper]
model_size = "large-v3"
device = "cpu"
compute_type = "int8"

[siliconflow]
api_key = ""

[proxy]
[azure]
[ui]
hide_log = false
TOML

    # ── Inject API keys from env vars ──
    if [ -n "$DEEPSEEK_API_KEY" ]; then
        sed -i "s|deepseek_api_key = \"\"|deepseek_api_key = \"$DEEPSEEK_API_KEY\"|" "$CONFIG_FILE"
        echo "[render_entrypoint] DeepSeek API key configured"
    fi

    if [ -n "$PEXELS_API_KEY" ]; then
        sed -i "s|pexels_api_keys = \[\]|pexels_api_keys = [\"$PEXELS_API_KEY\"]|" "$CONFIG_FILE"
        echo "[render_entrypoint] Pexels API key configured"
    fi

    echo "[render_entrypoint] Config written."
else
    echo "[render_entrypoint] Using existing config.toml"
fi

# ── Launch dashboard ──
echo "[render_entrypoint] Starting MPT Dashboard on port ${PORT:-8501}..."
exec streamlit run dashboard.py \
    --server.port="${PORT:-8501}" \
    --server.address="0.0.0.0" \
    --server.headless="true" \
    --browser.gatherUsageStats="false" \
    --server.enableCORS="false" \
    --server.enableXsrfProtection="false"
