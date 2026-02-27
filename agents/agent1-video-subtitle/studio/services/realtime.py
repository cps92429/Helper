from __future__ import annotations

import os
import queue
import threading
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple


try:
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover
    np = None

try:
    import sounddevice as sd  # type: ignore
except Exception:  # pragma: no cover
    sd = None

try:
    from faster_whisper import WhisperModel  # type: ignore
except Exception:  # pragma: no cover
    WhisperModel = None


@dataclass(frozen=True)
class RealtimeSegment:
    start: float
    end: float
    text: str


def list_input_devices() -> List[Tuple[int, str]]:
    if sd is None:
        return []
    devices = sd.query_devices()
    out: List[Tuple[int, str]] = []
    for idx, d in enumerate(devices):
        try:
            if int(d.get("max_input_channels", 0)) > 0:
                out.append((idx, str(d.get("name", f"Device {idx}"))))
        except Exception:
            continue
    return out


class RealtimeTranscriber:
    def __init__(
        self,
        *,
        model_size: str = "base",
        language: str = "auto",
        sample_rate: int = 16000,
        chunk_seconds: float = 2.0,
        device: Optional[int] = None,
        compute_type: str = "int8",
        beam_size: int = 1,
        energy_threshold: float = 0.006,
    ) -> None:
        if np is None or sd is None:
            raise RuntimeError("缺少 sounddevice / numpy。請先執行：.\\setup.ps1 -Target Agent1Realtime")
        if WhisperModel is None:
            raise RuntimeError("缺少 faster-whisper。請先執行：.\\setup.ps1 -Target Agent1Realtime")

        self.model_size = model_size
        self.language = language
        self.sample_rate = int(sample_rate)
        self.chunk_seconds = float(chunk_seconds)
        self.device = device
        self.compute_type = compute_type
        self.beam_size = int(beam_size)
        self.energy_threshold = float(energy_threshold)

        # Worker I/O
        self._audio_q: "queue.Queue[np.ndarray]" = queue.Queue()
        self._seg_q: "queue.Queue[RealtimeSegment]" = queue.Queue()
        self._running = threading.Event()
        self._stream: Optional["sd.InputStream"] = None

        cpu_threads = max(1, (os.cpu_count() or 4) - 1)
        self._model = WhisperModel(
            self.model_size,
            device="cpu",
            compute_type=self.compute_type,
            cpu_threads=cpu_threads,
            num_workers=cpu_threads,
        )

        self._t0: Optional[float] = None
        self._processed_seconds = 0.0
        self.segments: List[RealtimeSegment] = []

        self._worker_thread: Optional[threading.Thread] = None
        self._stream_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._running.is_set():
            return
        self._running.set()
        self._t0 = time.time()

        self._worker_thread = threading.Thread(target=self._worker_loop, name="realtime-worker", daemon=True)
        self._worker_thread.start()

        self._stream_thread = threading.Thread(target=self._stream_loop, name="realtime-stream", daemon=True)
        self._stream_thread.start()

    def stop(self) -> None:
        self._running.clear()
        try:
            if self._stream is not None:
                self._stream.stop()
                self._stream.close()
        except Exception:
            pass
        self._stream = None

    def is_running(self) -> bool:
        return self._running.is_set()

    def get_segment_nowait(self) -> Optional[RealtimeSegment]:
        try:
            return self._seg_q.get_nowait()
        except queue.Empty:
            return None

    def _audio_callback(self, indata, frames, time_info, status) -> None:
        if not self._running.is_set():
            return
        try:
            self._audio_q.put(indata.copy())
        except Exception:
            return

    def _stream_loop(self) -> None:
        assert sd is not None
        # Run the sounddevice stream on its own thread so UI never blocks.
        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                device=self.device,
                callback=self._audio_callback,
            )
            with self._stream:
                while self._running.is_set():
                    time.sleep(0.05)
        except Exception as e:
            self._running.clear()
            self._seg_q.put(RealtimeSegment(start=0.0, end=0.0, text=f"[錯誤] 麥克風串流啟動失敗：{e}"))

    def _worker_loop(self) -> None:
        assert np is not None
        samples_needed = int(self.sample_rate * self.chunk_seconds)
        buf: List["np.ndarray"] = []

        while self._running.is_set():
            try:
                chunk = self._audio_q.get(timeout=0.5)
            except queue.Empty:
                continue

            buf.append(chunk)
            total_samples = int(sum(int(x.shape[0]) for x in buf))
            if total_samples < samples_needed:
                continue

            audio = np.concatenate(buf, axis=0).astype("float32", copy=False).flatten()
            buf.clear()

            # Simple RMS gate to avoid spending CPU on silence.
            rms = float(np.sqrt(np.mean(np.square(audio)))) if audio.size else 0.0
            if rms < self.energy_threshold:
                self._processed_seconds += self.chunk_seconds
                continue

            offset = self._processed_seconds
            self._processed_seconds += self.chunk_seconds

            try:
                lang = None if self.language == "auto" else self.language
                segments, _info = self._model.transcribe(
                    audio,
                    language=lang,
                    beam_size=self.beam_size,
                )
                for seg in segments:
                    text = (seg.text or "").strip()
                    if not text:
                        continue
                    s = RealtimeSegment(start=float(seg.start) + offset, end=float(seg.end) + offset, text=text)
                    self.segments.append(s)
                    self._seg_q.put(s)
            except Exception as e:
                self._seg_q.put(RealtimeSegment(start=offset, end=offset, text=f"[WARN] 轉錄失敗：{e}"))

