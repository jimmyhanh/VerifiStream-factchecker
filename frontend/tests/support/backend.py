"""Synthetic browser-test server. Never shipped in the runtime image.

Only media/ASR/search/fetch/LLM adapters are faked; HTTP, storage, lineage, claim
rules, decomposition, ranking, verification and confidence use production code.
"""
import sys
import tempfile
import wave
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'backend/tests'))
from app.main import create_app
from app.models.transcript import Segment, TranscriptResult
from app.models.video import ExtractionInfo
from app.shared.config import Settings
from test_retrieval import Search, Fetcher
from test_mapping import Provider

_storage = tempfile.TemporaryDirectory(prefix='verifistream-browser-fixture-')

class Media:
    def probe(self, source, extension): return 1.0
    def extract(self, source, target):
        with wave.open(str(target),'wb') as audio:
            audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(16000)
            audio.writeframes(b'\0\0' * 16000)
        return ExtractionInfo(ffmpeg_version='synthetic-browser-fixture')

class Speech:
    def transcribe(self,audio,language):
        return TranscriptResult(language='en',duration_seconds=1,
            segments=[Segment(id=0,start=0,end=1,text='In 2024, London opened 2 schools.')],
            provider='synthetic-browser-fixture',provider_version='v1',model='fixture',
            model_revision='fixture',engine_version='fixture',parameters={})

app = create_app(Settings(storage_root=Path(_storage.name)), media=Media(),
                 transcription_provider=Speech(),search_provider=Search(),
                 source_fetcher=Fetcher(),mapping_provider=Provider())
