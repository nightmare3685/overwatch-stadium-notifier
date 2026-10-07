"""GUI diagnostic lifecycle tests; no live audio capture."""
import time
import tkinter as tk
import unittest
from unittest.mock import patch
from app import App


class SilentAudio:
    def __init__(self, pid):
        pass
    def __enter__(self):
        return self
    def __exit__(self, *_):
        pass
    def blocks(self, stop):
        yield None
        for _ in range(10):
            yield bytes(3200)


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = App(self.root)

    def tearDown(self):
        self.root.destroy()

    def test_successful_capture_logs_without_detection(self):
        with patch('app.find_overwatch', return_value=123), patch('app.ProcessAudio', SilentAudio):
            self.app.start()
            self.app.worker.join(timeout=3)
            self.assertFalse(self.app.worker.is_alive())
            self.app.poll()
        log = self.app.log.get('1.0', 'end')
        for text in ('検知開始を受付', '検知中', '音声受信', '監視終了'):
            self.assertIn(text, log)
        self.assertNotIn('マッチが見つかりました', log)
        self.assertAlmostEqual(self.app.received_seconds, 1.)

    def test_start_failure_is_logged(self):
        with patch('app.find_overwatch', side_effect=ValueError('OW is not running')), patch('app.messagebox.showerror'):
            self.app.start()
        self.assertIn('開始できません: OW is not running', self.app.log.get('1.0', 'end'))

    def test_waiting_for_audio_is_visible(self):
        class Worker:
            def is_alive(self): return True
        self.app.worker = Worker()
        self.app.last_input = time.monotonic() - 20
        self.app.last_wait_log = 0
        self.app.poll()
        self.assertIn('音声データ待ち', self.app.input_status.get())
        self.assertIn('5秒以上', self.app.log.get('1.0', 'end'))


if __name__ == '__main__':
    unittest.main()
