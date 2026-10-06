"""Read PCM from the Windows process-only helper; never fall back to device audio."""
import os
from pathlib import Path
import queue
import subprocess
import threading
import time

HELPER = Path(__file__).with_name('ProcessAudio.exe')
FLAGS = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0


def find_overwatch():
    result = subprocess.run([str(HELPER), '--list'], capture_output=True, timeout=5,
                            creationflags=FLAGS, text=True, encoding='utf-8', errors='replace')
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    ids = [int(line) for line in result.stdout.splitlines() if line.strip().isdigit()]
    if not ids:
        raise ValueError('Overwatchが起動していません。ゲームを起動してから検知開始を押してください。')
    if len(ids) != 1:
        raise ValueError('Overwatchが複数あります。1つだけ起動した状態で検知を開始してください。')
    return ids[0]


class ProcessAudio:
    def __init__(self, pid):
        self.process = subprocess.Popen([str(HELPER), str(pid)], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=FLAGS)
        self.audio = queue.Queue(maxsize=64)
        self.ready = threading.Event()
        self.closed = threading.Event()
        self.error = ''
        self.threads = [threading.Thread(target=self.read_audio, daemon=True),
                        threading.Thread(target=self.read_status, daemon=True)]
        for thread in self.threads:
            thread.start()

    def read_status(self):
        for line in self.process.stderr:
            text = line.decode('utf-8', errors='replace').strip()
            if text.startswith('READY '):
                self.ready.set()
            elif text:
                self.error = text

    def read_audio(self):
        while not self.closed.is_set():
            data = self.process.stdout.read(3200)
            if not data:
                break
            try:
                self.audio.put(data, timeout=.5)
            except queue.Full:
                self.error = '音声処理が追いつきません。検知を停止して再開してください。'
                self.process.terminate()
                break

    def blocks(self, stop):
        deadline = time.monotonic() + 12
        while not self.ready.wait(.05):
            if stop.is_set():
                return
            if self.process.poll() is not None:
                self.threads[1].join(timeout=.5)
                raise RuntimeError(self.error or 'OWの音声取得を開始できませんでした。')
            if time.monotonic() > deadline:
                raise RuntimeError('OWの音声取得がタイムアウトしました。')
        yield None  # readiness notification, even when OW is silent
        while not stop.is_set():
            if self.error:
                raise RuntimeError(self.error)
            try:
                yield self.audio.get(timeout=.1)
            except queue.Empty:
                if self.process.poll() is not None:
                    self.threads[1].join(timeout=.5)
                    raise RuntimeError(self.error or 'OWの音声取得が終了しました。ゲームを確認して再開してください。')

    def close(self):
        self.closed.set()
        try:
            if self.process.poll() is None:
                self.process.stdin.write(b'stop\n')
                self.process.stdin.flush()
                self.process.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            self.process.kill()
            self.process.wait(timeout=2)
        finally:
            for thread in self.threads:
                thread.join(timeout=1)
            for pipe in (self.process.stdin, self.process.stdout, self.process.stderr):
                try:
                    pipe.close()
                except OSError:
                    # The helper may exit between poll() and a stop write.
                    # Closing that broken stdin must not prevent closing output pipes.
                    pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
