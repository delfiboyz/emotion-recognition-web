FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TF_CPP_MIN_LOG_LEVEL=2

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Bobot model DeepFace disimpan di volume agar tidak diunduh ulang.
ENV DEEPFACE_HOME=/models EMOTION_DB_PATH=/app/data/emotions.db
VOLUME ["/models", "/app/data"]
EXPOSE 5000

# 1 worker (model dimuat sekali), banyak thread untuk request paralel.
CMD ["gunicorn", "-w", "1", "--threads", "8", "-t", "120", "-b", "0.0.0.0:5000", "wsgi:app"]
