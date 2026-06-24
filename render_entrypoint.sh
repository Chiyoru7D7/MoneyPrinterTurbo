#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# Render Entrypoint — write config.toml with Python, launch
# ─────────────────────────────────────────────────────────────
set -e

CONFIG_FILE="/MoneyPrinterTurbo/config.toml"

echo "[render_entrypoint] Writing config.toml from env vars with Python..."

python3 -c "
import os

deepseek_key = os.getenv('DEEPSEEK_API_KEY', '')
pexels_key   = os.getenv('PEXELS_API_KEY', '')
llm_provider = os.getenv('LLM_PROVIDER', 'deepseek')
voice_name   = os.getenv('VOICE_NAME', 'en-US-JennyNeural')

config = f'''[app]
video_source = \"pexels\"
hide_config = false
edge_tts_timeout = 30
tls_verify = true

pexels_api_keys = [\"{pexels_key}\"]
pixabay_api_keys = []
coverr_api_keys = []

llm_provider = \"{llm_provider}\"
deepseek_api_key = \"{deepseek_key}\"
deepseek_model_name = \"deepseek-chat\"
deepseek_base_url = \"https://api.deepseek.com\"

voice_name = \"{voice_name}\"

subtitle_enabled = true
subtitle_provider = \"edge\"
font_name = \"STHeitiMedium.ttc\"
font_size = 60
text_fore_color = \"#FFFFFF\"
text_background_color = true
stroke_color = \"#000000\"
stroke_width = 1.5
subtitle_position = \"bottom\"

material_directory = \"\"

[whisper]
model_size = \"large-v3\"
device = \"cpu\"
compute_type = \"int8\"

[siliconflow]
api_key = \"\"

[proxy]
[azure]
[ui]
hide_log = false
'''

with open('$CONFIG_FILE', 'w') as f:
    f.write(config)

print(f'[render_entrypoint] Config written: llm_provider={llm_provider}, deepseek_key={\"***\" if deepseek_key else \"(missing)\"}, pexels_key={\"***\" if pexels_key else \"(missing)\"}, voice={voice_name}')
"

echo "[render_entrypoint] Starting MPT Dashboard on port ${PORT:-8501}..."
exec streamlit run dashboard.py \
    --server.port="${PORT:-8501}" \
    --server.address="0.0.0.0" \
    --server.headless="true" \
    --browser.gatherUsageStats="false" \
    --server.enableCORS="false" \
    --server.enableXsrfProtection="false"
