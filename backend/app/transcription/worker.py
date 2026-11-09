"""Internal subprocess entry point, not a background job queue."""
import json
import sys
import wave
from app.transcription.identity import decoding_options, provenance, snapshot_options
from pathlib import Path


def transcribe(audio: Path, options: dict) -> dict:
    try:
        from faster_whisper import WhisperModel
        from faster_whisper.tokenizer import _LANGUAGE_CODES
        from huggingface_hub import snapshot_download
    except ImportError:
        return {'error_code': 'provider_unavailable'}
    if options['language'] is not None and options['language'] not in _LANGUAGE_CODES:
        return {'error_code': 'unsupported_language'}
    try:
        # Cache reuse must also work offline after a successful first download.
        kwargs = snapshot_options(options['model'], options['revision'], Path(options['cache']))
        try:
            model_path = snapshot_download(**kwargs, local_files_only=True)
        except Exception:
            model_path = snapshot_download(**kwargs)
        model = WhisperModel(model_path, device='cpu', compute_type='int8',
                             cpu_threads=options['threads'], local_files_only=True)
    except Exception:
        return {'error_code': 'model_unavailable'}
    try:
        with wave.open(str(audio), 'rb') as stream:
            duration = stream.getnframes() / stream.getframerate()
        segments, info = model.transcribe(
            str(audio), **decoding_options(options['language']),
        )
        items = []
        for segment in segments:
            text = segment.text.strip()
            # Whisper may extend the final endpoint slightly into padded audio.
            start, end = max(0.0, segment.start), min(duration, segment.end)
            if text and end > start:
                items.append(dict(id=len(items), start=start, end=end, text=text))
        return dict(
            language=info.language if items else None, duration_seconds=duration,
            segments=items, **provenance(options['model'], Path(model_path).name,
                                         options['threads'], options['language']),
        )
    except Exception:
        return {'error_code': 'transcription_failed'}


if __name__ == '__main__':
    result = transcribe(Path(sys.argv[1]), json.loads(sys.argv[3]))
    Path(sys.argv[2]).write_text(json.dumps(result), encoding='utf-8')
