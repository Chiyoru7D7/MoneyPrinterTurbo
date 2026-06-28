#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# Render Entrypoint — write config.toml with Python, launch
# ─────────────────────────────────────────────────────────────
set -e

# Standard plan has enough RAM — use full 1080p
export LOW_MEMORY_MODE="${LOW_MEMORY_MODE:-0}"
echo "[render_entrypoint] LOW_MEMORY_MODE=$LOW_MEMORY_MODE"

CONFIG_FILE="/MoneyPrinterTurbo/config.toml"

echo "[render_entrypoint] Writing config.toml from env vars with Python..."

python3 -c "
import os

deepseek_key   = os.getenv('DEEPSEEK_API_KEY', '')
pexels_key     = os.getenv('PEXELS_API_KEY', '')
llm_provider   = os.getenv('LLM_PROVIDER', 'deepseek')
voice_name     = os.getenv('VOICE_NAME', 'en-US-JennyNeural')
video_source   = os.getenv('VIDEO_SOURCE', 'pexels')         # 'pexels' | 'ai_image'
cf_account_id  = os.getenv('CLOUDFLARE_ACCOUNT_ID', '')
cf_api_token   = os.getenv('CLOUDFLARE_API_TOKEN', '')
up_enabled     = os.getenv('UPLOAD_POST_ENABLED', 'false')
up_api_key     = os.getenv('UPLOAD_POST_API_KEY', '')
up_username    = os.getenv('UPLOAD_POST_USERNAME', '')
up_platforms   = os.getenv('UPLOAD_POST_PLATFORMS', 'instagram')
up_auto        = os.getenv('UPLOAD_POST_AUTO_UPLOAD', 'false')
# Convert comma-separated platforms to TOML array format: ["ig","tt","yt"]
up_platforms_list = ', '.join(f'\"{p.strip()}\"' for p in up_platforms.split(','))

config = f'''[app]
video_source = \"{video_source}\"
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

# AI Image Generation (Cloudflare Workers AI — free)
cloudflare_account_id = \"{cf_account_id}\"
cloudflare_api_token = \"{cf_api_token}\"

# Upload-Post — auto publish to social media
upload_post_enabled = {up_enabled}
upload_post_api_key = \"{up_api_key}\"
upload_post_username = \"{up_username}\"
upload_post_platforms = [{up_platforms_list}]
upload_post_auto_upload = {up_auto}
upload_post_youtube_privacy_status = \"public\"

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

print(f'[render_entrypoint] Config written: video_source={video_source}, llm={llm_provider}, pexels={\"***\" if pexels_key else \"(missing)\"}, cloudflare={\"***\" if cf_api_token else \"(missing)\"}, voice={voice_name}, upload_post={up_enabled}')
"

echo "[render_entrypoint] Starting MPT Dashboard on port ${PORT:-8501}..."
exec streamlit run dashboard.py \
    --server.port="${PORT:-8501}" \
    --server.address="0.0.0.0" \
    --server.headless="true" \
    --browser.gatherUsageStats="false" \
    --server.enableCORS="false" \
    --server.enableXsrfProtection="false"
