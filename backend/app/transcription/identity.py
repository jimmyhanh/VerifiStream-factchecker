"""Inputs shared by the inference worker and the transcript reuse check."""
from importlib.metadata import version
from pathlib import Path
import re


def decoding_options(language: str | None) -> dict:
    return dict(language=language, task="transcribe", beam_size=5, temperature=0.0,
                vad_filter=True, condition_on_previous_text=False)


def provenance(model: str, revision: str, threads: int, language: str | None) -> dict:
    return dict(provider="faster-whisper", provider_version=version("faster-whisper"),
                engine_version=version("ctranslate2"), model="Systran/faster-whisper-" + model,
                model_revision=revision, adapter_version="faster-whisper-v2",
                parameters=dict(**decoding_options(language), device="cpu", compute_type="int8",
                                cpu_threads=threads, av_version=version("av"),
                                tokenizer_version=version("tokenizers"), vad_version=version("onnxruntime")))


def cached_revision(model: str, revision: str, cache: Path) -> str | None:
    # Resolve aliases using the same local snapshot preference as the worker.
    # An immutable commit needs no model download to identify it.
    if re.fullmatch(r"[a-f0-9]{40}", revision):
        return revision
    from huggingface_hub import snapshot_download
    path = snapshot_download(repo_id="Systran/faster-whisper-" + model, revision=revision,
                             cache_dir=str(cache.resolve()), local_files_only=True)
    commit = Path(path).name
    return commit if re.fullmatch(r"[a-f0-9]{40}", commit) else None
