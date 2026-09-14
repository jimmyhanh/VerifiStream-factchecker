import json
import math
import subprocess
import wave
from pathlib import Path
from typing import Protocol
from app.models.video import ExtractionInfo
from app.shared.config import Settings
from app.shared.errors import ServiceError

class MediaProcessor(Protocol):
    def probe(self, source: Path, extension: str) -> float: ...
    def extract(self, source: Path, target: Path) -> ExtractionInfo: ...

class FFmpegProcessor:
    def __init__(self, settings: Settings):
        self.settings = settings

    def _run(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                args, stdin=subprocess.DEVNULL, capture_output=True,
                text=True, timeout=self.settings.process_timeout_seconds, check=True,
            )
        except FileNotFoundError as exc:
            raise ServiceError("media_tool_unavailable", "FFmpeg or FFprobe is unavailable.", 503) from exc
        except subprocess.TimeoutExpired as exc:
            raise ServiceError("media_timeout", "Media processing exceeded the time limit.", 504) from exc
        except subprocess.CalledProcessError as exc:
            raise ServiceError("invalid_media", "Media could not be decoded.") from exc

    def probe(self, source: Path, extension: str) -> float:
        result = self._run([
            self.settings.ffprobe, "-v", "error",
            "-protocol_whitelist", "file", "-format_whitelist", "mov,matroska,webm",
            "-show_entries", "format=format_name,duration:stream=codec_type",
            "-of", "json", str(source.resolve()),
        ])
        try:
            data = json.loads(result.stdout)
            containers = set(data["format"]["format_name"].split(","))
            expected = {"mov"} if extension in {".mp4", ".mov"} else {"matroska", "webm"}
            if not containers & expected:
                raise ValueError("container mismatch")
            kinds = {stream["codec_type"] for stream in data["streams"]}
            if "video" not in kinds:
                raise ServiceError("no_video_stream", "File has no video stream.")
            if "audio" not in kinds:
                raise ServiceError("no_audio_stream", "Video has no audio stream.")
            duration = float(data["format"]["duration"])
            if not math.isfinite(duration) or duration <= 0:
                raise ValueError("invalid duration")
            if duration > self.settings.max_duration_seconds:
                raise ServiceError("video_too_long", "Video exceeds configured duration limit.")
            return duration
        except (KeyError, TypeError, ValueError) as exc:
            raise ServiceError("invalid_media", "Invalid or unsupported media metadata.") from exc

    def extract(self, source: Path, target: Path) -> ExtractionInfo:
        temporary = target.with_suffix(".part.wav")
        try:
            version = self._run([self.settings.ffmpeg, "-version"]).stdout.splitlines()[0]
            self._run([
                self.settings.ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                "-protocol_whitelist", "file", "-format_whitelist", "mov,matroska,webm",
                "-i", str(source.resolve()), "-map", "0:a:0", "-vn",
                "-threads", "1", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
                "-fs", str((self.settings.max_duration_seconds + 1) * 32000 + 4096),
                "-f", "wav", str(temporary.resolve()),
            ])
            with wave.open(str(temporary), "rb") as audio:
                duration = audio.getnframes() / audio.getframerate()
                if (audio.getnchannels(), audio.getframerate(), audio.getsampwidth()) != (1, 16000, 2):
                    raise ServiceError("invalid_audio_output", "Unexpected extracted audio format.", 500)
                if not 0 < duration <= self.settings.max_duration_seconds + 0.5:
                    raise ServiceError("invalid_audio_output", "Extracted audio duration is invalid.")
            temporary.replace(target)
            return ExtractionInfo(ffmpeg_version=version)
        except (wave.Error, EOFError) as exc:
            raise ServiceError("invalid_audio_output", "Extracted audio is unreadable.", 500) from exc
        finally:
            temporary.unlink(missing_ok=True)
