#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# Render Entrypoint — generate config.toml & launch dashboard
# API keys are read from env vars by config.py, NOT injected here
# ─────────────────────────────────────────────────────────────
set -e

CONFIG_FILE="/MoneyPrinterTurbo/config.toml"

# Generate a clean default config if missing (env takeover by config.py)
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

# API keys are set via environment variables in config.py
# DEEPSEEK_API_KEY, PEXELS_API_KEY, LLM_PROVIDER, VOICE_NAME
deepseek_api_key = ""
deepseek_model_name = "deepseek-chat"
deepseek_base_url = "https://api.deepseek.com"
llm_provider = "deepseek"

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

    echo "[render_entrypoint] Config written."
else
    echo "[render_entrypoint] Using existing config.toml"
fi

# Log env var status (config.py does the actual injection)
echo "[render_entrypoint] DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY:+(set)} PEXELS_API_KEY=${PEXELS_API_KEY:+(set)}"

echo "[render_entrypoint] Starting MPT Dashboard on port ${PORT:-8501}..."
exec streamlit run dashboard.py \
    --server.port="${PORT:-8501}" \
    --server.address="0.0.0.0" \
    --server.headless="true" \
    --browser.gatherUsageStats="false" \
    --server.enableCORS="false" \
    --server.enableXsrfProtection="false"
