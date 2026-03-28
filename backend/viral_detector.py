"""
🧠 Algoritma Deteksi Momen Viral
Menganalisis subtitle/transcript untuk menemukan momen berpotensi viral
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SubtitleSegment:
    """Satu baris subtitle"""
    start: float      # waktu mulai (detik)
    end: float        # waktu selesai (detik)
    text: str         # teks subtitle


@dataclass
class ViralClip:
    """Hasil deteksi klip viral"""
    start: float
    end: float
    score: float
    reason: str
    subtitle_segments: List[SubtitleSegment] = field(default_factory=list)
    title_suggestion: str = ""


class ViralDetector:
    """
    Mendeteksi momen-momen viral dari subtitle video.
    Menggunakan analisis teks berbasis keyword, pola hook, dan emotional scoring.
    """

    # Kata-kata yang menandakan momen emosional tinggi (viral potential)
    VIRAL_KEYWORDS = {
        # English
        "shocking": 3, "amazing": 3, "unbelievable": 3, "incredible": 3,
        "secret": 3, "truth": 2, "exposed": 3, "revealed": 3,
        "never": 2, "worst": 2, "best": 2, "insane": 3,
        "crazy": 2, "mind-blowing": 3, "hack": 2, "trick": 2,
        "mistake": 2, "warning": 3, "danger": 2, "finally": 2,
        "important": 2, "listen": 2, "watch": 2, "stop": 2,
        "wait": 2, "actually": 1, "literally": 1, "seriously": 2,
        "plot twist": 3, "game changer": 3, "life changing": 3,
        "no way": 2, "oh my god": 3, "what the": 2,

        # Indonesian
        "gila": 3, "parah": 3, "keren": 2, "rahasia": 3,
        "ternyata": 3, "serius": 2, "bahaya": 3, "penting": 2,
        "viral": 3, "heboh": 3, "terbongkar": 3, "fakta": 2,
        "tips": 2, "trik": 2, "salah": 2, "jangan": 2,
        "wajib": 2, "harus": 2, "awas": 3, "diam-diam": 2,
        "percaya": 2, "mustahil": 3, "luar biasa": 3,
        "nggak nyangka": 3, "auto": 2, "langsung": 1,
    }

    # Pola kalimat hook (pembuka yang menarik perhatian)
    HOOK_PATTERNS = [
        (r"(did you know|tahukah kamu|tau nggak)", 3),
        (r"(here'?s? (the|a) (thing|secret|truth))", 3),
        (r"(number \d|nomor \d|yang ke.?\d)", 2),
        (r"(the reason|alasannya|penyebabnya)", 2),
        (r"(what if|bagaimana kalau|gimana kalau)", 2),
        (r"(let me tell you|saya kasih tau|gue kasih tau)", 2),
        (r"(most people|kebanyakan orang|rata-rata orang)", 2),
        (r"(stop doing|jangan lakukan|berhenti)", 2),
        (r"(you need to|kamu harus|lo harus)", 2),
        (r"(this is why|ini alasannya|makanya)", 2),
        (r"(but here'?s? the|tapi yang)", 2),
        (r"^\d+[\.\)]\s", 1),  # Numbered list: "1. ..." "2) ..."
        (r"(first|second|third|pertama|kedua|ketiga)", 1),
        (r"\?$", 1),  # Kalimat pertanyaan
    ]

    def __init__(
        self,
        min_clip_duration: int = 15,
        max_clip_duration: int = 90,
        top_n_clips: int = 5,
        language: str = "auto"
    ):
        self.min_clip_duration = min_clip_duration
        self.max_clip_duration = max_clip_duration
        self.top_n_clips = top_n_clips
        self.language = language

    def _score_text(self, text: str) -> tuple:
        """Hitung skor viral dari sebuah teks. Return (score, reasons)"""
        text_lower = text.lower().strip()
        score = 0
        reasons = []

        # 1. Cek keyword viral
        for keyword, weight in self.VIRAL_KEYWORDS.items():
            if keyword in text_lower:
                score += weight
                reasons.append(f"keyword '{keyword}' (+{weight})")

        # 2. Cek pola hook
        for pattern, weight in self.HOOK_PATTERNS:
            if re.search(pattern, text_lower):
                score += weight
                reasons.append(f"hook pattern (+{weight})")

        # 3. Bonus untuk kalimat pendek & punchy (< 10 kata)
        word_count = len(text_lower.split())
        if word_count <= 10 and score > 0:
            score += 1
            reasons.append("short & punchy (+1)")

        # 4. Bonus untuk CAPS (menandakan emphasis)
        caps_words = re.findall(r'\b[A-Z]{2,}\b', text)
        if len(caps_words) >= 1:
            bonus = min(len(caps_words), 3)
            score += bonus
            reasons.append(f"emphasis CAPS (+{bonus})")

        # 5. Bonus untuk exclamation marks
        exclaim_count = text.count('!')
        if exclaim_count > 0:
            bonus = min(exclaim_count, 2)
            score += bonus
            reasons.append(f"exclamation (+{bonus})")

        return score, reasons

    def _find_natural_break(self, segments: List[SubtitleSegment], target_time: float, direction: str = "after") -> float:
        """Cari titik potong natural (di antara kalimat, bukan di tengah kata)"""
        best_time = target_time
        best_gap = float('inf')

        for i, seg in enumerate(segments):
            if direction == "after" and seg.start >= target_time:
                gap = seg.start - target_time
                if gap < best_gap:
                    best_gap = gap
                    best_time = seg.start
                    break
            elif direction == "before" and seg.end <= target_time:
                gap = target_time - seg.end
                if gap < best_gap:
                    best_gap = gap
                    best_time = seg.end

        return best_time

    def _create_windows(self, segments: List[SubtitleSegment]) -> List[dict]:
        """Buat sliding windows dari subtitle segments"""
        windows = []

        if not segments:
            return windows

        total_duration = segments[-1].end - segments[0].start

        # Sliding window dengan berbagai ukuran
        for window_size in [15, 30, 45, 60, 90]:
            if window_size > self.max_clip_duration:
                break
            if window_size < self.min_clip_duration:
                continue

            step = max(5, window_size // 3)  # Overlap setiap 1/3 window

            current_start = segments[0].start
            while current_start + window_size <= segments[-1].end:
                window_end = current_start + window_size

                # Ambil segments dalam window ini
                window_segments = [
                    s for s in segments
                    if s.start >= current_start and s.end <= window_end
                ]

                if window_segments:
                    # Hitung total score untuk window ini
                    total_score = 0
                    all_reasons = []
                    combined_text = " ".join(s.text for s in window_segments)

                    for seg in window_segments:
                        seg_score, seg_reasons = self._score_text(seg.text)
                        total_score += seg_score
                        all_reasons.extend(seg_reasons)

                    # Normalize score berdasarkan durasi (prefer shorter clips with high score)
                    duration = window_segments[-1].end - window_segments[0].start
                    if duration > 0:
                        normalized_score = total_score * (30 / duration)  # normalize to 30 sec
                    else:
                        normalized_score = 0

                    # Bonus jika dimulai dengan hook
                    first_text = window_segments[0].text.lower()
                    for pattern, weight in self.HOOK_PATTERNS:
                        if re.search(pattern, first_text):
                            normalized_score += weight * 1.5  # Extra bonus untuk opening hook
                            all_reasons.append(f"opening hook (+{weight * 1.5})")
                            break

                    windows.append({
                        "start": window_segments[0].start,
                        "end": window_segments[-1].end,
                        "score": normalized_score,
                        "raw_score": total_score,
                        "reasons": all_reasons,
                        "segments": window_segments,
                        "text": combined_text
                    })

                current_start += step

        return windows

    def _remove_overlaps(self, clips: List[dict]) -> List[dict]:
        """Hapus klip yang saling overlap, prioritaskan yang skor tertinggi"""
        if not clips:
            return []

        # Sort by score (highest first)
        sorted_clips = sorted(clips, key=lambda x: x["score"], reverse=True)
        selected = []

        for clip in sorted_clips:
            # Cek apakah overlap dengan yang sudah dipilih
            overlap = False
            for sel in selected:
                if clip["start"] < sel["end"] and clip["end"] > sel["start"]:
                    # Hitung overlap percentage
                    overlap_start = max(clip["start"], sel["start"])
                    overlap_end = min(clip["end"], sel["end"])
                    overlap_duration = overlap_end - overlap_start
                    clip_duration = clip["end"] - clip["start"]

                    if overlap_duration / clip_duration > 0.3:  # > 30% overlap
                        overlap = True
                        break

            if not overlap:
                selected.append(clip)

            if len(selected) >= self.top_n_clips:
                break

        # Sort by timestamp
        return sorted(selected, key=lambda x: x["start"])

    def _generate_title(self, clip: dict) -> str:
        """Generate judul singkat untuk klip"""
        text = clip["text"][:100]

        # Cari kalimat pertama sebagai judul
        sentences = re.split(r'[.!?]', text)
        if sentences:
            title = sentences[0].strip()
            if len(title) > 60:
                title = title[:57] + "..."
            return title

        return f"Clip {clip['start']:.0f}s - {clip['end']:.0f}s"

    def detect(self, segments: List[SubtitleSegment]) -> List[ViralClip]:
        """
        Deteksi momen-momen viral dari subtitle segments.

        Args:
            segments: List subtitle segments

        Returns:
            List ViralClip yang sudah diurutkan berdasarkan waktu
        """
        if not segments:
            return []

        # 1. Buat sliding windows
        windows = self._create_windows(segments)

        # 2. Filter windows dengan score > 0
        scored_windows = [w for w in windows if w["score"] > 0]

        if not scored_windows:
            # Fallback: jika tidak ada yang terdeteksi, ambil bagian awal & random
            print("⚠️ Tidak ada momen viral terdeteksi, menggunakan fallback...")
            scored_windows = sorted(windows, key=lambda x: x.get("raw_score", 0), reverse=True)[:self.top_n_clips]

        # 3. Hapus overlap
        selected = self._remove_overlaps(scored_windows)

        # 4. Konversi ke ViralClip
        result = []
        for clip_data in selected:
            clip = ViralClip(
                start=clip_data["start"],
                end=clip_data["end"],
                score=round(clip_data["score"], 2),
                reason="; ".join(set(clip_data["reasons"][:5])),  # Top 5 reasons
                subtitle_segments=clip_data["segments"],
                title_suggestion=self._generate_title(clip_data)
            )
            result.append(clip)

        return result


def format_timestamp(seconds: float) -> str:
    """Konversi detik ke format HH:MM:SS"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"
