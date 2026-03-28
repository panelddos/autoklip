FROM python:3.11-slim

# 1. Install system dependencies & build tools dalam satu layer
RUN apt-get update && apt-get install -y \
    ffmpeg \
    build-essential \
    gcc \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Upgrade pip dan install PyTorch versi CPU secara eksplisit (Penting untuk diet size!)
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# 3. Copy requirements dan install library lainnya
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Hapus build tools setelah selesai untuk menghemat ruang
RUN apt-get purge -y --auto-remove build-essential gcc git && \
    apt-get clean

# 5. Copy source code backend
COPY backend/ .

# 6. Persiapan folder output
RUN mkdir -p clips

EXPOSE 8000

# 7. Jalankan aplikasi
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
