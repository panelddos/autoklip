"""
🚀 Auto Video Clipper — FastAPI Server
Main entry point untuk backend
"""

import asyncio
import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl

from clipper import VideoClipper, ProcessResult

# ============================================================
# App Setup
# ============================================================

app = FastAPI(
    title="🎬 Auto Video Clipper",
    description="Otomatis memotong video YouTube menjadi klip viral dengan subtitle",
    version="1.0.0"
)

# CORS - izinkan frontend mengakses API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Untuk development. Di production, ganti dengan domain spesifik
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Output directory
OUTPUT_DIR = "./output"
TEMP_DIR = "./temp"
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# Mount static files untuk download
app.mount("/output", StaticFiles(directory=OUTPUT_DIR), name="output")

# Store job status
jobs = {}

# ============================================================
# Models
# ============================================================

class ClipRequest(BaseModel):
    youtube_url: str
    min_duration: Optional[int] = 15
    max_duration: Optional[int] = 90
    max_clips: Optional[int] = 5
    format_vertical: Optional[bool] = True
    video_quality: Optional[str] = "720"


class ClipInfo(BaseModel):
    filename: str
    start: float
    end: float
    duration: float
    score: float
    title: str
    reason: str
    has_subtitle: bool
    download_url: str
    start_formatted: str
    end_formatted: str


class JobStatus(BaseModel):
    job_id: str
    status: str  # "processing", "completed", "failed"
    progress: int  # 0-100
    message: str
    result: Optional[dict] = None


# ============================================================
# Helper Functions
# ============================================================

def format_time(seconds: float) -> str:
    """Format detik ke MM:SS atau HH:MM:SS"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


async def process_video_job(job_id: str, request: ClipRequest):
    """Background task untuk memproses video"""
    try:
        jobs[job_id] = {
            "status": "processing",
            "progress": 10,
            "message": "🔍 Menganalisis video..."
        }

        # Inisialisasi clipper
        clipper = VideoClipper(
            output_dir=OUTPUT_DIR,
            temp_dir=TEMP_DIR,
            min_clip_duration=request.min_duration,
            max_clip_duration=request.max_duration,
            max_clips=request.max_clips,
            video_quality=request.video_quality
        )

        jobs[job_id]["progress"] = 20
        jobs[job_id]["message"] = "📥 Downloading video..."

        # Proses video (ini blocking, jalankan di thread pool)
        loop = asyncio.get_event_loop()
        result: ProcessResult = await loop.run_in_executor(
            None,
            lambda: clipper.process(request.youtube_url, request.format_vertical)
        )

        if result.success:
            clips_data = []
            for clip in result.clips:
                clips_data.append({
                    "filename": clip.filename,
                    "start": clip.start,
                    "end": clip.end,
                    "duration": round(clip.duration, 1),
                    "score": clip.score,
                    "title": clip.title,
                    "reason": clip.reason,
                    "has_subtitle": clip.has_subtitle,
                    "download_url": f"/output/{clip.filename}",
                    "start_formatted": format_time(clip.start),
                    "end_formatted": format_time(clip.end)
                })

            jobs[job_id] = {
                "status": "completed",
                "progress": 100,
                "message": result.message,
                "result": {
                    "video_title": result.video_title,
                    "video_duration": result.video_duration,
                    "video_duration_formatted": format_time(result.video_duration),
                    "total_clips": len(clips_data),
                    "clips": clips_data
                }
            }
        else:
            jobs[job_id] = {
                "status": "failed",
                "progress": 0,
                "message": result.message,
                "result": {"error": result.error}
            }

    except Exception as e:
        jobs[job_id] = {
            "status": "failed",
            "progress": 0,
            "message": f"Error: {str(e)}",
            "result": {"error": str(e)}
        }


# ============================================================
# API Endpoints
# ============================================================

@app.get("/")
async def root():
    return {"message": "🎬 Auto Video Clipper API", "status": "online"}


@app.post("/api/clip")
async def create_clip_job(request: ClipRequest, background_tasks: BackgroundTasks):
    """
    🎬 Mulai proses clipping video.
    Mengembalikan job_id untuk tracking progress.
    """
    # Validasi URL
    if "youtube.com" not in request.youtube_url and "youtu.be" not in request.youtube_url:
        raise HTTPException(status_code=400, detail="URL harus dari YouTube!")

    # Buat job
    job_id = str(uuid.uuid4())[:12]
    jobs[job_id] = {
        "status": "processing",
        "progress": 0,
        "message": "⏳ Memulai proses..."
    }

    # Jalankan di background
    background_tasks.add_task(process_video_job, job_id, request)

    return {"job_id": job_id, "message": "Proses dimulai! Gunakan /api/status/{job_id} untuk cek progress."}


@app.get("/api/status/{job_id}")
async def get_job_status(job_id: str):
    """📊 Cek status & progress job"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job tidak ditemukan")
    return jobs[job_id]


@app.get("/api/download/{filename}")
async def download_clip(filename: str):
    """📥 Download file klip"""
    filepath = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
    return FileResponse(
        filepath,
        media_type="video/mp4",
        filename=filename
    )


@app.delete("/api/cleanup/{job_id}")
async def cleanup_job(job_id: str):
    """🗑️ Hapus file temporary dari job"""
    if job_id in jobs:
        del jobs[job_id]
    return {"message": "Cleanup done"}


@app.get("/api/health")
async def health_check():
    """❤️ Health check"""
    # Cek dependencies
    import shutil
    checks = {
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "yt-dlp": shutil.which("yt-dlp") is not None,
    }
    all_ok = all(checks.values())
    return {
        "status": "healthy" if all_ok else "degraded",
        "checks": checks
    }


# ============================================================
# Run Server
# ============================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
