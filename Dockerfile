FROM python:3.11-slim

# Install FFmpeg DAN Build Tools (WAJIB untuk Whisper & tiktoken)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    build-essential \
    gcc \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Upgrade pip & setuptools sebelum install requirements
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

# Copy folder backend ke dalam container
COPY backend/ .

RUN mkdir -p clips

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
