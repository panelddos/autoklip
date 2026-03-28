/**
 * 🎬 Auto Video Clipper — Frontend Logic
 * Handles UI interaction, API calls, progress tracking
 */

// ============================================================
// Configuration
// ============================================================

const API_BASE = "autoklip-production.up.railway.app";

const POLL_INTERVAL = 2000; // Cek status setiap 2 detik

// ============================================================
// DOM Elements
// ============================================================

const elements = {
    youtubeUrl: document.getElementById('youtubeUrl'),
    pasteBtn: document.getElementById('pasteBtn'),
    clipBtn: document.getElementById('clipBtn'),
    settingsToggle: document.getElementById('settingsToggle'),
    settingsPanel: document.getElementById('settingsPanel'),

    // Settings
    minDuration: document.getElementById('minDuration'),
    maxDuration: document.getElementById('maxDuration'),
    maxClips: document.getElementById('maxClips'),
    minDurationVal: document.getElementById('minDurationVal'),
    maxDurationVal: document.getElementById('maxDurationVal'),
    maxClipsVal: document.getElementById('maxClipsVal'),
    formatVertical: document.getElementById('formatVertical'),
    formatOriginal: document.getElementById('formatOriginal'),

    // Sections
    progressSection: document.getElementById('progressSection'),
    resultsSection: document.getElementById('resultsSection'),
    errorSection: document.getElementById('errorSection'),

    // Progress
    progressTitle: document.getElementById('progressTitle'),
    progressFill: document.getElementById('progressFill'),
    progressPercent: document.getElementById('progressPercent'),
    progressMessage: document.getElementById('progressMessage'),

    // Results
    videoTitle: document.getElementById('videoTitle'),
    videoDuration: document.getElementById('videoDuration'),
    totalClips: document.getElementById('totalClips'),
    clipsGrid: document.getElementById('clipsGrid'),

    // Error
    errorTitle: document.getElementById('errorTitle'),
    errorMessage: document.getElementById('errorMessage'),
    retryBtn: document.getElementById('retryBtn'),
    newClipBtn: document.getElementById('newClipBtn'),
};

// State
let currentJobId = null;
let pollTimer = null;
let isVerticalFormat = true;

// ============================================================
// Event Listeners
// ============================================================

// Paste button
elements.pasteBtn.addEventListener('click', async () => {
    try {
        const text = await navigator.clipboard.readText();
        elements.youtubeUrl.value = text;
        elements.youtubeUrl.focus();
    } catch {
        alert('Tidak bisa mengakses clipboard. Silakan paste manual (Ctrl+V).');
    }
});

// Settings toggle
elements.settingsToggle.addEventListener('click', () => {
    elements.settingsToggle.classList.toggle('active');
    elements.settingsPanel.classList.toggle('active');
});

// Range sliders
elements.minDuration.addEventListener('input', (e) => {
    elements.minDurationVal.textContent = `${e.target.value} detik`;
});
elements.maxDuration.addEventListener('input', (e) => {
    elements.maxDurationVal.textContent = `${e.target.value} detik`;
});
elements.maxClips.addEventListener('input', (e) => {
    elements.maxClipsVal.textContent = `${e.target.value} klip`;
});

// Format buttons
elements.formatVertical.addEventListener('click', () => {
    isVerticalFormat = true;
    elements.formatVertical.classList.add('active');
    elements.formatOriginal.classList.remove('active');
});
elements.formatOriginal.addEventListener('click', () => {
    isVerticalFormat = false;
    elements.formatOriginal.classList.add('active');
    elements.formatVertical.classList.remove('active');
});

// Main clip button
elements.clipBtn.addEventListener('click', startClipping);

// Enter key to submit
elements.youtubeUrl.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') startClipping();
});

// Retry & New clip buttons
elements.retryBtn.addEventListener('click', startClipping);
elements.newClipBtn.addEventListener('click', resetUI);

// ============================================================
// Main Functions
// ============================================================

async function startClipping() {
    const url = elements.youtubeUrl.value.trim();

    // Validate URL
    if (!url) {
        shakeElement(elements.youtubeUrl.parentElement);
        return;
    }

    if (!isValidYouTubeUrl(url)) {
        showError('URL Tidak Valid', 'Masukkan link YouTube yang valid. Contoh: https://youtube.com/watch?v=xxxxx');
        return;
    }

    // Prepare request
    const request = {
        youtube_url: url,
        min_duration: parseInt(elements.minDuration.value),
        max_duration: parseInt(elements.maxDuration.value),
        max_clips: parseInt(elements.maxClips.value),
        format_vertical: isVerticalFormat,
        video_quality: "720"
    };

    // Update UI
    showProgress();
    elements.clipBtn.disabled = true;

    try {
        // Start job
        const response = await fetch(`${API_BASE}/api/clip`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request)
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || 'Gagal memulai proses');
        }

        const data = await response.json();
        currentJobId = data.job_id;

        // Start polling
        startPolling();

    } catch (error) {
        showError('Koneksi Gagal', `Tidak bisa terhubung ke server. Pastikan backend berjalan.\n\nError: ${error.message}`);
        elements.clipBtn.disabled = false;
    }
}

function startPolling() {
    if (pollTimer) clearInterval(pollTimer);

    pollTimer = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE}/api/status/${currentJobId}`);
            const data = await response.json();

            updateProgress(data);

            if (data.status === 'completed') {
                clearInterval(pollTimer);
                showResults(data.result);
                elements.clipBtn.disabled = false;
            } else if (data.status === 'failed') {
                clearInterval(pollTimer);
                showError('Proses Gagal', data.result?.error || data.message);
                elements.clipBtn.disabled = false;
            }

        } catch (error) {
            console.error('Polling error:', error);
        }
    }, POLL_INTERVAL);
}

// ============================================================
// UI Update Functions
// ============================================================

function showProgress() {
    elements.progressSection.style.display = 'block';
    elements.resultsSection.style.display = 'none';
    elements.errorSection.style.display = 'none';

    // Reset progress
    updateProgress({ progress: 5, message: '⏳ Memulai proses...' });

    // Scroll to progress
    elements.progressSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function updateProgress(data) {
    const progress = data.progress || 0;
    elements.progressFill.style.width = `${progress}%`;
    elements.progressPercent.textContent = `${progress}%`;
    elements.progressMessage.textContent = data.message || '';

    // Update step indicators
    const stepThresholds = [
        { id: 'step1', min: 5 },
        { id: 'step2', min: 15 },
        { id: 'step3', min: 35 },
        { id: 'step4', min: 55 },
        { id: 'step5', min: 75 },
    ];

    stepThresholds.forEach(({ id, min }) => {
        const el = document.getElementById(id);
        if (progress >= min + 20) {
            el.className = 'step done';
        } else if (progress >= min) {
            el.className = 'step active';
        } else {
            el.className = 'step';
        }
    });
}

function showResults(result) {
    elements.progressSection.style.display = 'none';
    elements.resultsSection.style.display = 'block';
    elements.errorSection.style.display = 'none';

    // Video info
    elements.videoTitle.textContent = result.video_title;
    elements.videoDuration.textContent = result.video_duration_formatted;
    elements.totalClips.textContent = `${result.total_clips} klip`;

    // Render clips
    elements.clipsGrid.innerHTML = '';

    result.clips.forEach((clip, index) => {
        const card = createClipCard(clip, index + 1);
        elements.clipsGrid.appendChild(card);
    });

    // Scroll to results
    elements.resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function createClipCard(clip, number) {
    const card = document.createElement('div');
    card.className = 'clip-card';

    const scoreColor = clip.score >= 5 ? '#00B894' : clip.score >= 3 ? '#FDCB6E' : '#B0B0CC';
    const scoreLabel = clip.score >= 5 ? '🔥 High' : clip.score >= 3 ? '⚡ Medium' : '📊 Normal';

    card.innerHTML = `
        <div class="clip-header">
            <div class="clip-number">${number}</div>
            <div class="clip-score" style="color: ${scoreColor}; background: ${scoreColor}22;">
                ${scoreLabel} — ${clip.score}
            </div>
        </div>
        <div class="clip-body">
            <div class="clip-title">${escapeHtml(clip.title)}</div>
            <div class="clip-meta">
                <span>⏱️ ${clip.start_formatted} → ${clip.end_formatted}</span>
                <span>📏 ${clip.duration}s</span>
                ${clip.has_subtitle ? '<span>📝 Subtitle ✅</span>' : ''}
            </div>
            <div class="clip-reason">💡 ${escapeHtml(clip.reason)}</div>
        </div>
        <div class="clip-actions">
            <button class="preview-btn" onclick="previewClip('${clip.download_url}')">
                ▶️ Preview
            </button>
            <button class="download-btn" onclick="downloadClip('${clip.download_url}', '${clip.filename}')">
                📥 Download
            </button>
        </div>
    `;

    return card;
}

function showError(title, message) {
    elements.progressSection.style.display = 'none';
    elements.resultsSection.style.display = 'none';
    elements.errorSection.style.display = 'block';

    elements.errorTitle.textContent = title;
    elements.errorMessage.textContent = message;

    elements.errorSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function resetUI() {
    elements.youtubeUrl.value = '';
    elements.progressSection.style.display = 'none';
    elements.resultsSection.style.display = 'none';
    elements.errorSection.style.display = 'none';
    elements.clipBtn.disabled = false;
    currentJobId = null;

    window.scrollTo({ top: 0, behavior: 'smooth' });
    elements.youtubeUrl.focus();
}

// ============================================================
// Helper Functions
// ============================================================

function isValidYouTubeUrl(url) {
    const patterns = [
        /^(https?:\/\/)?(www\.)?youtube\.com\/watch\?v=[\w-]+/,
        /^(https?:\/\/)?(www\.)?youtu\.be\/[\w-]+/,
        /^(https?:\/\/)?(www\.)?youtube\.com\/shorts\/[\w-]+/,
        /^(https?:\/\/)?(www\.)?youtube\.com\/embed\/[\w-]+/,
    ];
    return patterns.some(p => p.test(url));
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function shakeElement(el) {
    el.style.animation = 'none';
    el.offsetHeight; // trigger reflow
    el.style.animation = 'shake 0.5s ease';
    setTimeout(() => el.style.animation = '', 500);
}

// Preview video in modal
function previewClip(url) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
        <div class="modal-content">
            <video controls autoplay>
                <source src="${API_BASE}${url}" type="video/mp4">
                Browser tidak support video.
            </video>
        </div>
        <button class="modal-close" onclick="this.parentElement.remove()">✕</button>
    `;
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) overlay.remove();
    });
    document.body.appendChild(overlay);
}

// Download clip
function downloadClip(url, filename) {
    const a = document.createElement('a');
    a.href = `${API_BASE}${url}`;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

// Add shake animation
const style = document.createElement('style');
style.textContent = `
    @keyframes shake {
        0%, 100% { transform: translateX(0); }
        20% { transform: translateX(-8px); }
        40% { transform: translateX(8px); }
        60% { transform: translateX(-5px); }
        80% { transform: translateX(5px); }
    }
`;
document.head.appendChild(style);

// ============================================================
// Init
// ============================================================

console.log('🎬 Auto Video Clipper loaded!');
elements.youtubeUrl.focus();
