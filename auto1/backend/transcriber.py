import os
import torch
import whisper
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str
    confidence: float


class WhisperTranscriber:
    def __init__(self, model_size: str = "medium", language: str = "en"):
        self.model_size = model_size
        self.language = language
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Loading Whisper model ({model_size}) on {self.device}")
        self.model = whisper.load_model(model_size).to(self.device)
        
        self.gene_editing_terms = {
            "crispr": "CRISPR",
            "cas9": "Cas9",
            "cas12": "Cas12",
            "cas13": "Cas13",
            "base editor": "Base Editor",
            "prime editor": "Prime Editor",
            "guide rna": "gRNA",
            "grna": "gRNA",
            "single nucleotide polymorphism": "SNP",
            "snp": "SNP",
            "off target": "off-target",
            "on target": "on-target",
            "gene drive": "gene drive",
            "germline editing": "germline editing",
            "somatic editing": "somatic editing",
            "heritable human genome editing": "HHGE",
            "hhge": "HHGE",
            "recombinant dna": "recombinant DNA",
            "dna": "DNA",
            "rna": "RNA",
            "mrna": "mRNA",
            "trna": "tRNA",
            "rnai": "RNAi",
            "polymerase chain reaction": "PCR",
            "pcr": "PCR",
            "restriction enzyme": "restriction enzyme",
            "zinc finger": "ZFN",
            "zfn": "ZFN",
            "tal effector nuclease": "TALEN",
            "talen": "TALEN",
            "homologous recombination": "HR",
            "non homologous end joining": "NHEJ",
            "nhej": "NHEJ",
            "hdr": "HDR",
            "homology directed repair": "HDR",
            "indel": "indel",
            "knockout": "knockout",
            "knockin": "knockin",
            "transgene": "transgene",
            "vector": "vector",
            "plasmid": "plasmid",
            "epigenetics": "epigenetics",
            "methylation": "methylation",
            "histone": "histone",
            "chromatin": "chromatin",
            "allele": "allele",
            "genotype": "genotype",
            "phenotype": "phenotype",
            "penetrance": "penetrance",
            "expressivity": "expressivity",
            "mosaicism": "mosaicism",
            "chimera": "chimera",
            "in vitro fertilization": "IVF",
            "ivf": "IVF",
            "preimplantation genetic diagnosis": "PGD",
            "pgd": "PGD",
            "somatic cell nuclear transfer": "SCNT",
            "scnt": "SCNT",
        }

    def transcribe(self, audio_path: str, task: str = "transcribe") -> Dict:
        logger.info(f"Transcribing {audio_path}")
        
        result = self.model.transcribe(
            audio_path,
            language=self.language,
            task=task,
            fp16=torch.cuda.is_available(),
            verbose=False
        )
        
        return result

    def extract_segments(self, transcription_result: Dict) -> List[TranscriptSegment]:
        segments = []
        for seg in transcription_result.get('segments', []):
            segments.append(TranscriptSegment(
                start=seg['start'],
                end=seg['end'],
                text=seg['text'].strip(),
                confidence=seg.get('avg_logprob', 0.0)
            ))
        return segments

    def normalize_technical_terms(self, text: str) -> str:
        normalized_text = text
        for term_lower, term_correct in self.gene_editing_terms.items():
            pattern = re.compile(r'\b' + re.escape(term_lower) + r'\b', re.IGNORECASE)
            normalized_text = pattern.sub(term_correct, normalized_text)
        return normalized_text

    def get_full_text(self, segments: List[TranscriptSegment]) -> str:
        full_text = " ".join([seg.text for seg in segments])
        return self.normalize_technical_terms(full_text)

    def transcribe_with_normalization(self, audio_path: str) -> Tuple[str, List[TranscriptSegment]]:
        result = self.transcribe(audio_path)
        segments = self.extract_segments(result)
        
        normalized_segments = []
        for seg in segments:
            normalized_text = self.normalize_technical_terms(seg.text)
            normalized_segments.append(TranscriptSegment(
                start=seg.start,
                end=seg.end,
                text=normalized_text,
                confidence=seg.confidence
            ))
        
        full_text = self.get_full_text(normalized_segments)
        return full_text, normalized_segments
