# Talking Page local TTS server (Chatterbox-Nano on CPU).
# The Chrome extension still runs on the host and talks to localhost:8765.

FROM python:3.11-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends git libsndfile1 ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY server/requirements.txt server/requirements.txt

# CPU wheels keep the image smaller and match NanoEngine (device="cpu").
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r server/requirements.txt

COPY server/ server/

ENV TALKING_PAGE_HOST=0.0.0.0
ENV TALKING_PAGE_PORT=8765
ENV PYTHONUNBUFFERED=1

EXPOSE 8765

CMD ["python", "server/talking_page_server.py"]
