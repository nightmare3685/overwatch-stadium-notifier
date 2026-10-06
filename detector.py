"""Local spectral-template detector. No network access or audio recording."""
import argparse
import json
import wave
from pathlib import Path
import numpy as np

RATE = 16000
HOP = 160
FRAME = 640
LABELS = {'match': '② マッチ成立音', 'stadium': '③ スタジアムだ！'}


def mono_resample(samples, rate):
    samples = np.asarray(samples, dtype=np.float32)
    if samples.ndim == 2:
        samples = samples.mean(axis=1)
    if rate != RATE:
        n = int(round(len(samples) * RATE / rate))
        samples = np.interp(np.arange(n) * rate / RATE,
                            np.arange(len(samples)), samples).astype(np.float32)
    return samples


def read_wav(path):
    with wave.open(str(path), 'rb') as f:
        if f.getsampwidth() != 2:
            raise ValueError('16-bit PCM WAV が必要です。')
        rate, channels = f.getframerate(), f.getnchannels()
        data = np.frombuffer(f.readframes(f.getnframes()), dtype='<i2')
    return mono_resample(data.reshape(-1, channels) / 32768., rate)


def features(samples):
    if len(samples) < FRAME:
        return np.empty((0, 64), dtype=np.float32)
    frames = np.lib.stride_tricks.sliding_window_view(samples, FRAME)[::HOP]
    spectrum = np.abs(np.fft.rfft(frames * np.hanning(FRAME), axis=1))[:, 1:321]
    bands = spectrum.reshape(-1, 64, 5).mean(axis=2)
    # Relative spectrum makes matching insensitive to ordinary volume changes.
    bands = np.log1p(bands / np.maximum(bands.max(axis=1, keepdims=True), 1e-8) * 100)
    bands -= bands.mean(axis=1, keepdims=True)
    bands /= np.maximum(np.linalg.norm(bands, axis=1, keepdims=True), 1e-8)
    rms = np.sqrt(np.mean(frames * frames, axis=1))
    bands[rms < 0.00008] = 0
    return bands.astype(np.float32)


class Detector:
    def __init__(self, threshold=0.90, cooldown=30., templates=None):
        if not 0 < threshold <= 1 or cooldown < 0:
            raise ValueError('threshold は 0〜1、cooldown は0以上です。')
        path = templates or Path(__file__).with_name('templates.npz')
        with np.load(path, allow_pickle=False) as archive:
            self.templates = {key: archive[key].copy() for key in LABELS}
        self.threshold, self.cooldown = threshold, cooldown
        self.last_event = -float('inf')
        self.history = np.empty((0, 64), dtype=np.float32)
        self.pending = np.empty(0, dtype=np.float32)
        self.max_frames = max(map(len, self.templates.values())) + 10
        self.frame_count = 0
        self.max_scores = dict.fromkeys(LABELS, 0.)

    def feed(self, samples):
        self.pending = np.concatenate((self.pending, samples))
        new = features(self.pending)
        if not len(new):
            return [], {}
        self.pending = self.pending[len(new) * HOP:]
        self.frame_count += len(new)
        self.history = np.concatenate((self.history, new))[-self.max_frames:]
        scores = {}
        for key, template in self.templates.items():
            n = len(template)
            score = 0.
            for lag in range(min(len(new), 10)):
                end = len(self.history) - lag
                if end >= n:
                    candidate = self.history[end-n:end]
                    score = max(score, float(np.sum(candidate * template) / n))
            scores[key] = score
            self.max_scores[key] = max(self.max_scores[key], score)
        timestamp = (self.frame_count * HOP + FRAME - HOP) / RATE
        winner = max(scores, key=scores.get)
        events = []
        if scores[winner] >= self.threshold and timestamp - self.last_event >= self.cooldown:
            self.last_event = timestamp
            events.append({'seconds': round(timestamp, 2), 'sound': winner,
                           'score': round(scores[winner], 4)})
        return events, scores


def analyze(path, threshold=.90, cooldown=30.):
    detector = Detector(threshold, cooldown)
    samples = read_wav(path)
    events = []
    for start in range(0, len(samples), 1600):
        found, _ = detector.feed(samples[start:start+1600])
        events.extend(found)
    return {'events': events, 'max_scores': detector.max_scores,
            'duration_seconds': len(samples) / RATE}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('wav', type=Path)
    parser.add_argument('--threshold', type=float, default=.90)
    parser.add_argument('--cooldown', type=float, default=30.)
    args = parser.parse_args()
    print(json.dumps(analyze(args.wav, args.threshold, args.cooldown), ensure_ascii=False, indent=2))
