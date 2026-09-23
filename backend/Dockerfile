FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /srv
COPY backend/pyproject.toml ./backend/pyproject.toml
COPY backend/app ./backend/app
COPY backend/logging.json ./backend/logging.json
RUN pip install --no-cache-dir './backend[transcription]' \
    && useradd --create-home appuser && mkdir /srv/storage && chown appuser /srv/storage
USER appuser
ENV STORAGE_ROOT=/srv/storage
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-config", "backend/logging.json"]
