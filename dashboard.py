"""
MoneyPrinterTurbo — Professional Video Production Dashboard
Run: streamlit run dashboard.py
"""
import streamlit as st
import os
import sys
import uuid
import threading
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger

st.set_page_config(
    page_title="MPT Dashboard | AI Video Production",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="auto",
)

# ── Color Palette ───────────────────────────────────────────
ACCENT = "#77dd77"
ACCENT_DARK = "#4caf50"
ACCENT_DEEP = "#2e7d32"
BG = "#f5faf6"
CARD_BG = "#ffffff"
CARD_BORDER = "#d0e8d0"
TEXT_PRIMARY = "#1a2e1a"
TEXT_SECONDARY = "#5a7a5a"
TEXT_MUTED = "#7a9a7a"
HEADING = "#0d1f0d"
SUCCESS = "#2e7d32"
RUNNING = "#e6a817"
FAILED = "#c0392b"
HIGHLIGHT_BG = "#e8f5e9"

# ── CSS Theme ──────────────────────────────────────────────
st.markdown(f"""
<style>
    .stApp {{ background: {BG}; }}
    [data-testid="stToolbar"] {{ display: none !important; }}
    #MainMenu {{ display: none !important; }}
    footer {{ display: none !important; }}
    header {{ display: none !important; }}
    .main .block-container {{ padding: 2rem 3rem; max-width: 1500px; }}

    h1 {{ font-size: 2.6rem !important; color: {HEADING} !important; font-weight: 800 !important; letter-spacing: -0.03em; }}
    h2 {{ font-size: 1.8rem !important; color: {HEADING} !important; font-weight: 700 !important; }}
    h3 {{ font-size: 1.4rem !important; color: {HEADING} !important; font-weight: 700 !important; }}
    p, li, label, div {{ color: {TEXT_PRIMARY}; }}
    .text-muted {{ color: {TEXT_MUTED}; font-size: 0.95rem; }}
    .text-secondary {{ color: {TEXT_SECONDARY}; font-size: 1rem; }}

    /* ── Cards ── */
    .card {{
        background: {CARD_BG};
        border: 1px solid {CARD_BORDER};
        border-radius: 16px;
        padding: 32px;
        margin-bottom: 24px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.04);
    }}
    .card-sm {{ padding: 24px; }}

    /* ── Stats Row ── */
    .stats-row {{ display: flex; gap: 18px; margin-bottom: 28px; flex-wrap: wrap; }}
    .stat-box {{
        flex: 1; min-width: 150px; background: {CARD_BG};
        border: 1px solid {CARD_BORDER}; border-radius: 10px;
        padding: 16px 20px; box-shadow: 0 1px 2px rgba(0,0,0,0.03);
        display: flex; flex-direction: column; justify-content: center; min-height: 84px;
    }}
    .stat-box.accent {{ border-left: 4px solid {ACCENT}; }}
    .stat-box .value {{ font-size: 1.8rem; font-weight: 800; color: {HEADING}; line-height: 1.1; }}
    .stat-box .label {{ font-size: 0.75rem; color: {TEXT_SECONDARY}; margin-top: 4px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }}
    .stat-box.accent .value {{ color: {ACCENT_DEEP}; }}

    /* ── Pipeline ── */
    .pipeline {{ display: flex; gap: 0; margin: 24px 0; background: {CARD_BG}; border: 1px solid {CARD_BORDER}; border-radius: 14px; overflow: hidden; }}
    .pipe-step {{
        flex: 1; text-align: center; padding: 20px 10px; position: relative; background: {CARD_BG};
    }}
    .pipe-step::after {{
        content: "→"; position: absolute; right: -10px; top: 50%; transform: translateY(-50%);
        color: {CARD_BORDER}; font-size: 1.5rem; font-weight: 700; z-index: 1;
    }}
    .pipe-step:last-child::after {{ content: ""; }}
    .pipe-step .icon {{ font-size: 2rem; margin-bottom: 6px; }}
    .pipe-step .name {{ font-size: 0.9rem; font-weight: 700; color: {TEXT_PRIMARY}; }}
    .pipe-step .detail {{ font-size: 0.78rem; color: {TEXT_MUTED}; }}

    /* ── Video card ── */
    .video-card {{
        background: {CARD_BG}; border: 1px solid {CARD_BORDER};
        border-radius: 16px; margin-bottom: 24px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,0.03);
    }}
    .video-card-header {{ padding: 22px 28px 14px 28px; display: flex; align-items: center; justify-content: space-between; }}
    .video-card-body {{ padding: 0 28px 24px 28px; }}

    /* ── Badges ── */
    .badge {{
        display: inline-flex; align-items: center; gap: 6px; padding: 6px 16px;
        border-radius: 24px; font-size: 0.85rem; font-weight: 700;
    }}
    .badge-success {{ background: #e8f5e9; color: {SUCCESS}; border: 1px solid #c8e6c9; }}
    .badge-failed {{ background: #ffebee; color: {FAILED}; border: 1px solid #ffcdd2; }}
    .badge-id {{
        background: {BG}; color: {TEXT_SECONDARY}; font-family: monospace; font-size: 0.82rem; padding: 4px 12px; border-radius: 8px;
    }}

    /* ── Buttons ── */
    .stButton > button {{
        background: {ACCENT} !important; color: #000000 !important; border: none !important;
        font-weight: 800 !important; border-radius: 14px !important; padding: 18px 40px !important;
        font-size: 1.4rem !important; transition: all 0.2s !important; letter-spacing: 0.02em;
    }}
    .stButton > button:hover {{
        background: {ACCENT_DARK} !important; color: white !important;
        box-shadow: 0 6px 20px rgba(119,221,119,0.4) !important; transform: translateY(-2px);
    }}

    /* ── Inputs ── */
    .stTextInput > div > div > input, .stSelectbox > div > div {{
        border: 2px solid {CARD_BORDER} !important; border-radius: 12px !important;
        padding: 16px 18px !important; font-size: 1.15rem !important; color: #000000 !important; background: white !important; font-weight: 600 !important;
    }}
    .stTextInput > div > div > input:focus {{
        border-color: {ACCENT} !important; box-shadow: 0 0 0 4px rgba(119,221,119,0.15) !important;
    }}
    .stSelectbox label, .stTextInput label {{ font-size: 1.25rem !important; color: #000000 !important; font-weight: 700 !important; }}

    /* ── Dark Sidebar ── */
    [data-testid="stSidebar"] {{
        background: #1a1a2e !important;
        border-right: none !important;
    }}
    [data-testid="stSidebar"] * {{
        color: #e0e0e0 !important;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
    }}
    [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{
        color: #ffffff !important;
    }}
    [data-testid="stSidebar"] strong {{
        color: {ACCENT} !important;
    }}
    [data-testid="stSidebar"] .stButton > button {{
        font-size: 0.9rem !important;
        font-weight: 600 !important;
        padding: 10px 12px !important;
        border-radius: 8px !important;
        text-align: center !important;
    }}
    [data-testid="stSidebar"] .stButton > button[kind="primary"] {{
        background: {ACCENT_DEEP} !important;
        color: #ffffff !important;
        border: 1px solid {ACCENT} !important;
    }}
    [data-testid="stSidebar"] .stButton > button[kind="secondary"] {{
        background: transparent !important;
        color: #cccccc !important;
        border: 1px solid #2a2a4a !important;
    }}
    [data-testid="stSidebar"] hr {{
        border-color: #2a2a4a !important;
    }}

    /* ── Radio buttons ── */
    .stRadio label {{
        color: #000000 !important;
        font-size: 1rem !important;
        font-weight: 600 !important;
    }}

    /* ── Tabs ── */
    .stTabs [data-baseweb="tab"] {{
        font-size: 1.1rem !important; font-weight: 700 !important; padding: 14px 24px !important;
        color: {TEXT_SECONDARY} !important;
    }}
    .stTabs [aria-selected="true"] {{ color: {ACCENT_DEEP} !important; }}

    /* ── Metrics ── */
    [data-testid="stMetricValue"] {{ color: {HEADING} !important; font-weight: 800 !important; font-size: 2rem !important; }}

    /* ── Footer ── */
    .footer {{ text-align: center; padding: 36px; color: {TEXT_MUTED}; font-size: 0.9rem; border-top: 2px solid {CARD_BORDER}; margin-top: 48px; }}

    /* ── Animations ── */
    .live-dot {{
        display: inline-block; width: 10px; height: 10px; border-radius: 50%; background: {ACCENT};
        animation: pulse 1.5s ease-in-out infinite; margin-right: 8px;
    }}
    @keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.35; }} }}

    /* ── Center form ── */
    .hero-form {{
        max-width: 600px; margin: 0 auto; text-align: center;
        background: {CARD_BG}; border: 2px solid {ACCENT};
        border-radius: 14px; padding: 28px 36px;
        box-shadow: 0 4px 16px rgba(119,221,119,0.10);
    }}
    .hero-form h2 {{ margin-bottom: 8px; }}
</style>
""", unsafe_allow_html=True)

# ── Data layer ──────────────────────────────────────────────
STORAGE = Path(__file__).parent / "storage" / "tasks"
CACHE = Path(__file__).parent / "storage" / "cache_videos"
_THREAD_STORE = {}
_THREAD_LOCK = threading.Lock()

if "running_tasks" not in st.session_state:
    st.session_state.running_tasks = {}
if "nav_page" not in st.session_state:
    st.session_state.nav_page = "🎬 Dashboard"


def load_tasks():
    tasks = []
    if not STORAGE.exists():
        return tasks
    for task_dir in sorted(STORAGE.iterdir(), reverse=True):
        if not task_dir.is_dir():
            continue
        final_videos = list(task_dir.glob("final-*.mp4"))
        combined = list(task_dir.glob("combined-*.mp4"))
        tasks.append({
            "id_short": task_dir.name[:8],
            "full_id": task_dir.name,
            "task_dir": str(task_dir),
            "final_videos": [str(v) for v in final_videos],
            "combined": [str(v) for v in combined],
            "video_count": len(final_videos),
            "modified": datetime.fromtimestamp(task_dir.stat().st_mtime),
            "success": len(final_videos) > 0,
        })
    return tasks


def get_video_size_mb(path):
    try: return os.path.getsize(path) / (1024 * 1024)
    except: return 0


def _run_video_generation(task_id, subject, voice, length_key="Short (~15s)", video_source="pexels", ai_provider="comfyui"):
    try:
        from app.models.schema import VideoParams
        from app.services import task as task_service

        length_config = {
            "Short (~15s)":  (1, "Write EXACTLY 2-3 short sentences. Total word count MUST be 25-40 words. Be concise."),
            "Medium (~30s)": (2, "Write EXACTLY 4-5 sentences. Total word count MUST be 60-90 words. Keep it engaging."),
            "Long (~60s)":   (3, "Write 6-8 sentences across 2-3 paragraphs. Total word count MUST be 130-170 words."),
        }
        paragraphs, script_prompt = length_config.get(length_key, length_config["Short (~15s)"])

        # Use English font for English voices, Chinese font for Chinese
        if voice.startswith("en-"):
            font = "Charm-Bold.ttf"
        else:
            font = "STHeitiMedium.ttc"

        with _THREAD_LOCK:
            _THREAD_STORE[task_id] = {"status": "running", "error": None}

        params_kwargs = dict(
            video_subject=subject,
            voice_name=voice,
            video_aspect="9:16",
            video_source=video_source,
            paragraph_number=paragraphs,
            video_script_prompt=script_prompt,
            font_name=font,
        )
        if video_source == "ai_image":
            params_kwargs["ai_material_provider"] = ai_provider
            params_kwargs["ai_scene_count"] = paragraphs

        params = VideoParams(**params_kwargs)
        task_service.start(task_id, params, stop_at="video")
        with _THREAD_LOCK:
            _THREAD_STORE[task_id] = {"status": "done", "error": None}
    except Exception as e:
        with _THREAD_LOCK:
            _THREAD_STORE[task_id] = {"status": "error", "error": str(e)}


with _THREAD_LOCK:
    for tid, tinfo in _THREAD_STORE.items():
        st.session_state.running_tasks.setdefault(tid, {}).update(tinfo)

tasks = load_tasks()
total = len(tasks)
success_count = sum(1 for t in tasks if t["success"])
total_videos = sum(t["video_count"] for t in tasks)
total_size = sum(sum(get_video_size_mb(v) for v in t["final_videos"]) for t in tasks)
success_rate = (success_count / total * 100) if total > 0 else 0

# ── Sidebar Navigation ──────────────────────────────────────
with st.sidebar:
    st.markdown(f"""
    <div style="text-align:center;padding:10px 0 20px 0;">
        <div style="font-size:2.8rem;">🎬</div>
        <h2 style="margin:4px 0;font-size:1.3rem !important;">MPT Console</h2>
        <p style="margin:0;font-size:0.8rem;opacity:0.7;">v1.3.0 · Render Cloud</p>
    </div>
    """, unsafe_allow_html=True)

    # Navigation — buttons instead of selectbox
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🎬 Dashboard", use_container_width=True,
                     type="primary" if st.session_state.nav_page == "🎬 Dashboard" else "secondary"):
            st.session_state.nav_page = "🎬 Dashboard"
            st.rerun()
    with c2:
        if st.button("⚙️ Pipeline", use_container_width=True,
                     type="primary" if st.session_state.nav_page == "⚙️ Pipeline & Info" else "secondary"):
            st.session_state.nav_page = "⚙️ Pipeline & Info"
            st.rerun()

    st.divider()

    # Config display
    try:
        from app.config.config import app as cfg
        llm_p = cfg.get("llm_provider", "deepseek")
        fs_source = cfg.get("video_source", "pexels")
        ai_p = cfg.get("ai_material_provider", "comfyui")
    except Exception:
        llm_p, fs_source, ai_p = "deepseek", "pexels", "comfyui"

    fs_icon = "🤖" if fs_source == "ai_image" else "🎞️"

    st.markdown(f"""
    <div style="text-align:center;font-size:0.9rem;line-height:2.2;">
        <div>🤖 LLM: <strong>{llm_p}</strong></div>
        <div>🎙️ TTS: <strong>Edge TTS</strong></div>
        <div>📐 Format: <strong>9:16</strong></div>
        <div>{fs_icon} Source: <strong>{fs_source}</strong></div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # Cache cleanup
    cache_count = len(list(CACHE.glob("*.mp4"))) if CACHE.exists() else 0
    cache_size = sum(f.stat().st_size for f in CACHE.glob("*.mp4")) / (1024 * 1024) if CACHE.exists() else 0
    st.caption(f"🎞️ Cached clips: {cache_count} files ({cache_size:.1f} MB)")
    if st.button("🗑️ Delete Cache", use_container_width=True):
        import shutil
        deleted = 0
        if CACHE.exists():
            for f in CACHE.glob("*.mp4"):
                try:
                    f.unlink()
                    deleted += 1
                except Exception:
                    pass
        st.success(f"Deleted {deleted} cached files.")
        st.rerun()

# ─────────────────────────────────────────────────────────────
# PAGE 1: DASHBOARD
# ─────────────────────────────────────────────────────────────
if st.session_state.nav_page == "🎬 Dashboard":

    # ── Header ──
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:16px;margin-bottom:6px;">
        <div>
            <h1 style="margin:0;">Video Production</h1>
            <p class="text-secondary" style="margin:4px 0 0 0;font-size:1.1rem;">
                AI-Powered Advertising · DeepSeek + Edge TTS + Pexels / AI Image
            </p>
        </div>
        <div style="margin-left:auto;text-align:right;">
            <span class="live-dot"></span>
            <span style="color:{TEXT_SECONDARY};font-weight:700;font-size:0.95rem;">Live</span>
            <br><span class="text-muted" style="font-size:0.8rem;">Render Cloud</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── Stats Row ──
    st.markdown(f"""
    <div class="stats-row">
        <div class="stat-box accent"><div class="value">{total}</div><div class="label">Total Tasks</div></div>
        <div class="stat-box accent"><div class="value">{total_videos}</div><div class="label">Videos Generated</div></div>
        <div class="stat-box accent"><div class="value">{success_rate:.0f}%</div><div class="label">Success Rate</div></div>
        <div class="stat-box accent"><div class="value">{total_size:.1f} MB</div><div class="label">Total Output</div></div>
        <div class="stat-box"><div class="value">DeepSeek</div><div class="label">LLM Engine</div></div>
        <div class="stat-box"><div class="value">9:16</div><div class="label">Format</div></div>
    </div>
    """, unsafe_allow_html=True)

    # ── HERO: Generate Form (center) ──
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(f"""
    <div class="hero-form">
        <h2>🚀 Generate New Video</h2>
        <p class="text-secondary" style="margin-bottom:24px;">Enter your product concept — AI handles the rest</p>
    """, unsafe_allow_html=True)

    with st.form("generate_form", clear_on_submit=False):
        topic = st.text_input(
            "What should the video be about?",
            placeholder="e.g. New eco-friendly sneakers made from recycled ocean plastic...",
            label_visibility="collapsed",
        )
        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            voice = st.radio(
                "Voice",
                ["en-US-JennyNeural", "en-US-GuyNeural", "zh-CN-XiaoxiaoNeural-Female"],
                index=0,
            )
        with c2:
            length = st.radio(
                "Video Length",
                ["Short (~15s)", "Medium (~30s)", "Long (~60s)"],
                index=0,
            )
        with c3:
            source = st.radio(
                "Footage Source",
                ["🎞️ Pexels", "🤖 AI Image"],
                index=0,
                help="Pexels = stock footage from the web. AI Image = ComfyUI/OpenRouter generates scene images.",
            )

        ai_provider = "comfyui"
        if source == "🤖 AI Image":
            # Default to config's provider, or openrouter on Render (no GPU)
            try:
                from app.config.config import app as _cfg
                _default_provider = _cfg.get("ai_material_provider", "") or ""
            except Exception:
                _default_provider = ""
            if not _default_provider:
                import os as _os
                _default_provider = "cloudflare" if _os.getenv("RENDER", "") else "comfyui"
            _providers = ["comfyui (local GPU)", "openrouter (cloud)", "together (cloud)", "cloudflare (free)"]
            _provider_idx = next(
                (i for i, p in enumerate(_providers) if p.startswith(_default_provider)), 3
            )
            ai_provider = st.radio(
                "AI Provider",
                _providers,
                index=_provider_idx,
                help="comfyui = local GPU. openrouter = cloud API. together = cloud ($5 deposit). cloudflare = FREE (~230/day, no credit card).",
            )
            # Strip the description suffix for the actual value
            ai_provider = ai_provider.split(" ")[0]

        video_source = "ai_image" if source == "🤖 AI Image" else "pexels"

        submitted = st.form_submit_button("⚡ Generate", type="primary", use_container_width=True)

        if submitted and topic.strip():
            task_id = str(uuid.uuid4())
            task_dir = STORAGE / task_id

            st.session_state.running_tasks[task_id] = {"status": "running", "error": None}
            t = threading.Thread(target=_run_video_generation, args=(task_id, topic.strip(), voice, length, video_source, ai_provider), daemon=True)
            t.start()
            st.success(f"Task `{task_id[:8]}` started!")

            # ── Progress bar: poll actual files ──
            import time as _time
            progress_placeholder = st.empty()
            is_ai = (video_source == "ai_image")
            footage_label = "Generating AI images..." if is_ai else "Downloading stock footage..."
            steps_poll = [
                (5,  "Starting pipeline...",                           lambda: True),
                (15, "Generating script with DeepSeek...",             lambda: (task_dir / "audio.mp3").exists()),
                (35, "Creating voiceover with Edge TTS...",            lambda: (task_dir / "subtitle.srt").exists()),
                (50, footage_label,                                    lambda: len(list(task_dir.glob("temp-clip-*.mp4"))) > 0 or len(list(task_dir.glob("kb_scene_*.mp4"))) > 0),
                (75, "Assembling video clips...",                      lambda: (task_dir / "combined-1.mp4").exists()),
                (95, "Rendering final MP4...",                         lambda: (task_dir / "final-1.mp4").exists()),
                (100,"Video complete!",                                lambda: (task_dir / "final-1.mp4").exists()),
            ]
            for pct, msg, check in steps_poll:
                with progress_placeholder.container():
                    st.progress(pct if pct < 100 else 100, msg)
                # Wait until condition met, checking every 3 seconds
                waited = 0
                while not check() and waited < 180:  # max 3 min per step
                    _time.sleep(3)
                    waited += 3
                if pct >= 100:
                    break
            with progress_placeholder.container():
                st.progress(100, "Video complete!")
            if task_id in st.session_state.running_tasks:
                del st.session_state.running_tasks[task_id]
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    # ── Running indicator (only for tasks without progress bar) ──
    running = {k: v for k, v in st.session_state.running_tasks.items() if v.get("status") in ("running",)}
    if running:
        st.markdown(f"""
        <div style="background:{HIGHLIGHT_BG};border:1px solid {ACCENT};border-radius:14px;padding:16px 24px;margin-bottom:24px;">
            <span class="live-dot" style="background:{RUNNING};"></span>
            <span style="color:{TEXT_PRIMARY};font-weight:700;font-size:1rem;">Generating video · this takes 2–4 minutes on Render</span>
        </div>
        """, unsafe_allow_html=True)

    # ── Video Gallery (Drawer-style collapsible) ──
    st.markdown(f"<h2>📼 Recent Videos <span style='font-size:1rem;color:{TEXT_MUTED};font-weight:400;'>({total} tasks)</span></h2>", unsafe_allow_html=True)

    if not tasks:
        st.markdown(f"""
        <div class="card" style="text-align:center;padding:60px;">
            <div style="font-size:4rem;margin-bottom:16px;">🎥</div>
            <h2 style="margin:0 0 8px 0;">No Videos Yet</h2>
            <p class="text-secondary" style="font-size:1.1rem;">Use the form above to generate your first AI-powered video.</p>
        </div>
        """, unsafe_allow_html=True)

    for task in tasks:
        modified_str = task["modified"].strftime("%b %d, %Y · %H:%M UTC")
        if task["success"]:
            status_icon = "✅"
            status_label = "Completed"
        else:
            status_icon = "❌"
            status_label = "Failed"

        size_info = ""
        if task["final_videos"]:
            mb = sum(get_video_size_mb(v) for v in task["final_videos"])
            size_info = f" · {mb:.1f} MB · {task['video_count']} video(s)"

        drawer_title = f"{status_icon}  `{task['id_short']}`  —  {status_label}  ·  {modified_str}{size_info}"

        with st.expander(drawer_title, expanded=(task == tasks[0] if tasks else False)):
            if task["final_videos"]:
                for vpath in task["final_videos"]:
                    if os.path.exists(vpath):
                        st.video(vpath)
                        break
            else:
                st.caption("No output video found for this task.")

            # Delete button
            cdel1, cdel2 = st.columns([3, 1])
            with cdel2:
                if st.button(f"🗑️ Delete", key=f"del_{task['full_id']}", use_container_width=True):
                    import shutil
                    try:
                        shutil.rmtree(task["task_dir"])
                        st.success(f"Deleted task `{task['id_short']}`")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")

# ─────────────────────────────────────────────────────────────
# PAGE 2: PIPELINE & INFO
# ─────────────────────────────────────────────────────────────
else:

    st.markdown("<h1>⚙️ Pipeline & System Info</h1>", unsafe_allow_html=True)
    st.markdown("<hr>", unsafe_allow_html=True)

    # Pipeline
    st.markdown("<h2>🔗 Video Generation Pipeline</h2>", unsafe_allow_html=True)

    try:
        from app.config.config import app as cfg
        fs_src = cfg.get("video_source", "pexels")
        ai_p = cfg.get("ai_material_provider", "comfyui")
    except Exception:
        fs_src, ai_p = "pexels", "comfyui"

    if fs_src == "ai_image":
        footage_icon = "🎨"
        footage_name = "AI Image Gen"
        footage_detail = f"Flux ({ai_p})"
    else:
        footage_icon = "📥"
        footage_name = "Stock Footage"
        footage_detail = "Pexels API"

    st.markdown(f"""
    <div class="pipeline">
        <div class="pipe-step"><div class="icon">🤖</div><div class="name">LLM Script</div><div class="detail">DeepSeek Chat</div></div>
        <div class="pipe-step"><div class="icon">🎬</div><div class="name">Director Cut</div><div class="detail">Script+Visuals</div></div>
        <div class="pipe-step"><div class="icon">🎙️</div><div class="name">TTS Narration</div><div class="detail">Edge TTS</div></div>
        <div class="pipe-step"><div class="icon">{footage_icon}</div><div class="name">{footage_name}</div><div class="detail">{footage_detail}</div></div>
        <div class="pipe-step"><div class="icon">🎥</div><div class="name">Ken Burns</div><div class="detail">ffmpeg zoompan</div></div>
        <div class="pipe-step"><div class="icon">📝</div><div class="name">Subtitles</div><div class="detail">Edge Sync</div></div>
        <div class="pipe-step"><div class="icon">🎵</div><div class="name">Render</div><div class="detail">FFmpeg</div></div>
    </div>
    """, unsafe_allow_html=True)

    # Config + Storage in two columns
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("<h3>⚙️ Active Configuration</h3>", unsafe_allow_html=True)
        try:
            from app.config.config import app as cfg
            llm_p = cfg.get("llm_provider", "deepseek")
            voice_p = cfg.get("voice_name", "en-US-JennyNeural")
            source = cfg.get("video_source", "pexels")
            ai_provider = cfg.get("ai_material_provider", "comfyui")
        except Exception:
            llm_p, voice_p, source, ai_provider = "deepseek", "en-US-JennyNeural", "pexels", "comfyui"

        footage_label = f"{source}" + (f" + {ai_provider}" if source == "ai_image" else "")

        st.markdown(f"""
        <div class="card card-sm">
            <table style="width:100%;font-size:1.05rem;line-height:2.6;">
                <tr><td style="color:{TEXT_SECONDARY};">🤖 LLM Provider</td><td style="font-weight:700;">{llm_p}</td></tr>
                <tr><td style="color:{TEXT_SECONDARY};">🧠 Model</td><td style="font-weight:700;">deepseek-chat</td></tr>
                <tr><td style="color:{TEXT_SECONDARY};">🎙️ TTS Engine</td><td style="font-weight:700;">Edge TTS</td></tr>
                <tr><td style="color:{TEXT_SECONDARY};">🗣️ Voice</td><td style="font-weight:700;">{voice_p}</td></tr>
                <tr><td style="color:{TEXT_SECONDARY};">📥 Footage Source</td><td style="font-weight:700;">{footage_label}</td></tr>
                <tr><td style="color:{TEXT_SECONDARY};">📐 Output Format</td><td style="font-weight:700;">9:16 Portrait (1080×1920)</td></tr>
                <tr><td style="color:{TEXT_SECONDARY};">🎞️ Codec</td><td style="font-weight:700;">libx264</td></tr>
                <tr><td style="color:{TEXT_SECONDARY};">🌐 Deployment</td><td style="font-weight:700;">Render Cloud</td></tr>
            </table>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown("<h3>💾 Storage Overview</h3>", unsafe_allow_html=True)
        cache_count = len(list(CACHE.glob("*.mp4"))) if CACHE.exists() else 0
        cache_size = sum(f.stat().st_size for f in CACHE.glob("*.mp4")) / (1024 * 1024) if CACHE.exists() else 0
        disk_tasks = len(list(STORAGE.iterdir())) if STORAGE.exists() else 0

        # Calculate per-task sizes
        task_sizes = []
        if STORAGE.exists():
            for td in STORAGE.iterdir():
                if td.is_dir():
                    sz = sum(f.stat().st_size for f in td.rglob("*") if f.is_file()) / (1024 * 1024)
                    task_sizes.append((td.name[:8], sz))

        st.markdown(f"""
        <div class="card card-sm">
            <div style="font-size:1.1rem;line-height:2.8;">
                <div>📂 <strong>{disk_tasks}</strong> task directories</div>
                <div>🎞️ <strong>{cache_count}</strong> cached video clips <span class="text-muted">({cache_size:.0f} MB)</span></div>
                <div>📼 <strong>{total_videos}</strong> final videos <span class="text-muted">({total_size:.1f} MB)</span></div>
                <div>✅ <strong>{success_rate:.0f}%</strong> success rate</div>
                <div>🟢 <strong>Online</strong> · Render Cloud</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if task_sizes:
            st.markdown("<h4 style='margin-top:16px;'>Per-Task Size</h4>", unsafe_allow_html=True)
            for tid, sz in task_sizes[:8]:
                st.markdown(f"""
                <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid {CARD_BORDER};">
                    <span style="font-family:monospace;color:{TEXT_SECONDARY};">{tid}</span>
                    <span style="font-weight:700;">{sz:.1f} MB</span>
                </div>
                """, unsafe_allow_html=True)

    # Tech stack section
    st.markdown("<br><h3>🛠️ Technology Stack</h3>", unsafe_allow_html=True)
    footage_tech = f"{source} + {ai_provider}" if source == "ai_image" else "Pexels API"

    st.markdown(f"""
    <div class="card card-sm">
        <table style="width:100%;font-size:1.05rem;line-height:2.6;">
            <tr><td style="color:{TEXT_SECONDARY};width:200px;">LLM</td><td style="font-weight:700;">DeepSeek Chat API</td></tr>
            <tr><td style="color:{TEXT_SECONDARY};">Text-to-Speech</td><td style="font-weight:700;">Microsoft Edge TTS (free)</td></tr>
            <tr><td style="color:{TEXT_SECONDARY};">Footage</td><td style="font-weight:700;">{footage_tech}</td></tr>
            <tr><td style="color:{TEXT_SECONDARY};">Video Composition</td><td style="font-weight:700;">moviepy 2.2.1 + ffmpeg zoompan</td></tr>
            <tr><td style="color:{TEXT_SECONDARY};">Encoding</td><td style="font-weight:700;">FFmpeg (libx264)</td></tr>
            <tr><td style="color:{TEXT_SECONDARY};">Subtitles</td><td style="font-weight:700;">Edge TTS timestamp sync</td></tr>
            <tr><td style="color:{TEXT_SECONDARY};">Framework</td><td style="font-weight:700;">Streamlit 1.58</td></tr>
            <tr><td style="color:{TEXT_SECONDARY};">Hosting</td><td style="font-weight:700;">Render Cloud (Docker)</td></tr>
        </table>
    </div>
    """, unsafe_allow_html=True)

# ── Footer ──────────────────────────────────────────────────
st.markdown(f"""
<div class="footer">
    <strong>MPT Dashboard</strong> &bull; Deployed on Render Cloud &bull; DeepSeek + Edge TTS + Pexels
    <br><span style="font-size:0.8rem;">{datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC</span>
</div>
""", unsafe_allow_html=True)
