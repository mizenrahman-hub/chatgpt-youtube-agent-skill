FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libass9 fonts-dejavu-core fontconfig \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./requirements.txt
COPY skills/yt-shorts/requirements.txt ./skills/yt-shorts/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && ffmpeg -hide_banner -encoders 2>/dev/null | grep -q libx264 \
    && ffmpeg -hide_banner -encoders 2>/dev/null | grep -qw aac \
    && ffmpeg -hide_banner -filters 2>/dev/null | grep -qw subtitles \
    && fc-match "DejaVu Sans"

COPY . .
RUN useradd --create-home --uid 10001 worker
USER worker
CMD ["python", "-u", "worker.py"]
