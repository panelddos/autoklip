FROM python:3.11-slim

# 1. Install dependencies sistem + NodeJS (untuk JS Runtime yt-dlp)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    build-essential \
    gcc \
    git \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Upgrade pip & Install PyTorch CPU
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# 3. Copy & Install requirements (Pastikan isinya: yt-dlp)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Bersihkan build tools (NodeJS jangan dihapus!)
RUN apt-get purge -y --auto-remove build-essential gcc git && \
    apt-get clean

# 5. Copy source & Set permission
COPY backend/ .
RUN mkdir -p clips && chmod -R 777 clips

EXPOSE 8000

# 6. Jalankan aplikasi
CMD uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}
