import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class SpeakerTurn:
    speaker: str
    start: float
    end: float
    speaker_type: str


class SpeakerDiarizer:
    def __init__(self, auth_token: Optional[str] = None, use_pyannote: bool = True):
        self.auth_token = auth_token or os.environ.get('PYANNOTE_AUTH_TOKEN')
        self.use_pyannote = use_pyannote
        self.pipeline = None
        
        self.speaker_profiles = {
            'scientist_keywords': [
                'CRISPR', 'Cas9', 'experiment', 'data', 'results', 'sequence',
                'genome', 'DNA', 'RNA', 'protein', 'enzyme', 'assay', 'in vitro',
                'in vivo', 'mouse model', 'clinical trial', 'efficacy', 'specificity',
                'off-target', 'efficiency', 'delivery', 'vector', 'plasmid', 'transfection',
                'expression', 'knockout', 'knockin', 'phenotype', 'genotype'
            ],
            'ethicist_keywords': [
                'ethics', 'moral', 'justice', 'autonomy', 'beneficence', 'non-maleficence',
                'consent', 'informed consent', 'privacy', 'confidentiality', 'equity',
                'access', 'fairness', 'regulation', 'policy', 'governance', 'oversight',
                'accountability', 'transparency', 'stakeholder', 'public engagement',
                'bioethics', 'neuroethics', 'germline', 'heritable', 'future generations',
                'dignity', 'human rights', 'social justice', 'discrimination', 'eugenics'
            ]
        }
        
        if self.use_pyannote and self.auth_token:
            self._init_pyannote()

    def _init_pyannote(self):
        try:
            from pyannote.audio import Pipeline
            logger.info("Initializing pyannote speaker diarization pipeline")
            self.pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=self.auth_token
            )
        except ImportError:
            logger.warning("pyannote.audio not installed. Using rule-based diarization.")
            self.use_pyannote = False
        except Exception as e:
            logger.warning(f"Failed to initialize pyannote: {e}. Using rule-based diarization.")
            self.use_pyannote = False

    def diarize(self, audio_path: str) -> List[SpeakerTurn]:
        if self.use_pyannote and self.pipeline:
            return self._diarize_with_pyannote(audio_path)
        else:
            return self._diarize_rule_based(audio_path)

    def _diarize_with_pyannote(self, audio_path: str) -> List[SpeakerTurn]:
        logger.info(f"Running pyannote diarization on {audio_path}")
        
        diarization = self.pipeline(audio_path)
        
        turns = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            turns.append(SpeakerTurn(
                speaker=speaker,
                start=turn.start,
                end=turn.end,
                speaker_type='unknown'
            ))
        
        return turns

    def _diarize_rule_based(self, audio_path: str) -> List[SpeakerTurn]:
        logger.info("Using rule-based speaker diarization (simulated)")
        
        import librosa
        import soundfile as sf
        
        audio, sr = librosa.load(audio_path, sr=16000)
        duration = len(audio) / sr
        
        turns = []
        segment_duration = 60.0
        current_time = 0.0
        speaker_idx = 0
        
        while current_time < duration:
            end_time = min(current_time + segment_duration, duration)
            speaker = f"SPEAKER_{speaker_idx % 3}"
            
            turns.append(SpeakerTurn(
                speaker=speaker,
                start=current_time,
                end=end_time,
                speaker_type='unknown'
            ))
            
            current_time = end_time
            speaker_idx += 1
        
        return turns

    def classify_speaker_type(self, text: str) -> str:
        scientist_score = sum(
            1 for keyword in self.speaker_profiles['scientist_keywords']
            if keyword.lower() in text.lower()
        )
        
        ethicist_score = sum(
            1 for keyword in self.speaker_profiles['ethicist_keywords']
            if keyword.lower() in text.lower()
        )
        
        if scientist_score > ethicist_score:
            return 'scientist'
        elif ethicist_score > scientist_score:
            return 'ethicist'
        else:
            return 'unknown'

    def merge_transcript_with_diarization(
        self,
        transcript_segments: List,
        speaker_turns: List[SpeakerTurn]
    ) -> List[Dict]:
        logger.info("Merging transcript with speaker diarization")
        
        merged = []
        
        for seg in transcript_segments:
            seg_mid = (seg.start + seg.end) / 2
            
            best_turn = None
            best_overlap = 0
            
            for turn in speaker_turns:
                overlap_start = max(seg.start, turn.start)
                overlap_end = min(seg.end, turn.end)
                overlap = max(0, overlap_end - overlap_start)
                
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_turn = turn
            
            speaker_type = self.classify_speaker_type(seg.text)
            
            merged.append({
                'start': seg.start,
                'end': seg.end,
                'text': seg.text,
                'speaker': best_turn.speaker if best_turn else 'UNKNOWN',
                'speaker_type': speaker_type,
                'confidence': seg.confidence
            })
        
        return merged
