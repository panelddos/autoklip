FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements dari root
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy folder backend ke dalam container
COPY backend/ .

RUN mkdir -p clips

EXPOSE 8000

# Sesuaikan path uvicorn ke folder backend
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
