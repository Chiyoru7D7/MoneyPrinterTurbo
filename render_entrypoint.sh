#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# Render Entrypoint — generate/update config.toml from env & launch
# ─────────────────────────────────────────────────────────────
set -e

CONFIG_FILE="/MoneyPrinterTurbo/config.toml"

# Generate default config if missing
if [ ! -f "$CONFIG_FILE" ]; then
    echo "[render_entrypoint] Generating default config.toml..."
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
deepseek_api_key = ""
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
fi

# ── ALWAYS inject API keys from env vars (overwrites existing) ──
if [ -n "$DEEPSEEK_API_KEY" ]; then
    if grep -q 'deepseek_api_key' "$CONFIG_FILE"; then
        sed -i "s|deepseek_api_key = \".*\"|deepseek_api_key = \"$DEEPSEEK_API_KEY\"|" "$CONFIG_FILE"
    fi
    echo "[render_entrypoint] DeepSeek API key configured: ${DEEPSEEK_API_KEY:0:5}..."
else
    echo "[render_entrypoint] WARNING: DEEPSEEK_API_KEY env var is not set!"
fi

if [ -n "$PEXELS_API_KEY" ]; then
    if grep -q 'pexels_api_keys' "$CONFIG_FILE"; then
        sed -i "s|pexels_api_keys = \[.*\]|pexels_api_keys = [\"$PEXELS_API_KEY\"]|" "$CONFIG_FILE"
    fi
    echo "[render_entrypoint] Pexels API key configured: ${PEXELS_API_KEY:0:5}..."
else
    echo "[render_entrypoint] WARNING: PEXELS_API_KEY env var is not set!"
fi

echo "[render_entrypoint] Starting MPT Dashboard on port ${PORT:-8501}..."
exec streamlit run dashboard.py \
    --server.port="${PORT:-8501}" \
    --server.address="0.0.0.0" \
    --server.headless="true" \
    --browser.gatherUsageStats="false" \
    --server.enableCORS="false" \
    --server.enableXsrfProtection="false"
