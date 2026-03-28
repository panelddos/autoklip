FROM python:3.11-slim

# Install FFmpeg (WAJIB untuk potong video)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements dan install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy semua source code
COPY . .

# Buat folder output
RUN mkdir -p clips

# Expose port
EXPOSE 8000

# Jalankan server
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
