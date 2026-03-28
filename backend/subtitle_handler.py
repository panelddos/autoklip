"""
📝 Subtitle Handler
Mengambil subtitle dari YouTube atau generate via Whisper AI
"""

import json
import os
import re
import subprocess
from typing import List, Optional

from viral_detector import SubtitleSegment


class SubtitleHandler:
    """Mengelola subtitle: download dari YouTube atau generate via Whisper"""

    def __init__(self, output_dir: str = "./temp"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def get_youtube_subtitles(self, video_url: str, video_id: str) -> Optional[List[SubtitleSegment]]:
        """
        Coba ambil subtitle dari YouTube langsung.
        Prioritas: manual subtitle > auto-generated subtitle
        """
        subtitle_file = os.path.join(self.output_dir, f"{video_id}.subtitle")

        try:
            # Coba download subtitle manual dulu
            cmd = [
                "yt-dlp",
                "--skip-download",
                "--write-sub",
                "--sub-lang", "id,en",
                "--sub-format", "json3",
                "--output", subtitle_file,
                video_url
            ]
            subprocess.run(cmd, capture_output=True, timeout=60)

            # Cek apakah file subtitle ada
            for lang in ["id", "en"]:
                json3_file = f"{subtitle_file}.{lang}.json3"
                if os.path.exists(json3_file):
                    segments = self._parse_json3(json3_file)
                    if segments:
                        print(f"✅ Subtitle manual ({lang}) ditemukan!")
                        return segments

            # Coba auto-generated subtitle
            cmd = [
                "yt-dlp",
                "--skip-download",
                "--write-auto-sub",
                "--sub-lang", "id,en",
                "--sub-format", "json3",
                "--output", subtitle_file,
                video_url
            ]
            subprocess.run(cmd, capture_output=True, timeout=60)

            for lang in ["id", "en"]:
                json3_file = f"{subtitle_file}.{lang}.json3"
                if os.path.exists(json3_file):
                    segments = self._parse_json3(json3_file)
                    if segments:
                        print(f"✅ Auto subtitle ({lang}) ditemukan!")
                        return segments

        except subprocess.TimeoutExpired:
            print("⚠️ Timeout saat download subtitle")
        except Exception as e:
            print(f"⚠️ Error download subtitle: {e}")

        return None

    def generate_whisper_subtitles(self, audio_path: str) -> Optional[List[SubtitleSegment]]:
        """Generate subtitle menggunakan Whisper AI (untuk video tanpa subtitle)"""
        try:
            import whisper

            print("🎤 Generating subtitle dengan Whisper AI...")
            model = whisper.load_model("base")  # Gunakan 'base' untuk kecepatan di server gratis
            result = model.transcribe(audio_path, verbose=False)

            segments = []
            for seg in result["segments"]:
                segments.append(SubtitleSegment(
                    start=seg["start"],
                    end=seg["end"],
                    text=seg["text"].strip()
                ))

            print(f"✅ Whisper berhasil generate {len(segments)} segments!")
            return segments

        except ImportError:
            print("⚠️ Whisper tidak tersedia, skip subtitle generation")
            return None
        except Exception as e:
            print(f"⚠️ Error Whisper: {e}")
            return None

    def _parse_json3(self, filepath: str) -> List[SubtitleSegment]:
        """Parse file subtitle format JSON3 dari YouTube"""
        segments = []

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            events = data.get("events", [])

            for event in events:
                if "segs" not in event:
                    continue

                start_ms = event.get("tStartMs", 0)
                duration_ms = event.get("dDurationMs", 0)

                # Gabungkan semua segment text
                text_parts = []
                for seg in event["segs"]:
                    text = seg.get("utf8", "").strip()
                    if text and text != "\n":
                        text_parts.append(text)

                combined_text = " ".join(text_parts).strip()
                if combined_text:
                    segments.append(SubtitleSegment(
                        start=start_ms / 1000.0,
                        end=(start_ms + duration_ms) / 1000.0,
                        text=combined_text
                    ))

        except Exception as e:
            print(f"⚠️ Error parsing JSON3: {e}")

        # Merge segments yang terlalu pendek
        return self._merge_short_segments(segments)

    def _merge_short_segments(self, segments: List[SubtitleSegment], min_duration: float = 1.0) -> List[SubtitleSegment]:
        """Gabungkan segment yang terlalu pendek"""
        if not segments:
            return []

        merged = [segments[0]]

        for seg in segments[1:]:
            last = merged[-1]

            # Gabungkan jika segment sebelumnya terlalu pendek
            if (last.end - last.start) < min_duration and (seg.start - last.end) < 1.0:
                merged[-1] = SubtitleSegment(
                    start=last.start,
                    end=seg.end,
                    text=f"{last.text} {seg.text}".strip()
                )
            else:
                merged.append(seg)

        return merged

    def segments_to_srt(self, segments: List[SubtitleSegment], output_path: str) -> str:
        """Konversi subtitle segments ke file SRT"""
        srt_content = ""

        for i, seg in enumerate(segments, 1):
            start_ts = self._seconds_to_srt_timestamp(seg.start)
            end_ts = self._seconds_to_srt_timestamp(seg.end)
            srt_content += f"{i}\n{start_ts} --> {end_ts}\n{seg.text}\n\n"

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(srt_content)

        return output_path

    def _seconds_to_srt_timestamp(self, seconds: float) -> str:
        """Konversi detik ke format SRT timestamp (HH:MM:SS,mmm)"""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
