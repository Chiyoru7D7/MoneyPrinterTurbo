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
    initial_sidebar_state="expanded",
)

# ── Color Palette (base: #77dd77) ──────────────────────────
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
    /* ── Global ── */
    .stApp {{
        background: {BG};
    }}
    .main .block-container {{
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        max-width: 1400px;
    }}

    /* ── Typography ── */
    h1, h2, h3, h4, h5, h6 {{
        color: {HEADING} !important;
        font-weight: 700 !important;
        letter-spacing: -0.02em;
    }}
    h1 {{ font-size: 2rem !important; }}
    h2 {{ font-size: 1.5rem !important; }}
    h3 {{ font-size: 1.2rem !important; }}
    p, li, label, span {{
        color: {TEXT_PRIMARY};
    }}
    .text-muted {{ color: {TEXT_MUTED}; font-size: 0.85rem; }}
    .text-secondary {{ color: {TEXT_SECONDARY}; }}

    /* ── Cards ── */
    .card {{
        background: {CARD_BG};
        border: 1px solid {CARD_BORDER};
        border-radius: 14px;
        padding: 28px;
        margin-bottom: 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.03);
        transition: box-shadow 0.2s;
    }}
    .card:hover {{
        box-shadow: 0 4px 12px rgba(0,0,0,0.06), 0 2px 4px rgba(0,0,0,0.04);
    }}
    .card-header {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 16px;
        padding-bottom: 14px;
        border-bottom: 2px solid {CARD_BORDER};
    }}
    .card-header h3 {{
        margin: 0;
        color: {HEADING} !important;
        font-size: 1.15rem !important;
    }}

    /* ── Stats Row ── */
    .stats-row {{
        display: flex;
        gap: 16px;
        margin-bottom: 24px;
        flex-wrap: wrap;
    }}
    .stat-box {{
        flex: 1;
        min-width: 160px;
        background: {CARD_BG};
        border: 1px solid {CARD_BORDER};
        border-radius: 12px;
        padding: 20px 24px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.03);
    }}
    .stat-box .stat-value {{
        font-size: 2.2rem;
        font-weight: 800;
        color: {HEADING};
        line-height: 1.1;
    }}
    .stat-box .stat-label {{
        font-size: 0.82rem;
        color: {TEXT_SECONDARY};
        margin-top: 4px;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }}
    .stat-box.accent {{
        border-left: 4px solid {ACCENT};
    }}
    .stat-box.accent .stat-value {{
        color: {ACCENT_DEEP};
    }}

    /* ── Pipeline ── */
    .pipeline {{
        display: flex;
        gap: 0;
        margin-bottom: 28px;
        background: {CARD_BG};
        border: 1px solid {CARD_BORDER};
        border-radius: 12px;
        overflow: hidden;
    }}
    .pipeline-step {{
        flex: 1;
        text-align: center;
        padding: 16px 8px;
        position: relative;
        background: {CARD_BG};
    }}
    .pipeline-step::after {{
        content: "→";
        position: absolute;
        right: -8px;
        top: 50%;
        transform: translateY(-50%);
        color: {CARD_BORDER};
        font-size: 1.2rem;
        font-weight: 700;
        z-index: 1;
    }}
    .pipeline-step:last-child::after {{
        content: "";
    }}
    .pipeline-step .step-icon {{
        font-size: 1.6rem;
        margin-bottom: 4px;
    }}
    .pipeline-step .step-name {{
        font-size: 0.75rem;
        font-weight: 700;
        color: {TEXT_PRIMARY};
    }}
    .pipeline-step .step-detail {{
        font-size: 0.65rem;
        color: {TEXT_MUTED};
    }}
    .pipeline-step.active {{
        background: {HIGHLIGHT_BG};
    }}
    .pipeline-step.active .step-name {{
        color: {ACCENT_DEEP};
    }}

    /* ── Video card ── */
    .video-card {{
        background: {CARD_BG};
        border: 1px solid {CARD_BORDER};
        border-radius: 14px;
        margin-bottom: 20px;
        overflow: hidden;
        box-shadow: 0 1px 3px rgba(0,0,0,0.03);
    }}
    .video-card-header {{
        padding: 20px 24px 12px 24px;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }}
    .video-card-body {{
        padding: 0 24px 20px 24px;
    }}

    /* ── Badges ── */
    .badge {{
        display: inline-flex;
        align-items: center;
        gap: 5px;
        padding: 5px 14px;
        border-radius: 20px;
        font-size: 0.78rem;
        font-weight: 600;
        letter-spacing: 0.02em;
    }}
    .badge-success {{
        background: #e8f5e9;
        color: {SUCCESS};
        border: 1px solid #c8e6c9;
    }}
    .badge-running {{
        background: #fff8e1;
        color: {RUNNING};
        border: 1px solid #ffecb3;
    }}
    .badge-failed {{
        background: #ffebee;
        color: {FAILED};
        border: 1px solid #ffcdd2;
    }}
    .badge-id {{
        background: {BG};
        color: {TEXT_SECONDARY};
        font-family: monospace;
        font-size: 0.75rem;
        padding: 3px 10px;
        border-radius: 6px;
    }}

    /* ── Buttons ── */
    .stButton > button {{
        background: {ACCENT} !important;
        color: {HEADING} !important;
        border: none !important;
        font-weight: 700 !important;
        border-radius: 10px !important;
        padding: 10px 24px !important;
        font-size: 0.95rem !important;
        transition: all 0.2s !important;
        letter-spacing: 0.01em;
    }}
    .stButton > button:hover {{
        background: {ACCENT_DARK} !important;
        color: white !important;
        box-shadow: 0 4px 12px rgba(119,221,119,0.35) !important;
        transform: translateY(-1px);
    }}

    /* ── Form inputs ── */
    .stTextInput > div > div > input {{
        border: 2px solid {CARD_BORDER} !important;
        border-radius: 10px !important;
        padding: 10px 14px !important;
        color: {TEXT_PRIMARY} !important;
        background: white !important;
    }}
    .stTextInput > div > div > input:focus {{
        border-color: {ACCENT} !important;
        box-shadow: 0 0 0 3px rgba(119,221,119,0.15) !important;
    }}
    .stSelectbox > div > div {{
        border: 2px solid {CARD_BORDER} !important;
        border-radius: 10px !important;
    }}

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {{
        background: #fafdfa !important;
        border-right: 2px solid {CARD_BORDER} !important;
    }}
    [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{
        color: {HEADING} !important;
    }}
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] li {{
        color: {TEXT_SECONDARY} !important;
    }}
    [data-testid="stSidebar"] .stDivider {{
        border-color: {CARD_BORDER};
    }}

    /* ── Expander ── */
    .streamlit-expanderHeader {{
        color: {TEXT_SECONDARY} !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
    }}

    /* ── Metrics override ── */
    [data-testid="stMetricValue"] {{
        color: {HEADING} !important;
        font-weight: 800 !important;
    }}
    [data-testid="stMetricLabel"] {{
        color: {TEXT_SECONDARY} !important;
    }}

    /* ── Info / Success / Error boxes ── */
    .stAlert {{
        border-radius: 10px !important;
        border: none !important;
        font-weight: 500;
    }}

    /* ── Divider ── */
    hr {{
        border-color: {CARD_BORDER} !important;
        margin: 24px 0 !important;
    }}

    /* ── Footer ── */
    .footer {{
        text-align: center;
        padding: 32px;
        color: {TEXT_MUTED};
        font-size: 0.8rem;
        border-top: 2px solid {CARD_BORDER};
        margin-top: 40px;
    }}
    .footer strong {{ color: {TEXT_SECONDARY}; }}

    /* ── Live dot ── */
    .live-dot {{
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: {ACCENT};
        animation: pulse 1.5s ease-in-out infinite;
        margin-right: 6px;
    }}
    @keyframes pulse {{
        0%, 100% {{ opacity: 1; }}
        50% {{ opacity: 0.4; }}
    }}

    /* ── Scrollbar ── */
    ::-webkit-scrollbar {{ width: 6px; }}
    ::-webkit-scrollbar-track {{ background: {BG}; }}
    ::-webkit-scrollbar-thumb {{ background: {CARD_BORDER}; border-radius: 3px; }}
    ::-webkit-scrollbar-thumb:hover {{ background: {ACCENT}; }}
</style>
""", unsafe_allow_html=True)

# ── Data layer ──────────────────────────────────────────────
STORAGE = Path(__file__).parent / "storage" / "tasks"
CACHE = Path(__file__).parent / "storage" / "cache_videos"
_THREAD_STORE = {}
_THREAD_LOCK = threading.Lock()

if "running_tasks" not in st.session_state:
    st.session_state.running_tasks = {}


def load_tasks():
    tasks = []
    if not STORAGE.exists():
        return tasks
    for task_dir in sorted(STORAGE.iterdir(), reverse=True):
        if not task_dir.is_dir():
            continue
        final_videos = list(task_dir.glob("final-*.mp4"))
        combined = list(task_dir.glob("combined-*.mp4"))
        subtitle = next(task_dir.glob("subtitle.srt"), None)
        audio = next(task_dir.glob("audio.mp3"), None)

        tasks.append({
            "id_short": task_dir.name[:8],
            "full_id": task_dir.name,
            "task_dir": str(task_dir),
            "final_videos": [str(v) for v in final_videos],
            "combined": [str(v) for v in combined],
            "subtitle": str(subtitle) if subtitle else None,
            "audio": str(audio) if audio else None,
            "video_count": len(final_videos),
            "modified": datetime.fromtimestamp(task_dir.stat().st_mtime),
            "success": len(final_videos) > 0,
        })
    return tasks


def get_video_size_mb(path):
    try:
        return os.path.getsize(path) / (1024 * 1024)
    except Exception:
        return 0


def _run_video_generation(task_id: str, subject: str, voice: str):
    try:
        from app.models.schema import VideoParams
        from app.services import task as task_service

        with _THREAD_LOCK:
            _THREAD_STORE[task_id] = {"status": "running", "error": None}

        params = VideoParams(
            video_subject=subject,
            voice_name=voice,
            video_aspect="9:16",
        )
        task_service.start(task_id, params, stop_at="video")

        with _THREAD_LOCK:
            _THREAD_STORE[task_id] = {"status": "done", "error": None}

    except Exception as e:
        with _THREAD_LOCK:
            _THREAD_STORE[task_id] = {"status": "error", "error": str(e)}


# Sync thread store → session state
with _THREAD_LOCK:
    for tid, tinfo in _THREAD_STORE.items():
        if tid not in st.session_state.running_tasks:
            st.session_state.running_tasks[tid] = tinfo
        else:
            st.session_state.running_tasks[tid].update(tinfo)

# ── Header ──────────────────────────────────────────────────
col_title, col_status = st.columns([4, 1])
with col_title:
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:14px;margin-bottom:4px;">
        <div style="font-size:2.4rem;">🎬</div>
        <div>
            <h1 style="margin:0;padding:0;">MPT Video Dashboard</h1>
            <p class="text-secondary" style="margin:2px 0 0 0;font-size:0.9rem;">
                AI-Powered Video Production Pipeline &bull; DeepSeek + Edge TTS + Pexels
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)

with col_status:
    st.markdown(f"""
    <div style="text-align:right;padding-top:10px;">
        <span class="live-dot"></span>
        <span style="color:{TEXT_SECONDARY};font-weight:600;font-size:0.85rem;">System Live</span>
        <br>
        <span class="text-muted" style="font-size:0.75rem;">Render Cloud</span>
    </div>
    """, unsafe_allow_html=True)

st.markdown('<hr>', unsafe_allow_html=True)

# ── Stats Row ───────────────────────────────────────────────
tasks = load_tasks()
total = len(tasks)
success_count = sum(1 for t in tasks if t["success"])
total_videos = sum(t["video_count"] for t in tasks)
total_size = sum(sum(get_video_size_mb(v) for v in t["final_videos"]) for t in tasks)
success_rate = (success_count / total * 100) if total > 0 else 0

st.markdown(f"""
<div class="stats-row">
    <div class="stat-box accent">
        <div class="stat-value">{total}</div>
        <div class="stat-label">Total Tasks</div>
    </div>
    <div class="stat-box accent">
        <div class="stat-value">{total_videos}</div>
        <div class="stat-label">Videos Generated</div>
    </div>
    <div class="stat-box accent">
        <div class="stat-value">{success_rate:.0f}%</div>
        <div class="stat-label">Success Rate</div>
    </div>
    <div class="stat-box accent">
        <div class="stat-value">{total_size:.1f} MB</div>
        <div class="stat-label">Total Output</div>
    </div>
    <div class="stat-box">
        <div class="stat-value" style="font-size:1.6rem;">DeepSeek</div>
        <div class="stat-label">LLM Engine</div>
    </div>
    <div class="stat-box">
        <div class="stat-value" style="font-size:1.6rem;">9:16</div>
        <div class="stat-label">Format</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Pipeline visualization ──────────────────────────────────
pipeline_steps = [
    ("🤖", "LLM Script", "DeepSeek Chat"),
    ("🔍", "Search Terms", "Keywords"),
    ("🎙️", "TTS Narration", "Edge TTS"),
    ("📥", "Stock Footage", "Pexels API"),
    ("🔗", "Clip Assembly", "moviepy"),
    ("📝", "Subtitles", "Edge Sync"),
    ("🎵", "Render", "FFmpeg"),
]

st.markdown('<div class="pipeline">', unsafe_allow_html=True)
for icon, name, detail in pipeline_steps:
    st.markdown(f"""
    <div class="pipeline-step">
        <div class="step-icon">{icon}</div>
        <div class="step-name">{name}</div>
        <div class="step-detail">{detail}</div>
    </div>
    """, unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# ── Running indicator ───────────────────────────────────────
running = {k: v for k, v in st.session_state.running_tasks.items() if v.get("status") in ("running", "starting")}
if running:
    st.markdown(f"""
    <div style="background:{HIGHLIGHT_BG};border:1px solid {ACCENT};border-radius:12px;padding:14px 20px;margin-bottom:20px;display:flex;align-items:center;gap:10px;">
        <span class="live-dot" style="background:{RUNNING};"></span>
        <span style="color:{TEXT_PRIMARY};font-weight:600;">Generating video in progress...</span>
        <span class="text-muted" style="margin-left:auto;">This takes 2–4 minutes on Render</span>
    </div>
    """, unsafe_allow_html=True)

# ── Video Gallery ───────────────────────────────────────────
st.markdown(f'<h2 style="margin-top:10px;">📼 Generated Videos</h2>', unsafe_allow_html=True)

if not tasks:
    st.markdown(f"""
    <div class="card" style="text-align:center;padding:48px;">
        <div style="font-size:3rem;margin-bottom:12px;">🎥</div>
        <h3 style="margin:0 0 8px 0;">No Videos Yet</h3>
        <p class="text-secondary" style="margin:0;">Use the sidebar to generate your first AI-powered video.</p>
    </div>
    """, unsafe_allow_html=True)

for task in tasks:
    with st.container():
        st.markdown('<div class="video-card">', unsafe_allow_html=True)

        # Header
        modified_str = task["modified"].strftime("%b %d, %Y · %H:%M UTC")
        if task["success"]:
            badge_html = f'<span class="badge badge-success">✓ Completed</span>'
        else:
            badge_html = f'<span class="badge badge-failed">✗ Failed</span>'

        size_str = ""
        if task["final_videos"]:
            size_mb = sum(get_video_size_mb(v) for v in task["final_videos"])
            size_str = f'<span class="text-muted"> · {size_mb:.1f} MB · {task["video_count"]} video(s)</span>'

        st.markdown(f"""
        <div class="video-card-header">
            <div>
                <span class="badge-id">{task['id_short']}</span>
                {badge_html}
                <span class="text-muted" style="margin-left:8px;">{modified_str}{size_str}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Video player
        if task["final_videos"]:
            st.markdown('<div class="video-card-body">', unsafe_allow_html=True)
            for vpath in task["final_videos"]:
                if os.path.exists(vpath):
                    st.video(vpath)
                    break
            st.markdown('</div>', unsafe_allow_html=True)

        # Files expander
        with st.expander("📁 View Task Files"):
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown(f"**🎬 Final Videos**")
                for v in task["final_videos"]:
                    st.code(os.path.basename(v), language=None)
            with c2:
                st.markdown(f"**🎵 Audio & Subtitles**")
                if task["audio"]:
                    st.caption(f"Audio: `{os.path.basename(task['audio'])}`")
                if task["subtitle"]:
                    st.caption(f"Subtitle: `{os.path.basename(task['subtitle'])}`")
            with c3:
                st.markdown(f"**📂 Directory**")
                st.caption(task["task_dir"])

        st.markdown('</div>', unsafe_allow_html=True)

# ── Sidebar ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🎬 MPT Console")
    st.markdown(f'<span class="text-muted">v1.3.0 · Render Cloud</span>', unsafe_allow_html=True)
    st.divider()

    # Quick stats
    st.markdown("### 📊 Pipeline Stats")
    st.markdown(f"""
    <div style="font-size:0.9rem;line-height:2;">
        <div><strong style="color:{TEXT_PRIMARY};">{total}</strong> <span class="text-secondary">tasks processed</span></div>
        <div><strong style="color:{TEXT_PRIMARY};">{success_count}/{total}</strong> <span class="text-secondary">successful</span></div>
        <div><strong style="color:{TEXT_PRIMARY};">{total_videos}</strong> <span class="text-secondary">videos output</span></div>
        <div><strong style="color:{TEXT_PRIMARY};">{total_size:.1f} MB</strong> <span class="text-secondary">total size</span></div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # Storage
    st.markdown("### 💾 Storage")
    cache_count = len(list(CACHE.glob("*.mp4"))) if CACHE.exists() else 0
    cache_size = sum(f.stat().st_size for f in CACHE.glob("*.mp4")) / (1024 * 1024) if CACHE.exists() else 0
    disk_tasks = len(list(STORAGE.iterdir())) if STORAGE.exists() else 0

    st.markdown(f"""
    <div style="font-size:0.85rem;line-height:2;">
        <div>📂 <strong>{disk_tasks}</strong> <span class="text-secondary">task directories</span></div>
        <div>🎞️ <strong>{cache_count}</strong> <span class="text-secondary">cached clips</span> <span class="text-muted">({cache_size:.0f} MB)</span></div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # Config
    st.markdown("### ⚙️ Active Config")
    try:
        from app.config.config import app as cfg
        llm = cfg.get("llm_provider", "deepseek")
        voice = cfg.get("voice_name", "en-US-JennyNeural")
        source = cfg.get("video_source", "pexels")
    except Exception:
        llm, voice, source = "deepseek", "en-US-JennyNeural", "pexels"

    st.markdown(f"""
    <div style="font-size:0.85rem;line-height:2.2;">
        <div>🤖 LLM: <strong style="color:{TEXT_PRIMARY};">{llm}</strong></div>
        <div>🎙️ TTS: <strong style="color:{TEXT_PRIMARY};">{voice}</strong></div>
        <div>📥 Footage: <strong style="color:{TEXT_PRIMARY};">{source}</strong></div>
        <div>📐 Format: <strong style="color:{TEXT_PRIMARY};">9:16 Portrait</strong></div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # New Task Form
    st.markdown("### 🚀 Generate New Video")

    with st.form("new_task_form"):
        topic = st.text_input(
            "Video Topic",
            placeholder="Describe your product or ad concept...",
            label_visibility="collapsed",
        )
        voice = st.selectbox(
            "Voice",
            [
                "en-US-JennyNeural",
                "en-US-GuyNeural",
                "en-US-AriaNeural",
                "en-US-DavisNeural",
                "zh-CN-XiaoxiaoNeural-Female",
            ],
        )
        submitted = st.form_submit_button(
            "⚡ Generate Video Now",
            type="primary",
            use_container_width=True,
        )

        if submitted and topic.strip():
            task_id = str(uuid.uuid4())
            st.session_state.running_tasks[task_id] = {"status": "starting", "error": None}
            t = threading.Thread(
                target=_run_video_generation,
                args=(task_id, topic.strip(), voice),
                daemon=True,
            )
            t.start()
            st.success(f"Task `{task_id[:8]}` launched! Check the gallery shortly.")
            st.rerun()

    # Recent activity
    recent = {k: v for k, v in st.session_state.running_tasks.items() if v.get("status") != "done"}
    if recent:
        st.divider()
        st.markdown("### ⏳ Recent Activity")
        for tid, tinfo in list(recent.items())[-5:]:
            s = tinfo.get("status", "?")
            icon = {"starting": "🟡", "running": "🔄", "error": "❌"}.get(s, "⚪")
            st.markdown(f"{icon} `{tid[:8]}` · *{s}*")
            if tinfo.get("error"):
                st.caption(f"⚠️ {tinfo['error'][:120]}")

# ── Footer ──────────────────────────────────────────────────
st.markdown(f"""
<div class="footer">
    <strong>MPT Dashboard</strong> &bull; Deployed on Render Cloud &bull; DeepSeek + Edge TTS + Pexels
    <br><span style="font-size:0.7rem;">{datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC</span>
</div>
""", unsafe_allow_html=True)
