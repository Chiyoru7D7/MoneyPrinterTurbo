"""
MoneyPrinterTurbo — Professional Video Production Dashboard
Run: streamlit run dashboard.py
"""
import streamlit as st
import os
import json
import glob
from datetime import datetime
from pathlib import Path

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
    .status-failed { background: #da363322; color: #f85149; border: 1px solid #da363344; }
    .section-title { color: #e6edf3; font-size: 1.3rem; font-weight: 700; margin: 32px 0 16px 0; padding-bottom: 8px; border-bottom: 2px solid #30363d; }
    .pipeline-step { padding: 10px 16px; margin: 4px 0; border-radius: 8px; background: #161b22; border: 1px solid #21262d; }
    .pipeline-step .check { color: #3fb950; }
</style>
""", unsafe_allow_html=True)

# ── Data layer ──────────────────────────────────────────────
STORAGE = Path(__file__).parent / "storage" / "tasks"
CACHE = Path(__file__).parent / "storage" / "cache_videos"

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

        # Read script.txt if exists
        script_txt = ""
        script_file = task_dir / "script.txt"
        if script_file.exists():
            script_txt = script_file.read_text(encoding="utf-8")

        tasks.append({
            "id": task_dir.name[:8] + "...",
            "full_id": task_dir.name,
            "task_dir": str(task_dir),
            "final_videos": [str(v) for v in final_videos],
            "combined": [str(v) for v in combined],
            "subtitle": str(subtitle) if subtitle else None,
            "audio": str(audio) if audio else None,
            "script": script_txt,
            "video_count": len(final_videos),
            "modified": datetime.fromtimestamp(task_dir.stat().st_mtime),
            "success": len(final_videos) > 0,
        })
    return tasks

def get_video_size_mb(path):
    try:
        return os.path.getsize(path) / (1024 * 1024)
    except:
        return 0

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
    st.metric("Videos Generated", f"{total_videos}  ({total_size:.1f} MB)")

# ── Pipeline Visualization ──────────────────────────────────
st.markdown('<div class="section-title">⚙️ Pipeline Flow</div>', unsafe_allow_html=True)

steps = [
    ("🤖", "LLM Script", "DeepSeek Chat"),
    ("🔍", "Search Terms", "Keyword extraction"),
    ("🎙️", "TTS Narration", "Edge TTS / Azure"),
    ("📥", "Stock Footage", "Pexels API"),
    ("🔗", "Clip Assembly", "moviepy + FFmpeg"),
    ("📝", "Subtitles", "Edge timestamp"),
    ("🎵", "BGM + Render", "Final MP4 output"),
]
cols = st.columns(len(steps))
for i, (icon, name, detail) in enumerate(steps):
    with cols[i]:
        st.markdown(f"""
        <div style="text-align:center; padding:12px 4px;">
            <div style="font-size:1.8rem;">{icon}</div>
            <div style="color:#e6edf3; font-weight:600; font-size:0.85rem;">{name}</div>
            <div style="color:#8b949e; font-size:0.7rem;">{detail}</div>
        </div>
        """, unsafe_allow_html=True)
    if i < len(steps) - 1:
        cols[i].markdown('<div style="text-align:right; color:#30363d; font-size:1.5rem; margin-top:-40px;">→</div>', unsafe_allow_html=True)

# ── Video Gallery ───────────────────────────────────────────
st.markdown('<div class="section-title">📼 Generated Videos</div>', unsafe_allow_html=True)

tasks = load_tasks()

if not tasks:
    st.info("No videos generated yet. Run the CLI to create your first video!")

for task in tasks:
    with st.container():
        st.markdown(f'<div class="video-card">', unsafe_allow_html=True)

        # Header row
        c1, c2 = st.columns([4, 1])
        with c1:
            status_class = "status-success" if task["success"] else "status-failed"
            status_text = "✓ COMPLETED" if task["success"] else "✗ FAILED"
            st.markdown(f"""
            <h3>Task {task['id']}</h3>
            <span class="status-badge {status_class}">{status_text}</span>
            <span class="meta"> • {task['modified'].strftime('%Y-%m-%d %H:%M')} • {task['video_count']} video(s)</span>
            """, unsafe_allow_html=True)
        with c2:
            if task["final_videos"]:
                size_mb = sum(get_video_size_mb(v) for v in task["final_videos"])
                st.metric("Output", f"{size_mb:.1f} MB")

        # Script preview
        if task["script"]:
            st.markdown(f'<div class="script">📝 {task["script"][:300]}{"..." if len(task["script"]) > 300 else ""}</div>', unsafe_allow_html=True)

        # Video player
        if task["final_videos"]:
            for vpath in task["final_videos"]:
                if os.path.exists(vpath):
                    st.video(vpath)
                    break  # Show first video only per task

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
                    st.code(f"🎵 {task['audio']}", language=None)
                if task["subtitle"]:
                    st.code(f"📝 {task['subtitle']}", language=None)
            with f3:
                st.markdown("**Combined Clips**")
                for c in task["combined"]:
                    st.code(c, language=None)

        st.markdown('</div>', unsafe_allow_html=True)

# ── Sidebar ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🎬 MoneyPrinterTurbo")
    st.markdown("*v1.3.0*")
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
    cache_size = sum(f.stat().st_size for f in CACHE.glob("*.mp4")) / (1024*1024) if CACHE.exists() else 0
    st.markdown(f"- {cache_count} cached videos ({cache_size:.0f} MB)")
    task_count = len(list(STORAGE.iterdir())) if STORAGE.exists() else 0
    st.markdown(f"- {task_count} task directories")

    st.divider()
    st.markdown("### 🔧 Config")
    st.markdown("- **LLM**: DeepSeek Chat")
    st.markdown("- **TTS**: Edge TTS (free)")
    st.markdown("- **Footage**: Pexels")
    st.markdown("- **Format**: 9:16 Portrait")

    st.divider()
    st.markdown("### 🚀 New Task")
    with st.form("new_task"):
        topic = st.text_input("Video Topic", placeholder="e.g. Product launch ad...")
        voice = st.selectbox("Voice", ["en-US-JennyNeural", "en-US-GuyNeural", "zh-CN-XiaoxiaoNeural-Female"])
        submit = st.form_submit_button("Generate Video")
        if submit and topic:
            st.info(f"Run: `python cli.py --video-subject '{topic}' --voice-name '{voice}' --video-aspect '9:16'`")

st.markdown("""<div style="text-align:center; color:#30363d; padding:40px; font-size:0.8rem;">
    MoneyPrinterTurbo Dashboard • Powered by DeepSeek + Edge TTS + Pexels
</div>""", unsafe_allow_html=True)
