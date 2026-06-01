import os
import librosa
import numpy as np
import soundfile as sf
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class AudioSegment:
    start: float
    end: float
    speaker: str
    text: str
    speaker_type: str


class AudioProcessor:
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.sample_rate = self.config.get('sample_rate', 16000)
        self.noise_reduction_params = self.config.get('noise_reduction', {
            'n_fft': 2048,
            'hop_length': 512,
            'noise_frame_duration': 0.5
        })

    def load_audio(self, file_path: str) -> Tuple[np.ndarray, int]:
        logger.info(f"Loading audio file: {file_path}")
        audio, sr = librosa.load(file_path, sr=self.sample_rate)
        return audio, sr

    def remove_lab_noise(self, audio: np.ndarray, sr: int) -> np.ndarray:
        logger.info("Applying noise reduction for lab equipment noise")
        
        noise_duration = self.noise_reduction_params['noise_frame_duration']
        noise_samples = int(noise_duration * sr)
        noise_clip = audio[:noise_samples]
        
        if len(noise_clip) < self.noise_reduction_params['n_fft']:
            noise_clip = audio[:self.noise_reduction_params['n_fft'] * 2]
        
        D_noise = librosa.stft(
            noise_clip,
            n_fft=self.noise_reduction_params['n_fft'],
            hop_length=self.noise_reduction_params['hop_length']
        )
        noise_mag = np.mean(np.abs(D_noise), axis=1, keepdims=True)
        noise_mag = noise_mag * 1.5
        
        D_audio = librosa.stft(
            audio,
            n_fft=self.noise_reduction_params['n_fft'],
            hop_length=self.noise_reduction_params['hop_length']
        )
        
        mag_audio = np.abs(D_audio)
        phase_audio = np.angle(D_audio)
        
        mag_clean = np.maximum(mag_audio - noise_mag, 0.01 * mag_audio)
        
        D_clean = mag_clean * np.exp(1j * phase_audio)
        audio_clean = librosa.istft(
            D_clean,
            hop_length=self.noise_reduction_params['hop_length']
        )
        
        return audio_clean

    def spectral_subtraction(self, audio: np.ndarray, sr: int, alpha: float = 2.0, beta: float = 0.01) -> np.ndarray:
        logger.info("Applying spectral subtraction")
        
        n_fft = self.noise_reduction_params['n_fft']
        hop_length = self.noise_reduction_params['hop_length']
        
        D = librosa.stft(audio, n_fft=n_fft, hop_length=hop_length)
        mag = np.abs(D)
        phase = np.angle(D)
        
        noise_est = np.mean(mag[:, :10], axis=1, keepdims=True)
        noise_est = np.tile(noise_est, (1, mag.shape[1]))
        
        mag_clean = np.sqrt(np.maximum(mag**2 - alpha * noise_est**2, beta * mag**2))
        D_clean = mag_clean * np.exp(1j * phase)
        audio_clean = librosa.istft(D_clean, hop_length=hop_length)
        
        return audio_clean

    def wiener_filter(self, audio: np.ndarray, sr: int) -> np.ndarray:
        logger.info("Applying Wiener filter for advanced noise reduction")
        
        from scipy.signal import wiener
        audio_clean = wiener(audio, mysize=55)
        return audio_clean

    def process_audio_pipeline(self, input_path: str, output_path: str) -> str:
        logger.info(f"Starting audio processing pipeline for {input_path}")
        
        audio, sr = self.load_audio(input_path)
        audio = self.remove_lab_noise(audio, sr)
        audio = self.spectral_subtraction(audio, sr)
        audio = self.wiener_filter(audio, sr)
        
        max_val = np.max(np.abs(audio))
        if max_val > 0:
            audio = audio / max_val * 0.9
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        sf.write(output_path, audio, sr)
        logger.info(f"Cleaned audio saved to {output_path}")
        
        return output_path
