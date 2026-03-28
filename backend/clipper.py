"""
✂️ Video Clipper Engine
Download video & potong menjadi klip viral dengan subtitle
"""

import os
import re
import subprocess
import uuid
from dataclasses import dataclass
from typing import List, Optional

from subtitle_handler import SubtitleHandler
from viral_detector import SubtitleSegment, ViralClip, ViralDetector, format_timestamp


@dataclass
class ClipResult:
    """Hasil satu klip"""
    filename: str
    filepath: str
    start: float
    end: float
    duration: float
    score: float
    title: str
    reason: str
    has_subtitle: bool
    download_url: str = ""


@dataclass
class ProcessResult:
    """Hasil keseluruhan proses"""
    success: bool
    video_title: str
    video_duration: float
    clips: List[ClipResult]
    message: str
    error: Optional[str] = None


class VideoClipper:
    """
    Engine utama: download video → analisis → potong → burn subtitle
    """

    def __init__(
        self,
        output_dir: str = "./output",
        temp_dir: str = "./temp",
        min_clip_duration: int = 15,
        max_clip_duration: int = 90,
        max_clips: int = 5,
        video_quality: str = "720"
    ):
        self.output_dir = output_dir
        self.temp_dir = temp_dir
        self.min_clip_duration = min_clip_duration
        self.max_clip_duration = max_clip_duration
        self.max_clips = max_clips
        self.video_quality = video_quality

        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(temp_dir, exist_ok=True)

        self.subtitle_handler = SubtitleHandler(temp_dir)
        self.viral_detector = ViralDetector(
            min_clip_duration=min_clip_duration,
            max_clip_duration=max_clip_duration,
            top_n_clips=max_clips
        )

    def _extract_video_id(self, url: str) -> str:
        """Extract video ID dari URL YouTube"""
        patterns = [
            r"(?:v=|\/)([0-9A-Za-z_-]{11}).*",
            r"(?:youtu\.be\/)([0-9A-Za-z_-]{11})",
            r"(?:embed\/)([0-9A-Za-z_-]{11})",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return str(uuid.uuid4())[:11]

    def _get_video_info(self, url: str) -> dict:
        """Dapatkan info video (judul, durasi, dll)"""
        try:
            cmd = [
                "yt-dlp",
                "--dump-json",
                "--no-download",
                url
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                import json
                info = json.loads(result.stdout)
                return {
                    "title": info.get("title", "Unknown"),
                    "duration": info.get("duration", 0),
                    "channel": info.get("channel", "Unknown"),
                    "view_count": info.get("view_count", 0),
                }
        except Exception as e:
            print(f"⚠️ Error getting video info: {e}")

        return {"title": "Unknown", "duration": 0, "channel": "Unknown", "view_count": 0}

    def _download_video(self, url: str, video_id: str) -> Optional[str]:
        """Download video dari YouTube"""
        output_path = os.path.join(self.temp_dir, f"{video_id}.mp4")

        if os.path.exists(output_path):
            print("📦 Video sudah ada di cache, skip download")
            return output_path

        try:
            print(f"📥 Downloading video (max {self.video_quality}p)...")
            cmd = [
                "yt-dlp",
                "-f", f"bestvideo[height<={self.video_quality}][ext=mp4]+bestaudio[ext=m4a]/best[height<={self.video_quality}][ext=mp4]/best",
                "--merge-output-format", "mp4",
                "-o", output_path,
                url
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode == 0 and os.path.exists(output_path):
                print("✅ Video berhasil di-download!")
                return output_path
            else:
                print(f"❌ Download gagal: {result.stderr[:200]}")
                return None

        except subprocess.TimeoutExpired:
            print("❌ Download timeout (>5 menit)")
            return None
        except Exception as e:
            print(f"❌ Error download: {e}")
            return None

    def _cut_video_with_subtitle(
        self,
        source_video: str,
        output_path: str,
        start: float,
        end: float,
        subtitle_segments: List[SubtitleSegment],
        format_9_16: bool = True
    ) -> bool:
        """
        Potong video dan burn subtitle langsung.
        Option: convert ke format 9:16 (vertical) untuk TikTok/Reels/Shorts
        """
        duration = end - start

        # Buat SRT subtitle untuk klip ini (adjust timestamp relatif ke start)
        adjusted_segments = []
        for seg in subtitle_segments:
            if seg.start >= start and seg.end <= end + 1:
                adjusted_segments.append(SubtitleSegment(
                    start=max(0, seg.start - start),
                    end=min(duration, seg.end - start),
                    text=seg.text
                ))

        srt_path = output_path.replace(".mp4", ".srt")
        self.subtitle_handler.segments_to_srt(adjusted_segments, srt_path)

        try:
            # Escape path untuk FFmpeg subtitle filter
            srt_escaped = srt_path.replace("\\", "/").replace(":", "\\:")

            # Subtitle style (mirip style TikTok/Reels)
            subtitle_style = (
                "FontName=Arial,FontSize=14,PrimaryColour=&H00FFFFFF,"
                "OutlineColour=&H00000000,BackColour=&H80000000,"
                "Bold=1,Outline=2,Shadow=1,MarginV=40"
            )

            if format_9_16:
                # Convert ke 9:16 (vertical) dengan crop center
                filter_complex = (
                    f"[0:v]crop=ih*9/16:ih:(iw-ih*9/16)/2:0,"
                    f"scale=1080:1920:force_original_aspect_ratio=decrease,"
                    f"pad=1080:1920:(1080-iw)/2:(1920-ih)/2:black,"
                    f"subtitles='{srt_escaped}':force_style='{subtitle_style}'[v]"
                )
            else:
                # Keep original aspect ratio
                filter_complex = (
                    f"[0:v]subtitles='{srt_escaped}':force_style='{subtitle_style}'[v]"
                )

            cmd = [
                "ffmpeg", "-y",
                "-ss", str(start),
                "-i", source_video,
                "-t", str(duration),
                "-filter_complex", filter_complex,
                "-map", "[v]", "-map", "0:a?",
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart",
                output_path
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)

            if result.returncode == 0 and os.path.exists(output_path):
                return True
            else:
                print(f"⚠️ FFmpeg error, mencoba tanpa subtitle...")
                # Fallback: potong tanpa subtitle
                return self._cut_video_simple(source_video, output_path, start, duration, format_9_16)

        except Exception as e:
            print(f"⚠️ Error cutting video: {e}")
            return self._cut_video_simple(source_video, output_path, start, duration, format_9_16)

    def _cut_video_simple(self, source: str, output: str, start: float, duration: float, format_9_16: bool) -> bool:
        """Potong video sederhana tanpa subtitle (fallback)"""
        try:
            if format_9_16:
                cmd = [
                    "ffmpeg", "-y",
                    "-ss", str(start), "-i", source, "-t", str(duration),
                    "-vf", "crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(1080-iw)/2:(1920-ih)/2:black",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                    "-c:a", "aac", "-b:a", "128k",
                    output
                ]
            else:
                cmd = [
                    "ffmpeg", "-y",
                    "-ss", str(start), "-i", source, "-t", str(duration),
                    "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                    "-c:a", "aac", "-b:a", "128k",
                    output
                ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            return result.returncode == 0 and os.path.exists(output)

        except Exception as e:
            print(f"❌ Error simple cut: {e}")
            return False

    def process(self, youtube_url: str, format_vertical: bool = True) -> ProcessResult:
        """
        🎬 Proses utama: URL → Download → Analisis → Potong → Output

        Args:
            youtube_url: Link YouTube
            format_vertical: True untuk 9:16 (TikTok/Reels), False untuk original

        Returns:
            ProcessResult dengan daftar klip yang berhasil dibuat
        """
        video_id = self._extract_video_id(youtube_url)
        session_id = str(uuid.uuid4())[:8]

        print(f"\n{'='*60}")
        print(f"🎬 AUTO CLIPPER - Processing: {youtube_url}")
        print(f"{'='*60}\n")

        # Step 1: Get video info
        print("📋 Step 1: Mengambil info video...")
        info = self._get_video_info(youtube_url)
        print(f"   Title: {info['title']}")
        print(f"   Duration: {info['duration']}s")

        # Step 2: Download subtitle
        print("\n📝 Step 2: Mengambil subtitle...")
        segments = self.subtitle_handler.get_youtube_subtitles(youtube_url, video_id)

        # Step 3: Download video
        print("\n📥 Step 3: Download video...")
        video_path = self._download_video(youtube_url, video_id)

        if not video_path:
            return ProcessResult(
                success=False,
                video_title=info["title"],
                video_duration=info["duration"],
                clips=[],
                message="Gagal download video",
                error="Download failed. Video mungkin restricted atau terlalu besar."
            )

        # Step 3b: Generate subtitle via Whisper jika tidak ada
        if not segments:
            print("\n🎤 Step 3b: Generate subtitle via Whisper AI...")
            segments = self.subtitle_handler.generate_whisper_subtitles(video_path)

        if not segments:
            return ProcessResult(
                success=False,
                video_title=info["title"],
                video_duration=info["duration"],
                clips=[],
                message="Tidak bisa mendapatkan subtitle",
                error="Video tidak punya subtitle dan Whisper AI gagal. Coba video lain yang sudah ada subtitle-nya."
            )

        print(f"   ✅ {len(segments)} subtitle segments ditemukan")

        # Step 4: Deteksi momen viral
        print("\n🧠 Step 4: Menganalisis momen viral...")
        viral_clips = self.viral_detector.detect(segments)
        print(f"   ✅ {len(viral_clips)} momen viral terdeteksi!")

        for i, vc in enumerate(viral_clips):
            print(f"   [{i+1}] {format_timestamp(vc.start)} - {format_timestamp(vc.end)} | Score: {vc.score} | {vc.title_suggestion[:50]}")

        # Step 5: Potong video
        print(f"\n✂️ Step 5: Memotong {len(viral_clips)} klip...")
        clip_results = []

        for i, vc in enumerate(viral_clips):
            clip_filename = f"clip_{session_id}_{i+1}.mp4"
            clip_path = os.path.join(self.output_dir, clip_filename)

            print(f"   [{i+1}/{len(viral_clips)}] Cutting {format_timestamp(vc.start)} - {format_timestamp(vc.end)}...")

            success = self._cut_video_with_subtitle(
                source_video=video_path,
                output_path=clip_path,
                start=vc.start,
                end=vc.end,
                subtitle_segments=vc.subtitle_segments,
                format_9_16=format_vertical
            )

            if success:
                duration = vc.end - vc.start
                clip_results.append(ClipResult(
                    filename=clip_filename,
                    filepath=clip_path,
                    start=vc.start,
                    end=vc.end,
                    duration=duration,
                    score=vc.score,
                    title=vc.title_suggestion,
                    reason=vc.reason,
                    has_subtitle=True,
                    download_url=f"/download/{clip_filename}"
                ))
                print(f"   ✅ Clip {i+1} berhasil!")
            else:
                print(f"   ❌ Clip {i+1} gagal")

        # Cleanup temp files (optional)
        print(f"\n{'='*60}")
        print(f"🎉 Selesai! {len(clip_results)}/{len(viral_clips)} klip berhasil dibuat")
        print(f"{'='*60}\n")

        return ProcessResult(
            success=len(clip_results) > 0,
            video_title=info["title"],
            video_duration=info["duration"],
            clips=clip_results,
            message=f"Berhasil membuat {len(clip_results)} klip viral dari '{info['title']}'"
        )


    def cleanup(self, session_id: str = None):
        """Bersihkan file temporary"""
        import glob

        if session_id:
            # Cleanup specific session
            for f in glob.glob(os.path.join(self.output_dir, f"clip_{session_id}_*")):
                os.remove(f)
        else:
            # Cleanup temp dir
            for f in glob.glob(os.path.join(self.temp_dir, "*")):
                try:
                    os.remove(f)
                except:
                    pass
