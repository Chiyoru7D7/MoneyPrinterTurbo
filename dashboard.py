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

# Ensure MPT modules are importable
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger

st.set_page_config(
    page_title="MPT Video Dashboard",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Dark theme ──────────────────────────────────────────────
st.markdown("""
<style>
    .main { background: #0d1117; }
    .stMetric { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 20px; }
    .stMetric label { color: #8b949e !important; }
    .stMetric [data-testid="stMetricValue"] { color: #e6edf3 !important; font-size: 2rem !important; }
    .video-card { background: #161b22; border: 1px solid #30363d; border-radius: 16px; padding: 24px; margin-bottom: 20px; }
    .video-card h3 { color: #58a6ff; margin: 0 0 8px 0; }
    .video-card .meta { color: #8b949e; font-size: 0.85rem; }
    .video-card .script { color: #c9d1d9; background: #0d1117; padding: 16px; border-radius: 8px; margin: 12px 0; font-style: italic; border-left: 3px solid #58a6ff; }
    .tag { display: inline-block; background: #1f6feb22; color: #58a6ff; border: 1px solid #1f6feb44; border-radius: 20px; padding: 4px 12px; margin: 2px; font-size: 0.8rem; }
    .status-badge { display: inline-block; padding: 4px 14px; border-radius: 20px; font-size: 0.82rem; font-weight: 600; }
    .status-success { background: #23863622; color: #3fb950; border: 1px solid #23863644; }
    .status-running { background: #d2992222; color: #e3b341; border: 1px solid #d2992244; }
    .status-failed { background: #da363322; color: #f85149; border: 1px solid #da363344; }
    .section-title { color: #e6edf3; font-size: 1.3rem; font-weight: 700; margin: 32px 0 16px 0; padding-bottom: 8px; border-bottom: 2px solid #30363d; }
    .live-log { background: #0d1117; color: #3fb950; font-family: monospace; padding: 10px 16px; border-radius: 8px; border: 1px solid #23863644; max-height: 200px; overflow-y: auto; font-size: 0.8rem; }
</style>
""", unsafe_allow_html=True)

# ── Data layer ──────────────────────────────────────────────
STORAGE = Path(__file__).parent / "storage" / "tasks"
CACHE = Path(__file__).parent / "storage" / "cache_videos"

# ── Session state ───────────────────────────────────────────
if "running_tasks" not in st.session_state:
    st.session_state.running_tasks = {}  # {task_id: {"status": "running|done|error", "log": [], "result": None}}

# Thread-safe global store for background threads (st.session_state inaccessible from threads)
_THREAD_STORE = {}
_THREAD_LOCK = threading.Lock()


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
            "id": task_dir.name[:8] + "...",
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


def _run_video_generation(task_id: str, subject: str, voice_name: str):
    """Background thread: generate a video via MPT task service."""
    try:
        from app.models.schema import VideoParams
        from app.services import task as task_service

        with _THREAD_LOCK:
            _THREAD_STORE[task_id] = {"status": "running", "error": None}

        params = VideoParams(
            video_subject=subject,
            voice_name=voice_name,
            video_aspect="9:16",
        )
        task_service.start(task_id, params, stop_at="video")

        with _THREAD_LOCK:
            _THREAD_STORE[task_id] = {"status": "done", "error": None}

    except Exception as e:
        with _THREAD_LOCK:
            _THREAD_STORE[task_id] = {"status": "error", "error": str(e)}


# ── Header ──────────────────────────────────────────────────
col1, col2, col3 = st.columns([3, 1, 1])
with col1:
    st.markdown("# 🎬 MPT Video Dashboard")
    st.markdown("##### AI-Powered Video Production Pipeline")
with col2:
    tasks = load_tasks()
    total = len(tasks)
    success = sum(1 for t in tasks if t["success"])
    st.metric("Total Tasks", total)
with col3:
    total_videos = sum(t["video_count"] for t in tasks)
    total_size = sum(
        sum(get_video_size_mb(v) for v in t["final_videos"]) for t in tasks
    )
    st.metric("Videos Generated", f"{total_videos}")

# ── Pipeline Visualization ──────────────────────────────────
st.markdown('<div class="section-title">⚙️ Pipeline Flow</div>', unsafe_allow_html=True)

steps = [
    ("🤖", "LLM Script", "DeepSeek Chat"),
    ("🔍", "Search Terms", "Keyword extraction"),
    ("🎙️", "TTS Narration", "Edge TTS"),
    ("📥", "Stock Footage", "Pexels API"),
    ("🔗", "Clip Assembly", "moviepy + FFmpeg"),
    ("📝", "Subtitles", "Edge timestamp"),
    ("🎵", "BGM + Render", "Final MP4"),
]
cols = st.columns(len(steps))
for i, (icon, name, detail) in enumerate(steps):
    with cols[i]:
        st.markdown(f"""
        <div style="text-align:center; padding:8px 4px;">
            <div style="font-size:1.5rem;">{icon}</div>
            <div style="color:#e6edf3; font-weight:600; font-size:0.8rem;">{name}</div>
            <div style="color:#8b949e; font-size:0.65rem;">{detail}</div>
        </div>
        """, unsafe_allow_html=True)

# ── Live running tasks ──────────────────────────────────────
# Merge thread store into session state for UI display
with _THREAD_LOCK:
    for tid, tinfo in _THREAD_STORE.items():
        if tid not in st.session_state.running_tasks:
            st.session_state.running_tasks[tid] = tinfo
        else:
            st.session_state.running_tasks[tid].update(tinfo)

running = {k: v for k, v in st.session_state.running_tasks.items() if v.get("status") in ("running", "starting")}
if running:
    st.markdown('<div class="section-title">🔄 Generating Now</div>', unsafe_allow_html=True)
    for tid, tinfo in running.items():
        st.markdown(f"""
        <div style="padding:12px 20px; background:#161b22; border:1px solid #d2992244; border-radius:8px; margin-bottom:8px;">
            <span class="status-badge status-running">⏳ GENERATING</span>
            <span style="color:#e6edf3; margin-left:8px;">Task <code>{tid[:8]}...</code></span>
            <span style="color:#8b949e; margin-left:12px; font-size:0.85rem;">This takes 2-4 min on Render free tier</span>
        </div>
        """, unsafe_allow_html=True)

# ── Video Gallery ───────────────────────────────────────────
st.markdown('<div class="section-title">📼 Generated Videos</div>', unsafe_allow_html=True)

tasks = load_tasks()

if not tasks:
    st.info("No videos yet. Use the sidebar to generate your first video! 🚀")

for task in tasks:
    with st.container():
        st.markdown('<div class="video-card">', unsafe_allow_html=True)

        c1, c2 = st.columns([4, 1])
        with c1:
            status_class = "status-success" if task["success"] else "status-failed"
            status_text = "✓ COMPLETED" if task["success"] else "✗ FAILED"
            st.markdown(f"""
            <h3>Task {task['id']}</h3>
            <span class="status-badge {status_class}">{status_text}</span>
            <span class="meta"> • {task['modified'].strftime('%Y-%m-%d %H:%M UTC')} • {task['video_count']} video(s)</span>
            """, unsafe_allow_html=True)
        with c2:
            if task["final_videos"]:
                size_mb = sum(get_video_size_mb(v) for v in task["final_videos"])
                st.metric("Output", f"{size_mb:.1f} MB")

        # Video player
        if task["final_videos"]:
            for vpath in task["final_videos"]:
                if os.path.exists(vpath):
                    st.video(vpath)
                    break

        # Files
        with st.expander("📁 Task Files"):
            f1, f2, f3 = st.columns(3)
            with f1:
                st.markdown("**Final Videos**")
                for v in task["final_videos"]:
                    st.code(v, language=None)
            with f2:
                st.markdown("**Artifacts**")
                if task["audio"]:
                    st.markdown(f"🎵 Audio: `{task['audio']}`")
                if task["subtitle"]:
                    st.markdown(f"📝 Subtitle: `{task['subtitle']}`")
            with f3:
                st.markdown("**Directory**")
                st.code(task["task_dir"], language=None)

        st.markdown('</div>', unsafe_allow_html=True)

# ── Sidebar ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🎬 MoneyPrinterTurbo")
    st.markdown("*v1.3.0 — Cloud Edition*")
    st.divider()

    st.markdown("### 📊 Quick Stats")
    st.markdown(f"- **{total}** tasks processed")
    st.markdown(f"- **{success}/{total}** successful")
    st.markdown(f"- **{total_videos}** videos output")
    if total > 0:
        rate = (success / total) * 100
        st.markdown(f"- **{rate:.0f}%** success rate")

    st.divider()
    st.markdown("### 🗂️ Storage")
    cache_count = len(list(CACHE.glob("*.mp4"))) if CACHE.exists() else 0
    cache_size = sum(f.stat().st_size for f in CACHE.glob("*.mp4")) / (1024 * 1024) if CACHE.exists() else 0
    disk_tasks = len(list(STORAGE.iterdir())) if STORAGE.exists() else 0
    st.markdown(f"- {disk_tasks} task directories")
    st.markdown(f"- {cache_count} cached clips ({cache_size:.0f} MB)")

    st.divider()
    st.markdown("### 🔧 Active Config")
    from app.config.config import app as cfg
    llm = cfg.get("llm_provider", "deepseek")
    voice = cfg.get("voice_name", "en-US-JennyNeural")
    source = cfg.get("video_source", "pexels")
    st.markdown(f"- **LLM**: {llm}")
    st.markdown(f"- **TTS**: Edge TTS ({voice})")
    st.markdown(f"- **Footage**: {source}")
    st.markdown(f"- **Format**: 9:16 Portrait")

    st.divider()
    st.markdown("### 🚀 New Task")
    st.caption("Generate a video directly on the cloud.")

    with st.form("new_task_form"):
        topic = st.text_input(
            "Video Topic",
            placeholder="e.g. New eco-friendly sneakers made from bamboo...",
        )
        voice = st.selectbox(
            "Voice",
            ["en-US-JennyNeural", "en-US-GuyNeural", "en-US-AriaNeural",
             "en-US-DavisNeural", "zh-CN-XiaoxiaoNeural-Female"],
        )
        submitted = st.form_submit_button("⚡ Generate Video", type="primary", use_container_width=True)

        if submitted and topic.strip():
            task_id = str(uuid.uuid4())
            st.session_state.running_tasks[task_id] = {"status": "starting", "error": None}
            t = threading.Thread(
                target=_run_video_generation,
                args=(task_id, topic.strip(), voice),
                daemon=True,
            )
            t.start()
            st.session_state.running_tasks[task_id]["thread"] = t
            st.success(f"✅ Task `{task_id[:8]}...` started! Generating...")
            st.caption("Page will auto-refresh. Watch the gallery for your video.")
            st.rerun()

    # ── Running task status ──
    recent = {k: v for k, v in st.session_state.running_tasks.items() if v["status"] != "done"}
    if recent:
        st.divider()
        st.markdown("### ⏳ Recent Tasks")
        for tid, tinfo in list(recent.items())[-5:]:
            icon = {"starting": "🟡", "running": "🔄", "error": "❌"}.get(tinfo["status"], "⚪")
            st.markdown(f"{icon} `{tid[:8]}...` — *{tinfo['status']}*")
            if tinfo.get("error"):
                st.caption(f"Error: {tinfo['error']}")

st.markdown("""<div style="text-align:center; color:#30363d; padding:20px; font-size:0.8rem;">
    MPT Dashboard • Deployed on Render • DeepSeek + Edge TTS + Pexels
</div>""", unsafe_allow_html=True)
