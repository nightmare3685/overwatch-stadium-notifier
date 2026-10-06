"""Windows integration checks (silent helper processes; no sound playback)."""
import os
import subprocess
import sys
import threading
import time
import unittest
from process_audio import ProcessAudio, HELPER, FLAGS


@unittest.skipUnless(os.name == 'nt' and HELPER.exists(), 'Windows helper required')
class ProcessCaptureTests(unittest.TestCase):
    def test_invalid_target_fails(self):
        p = subprocess.run([str(HELPER), '0'], capture_output=True, timeout=5, creationflags=FLAGS)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn(b'ERROR', p.stderr)
        self.assertEqual(p.stdout, b'')

    def test_silent_target_can_be_cancelled(self):
        target = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)'], creationflags=FLAGS)
        stop = threading.Event()
        try:
            with ProcessAudio(target.pid) as capture:
                blocks = capture.blocks(stop)
                self.assertIsNone(next(blocks))
                timer = threading.Timer(.3, stop.set)
                timer.start()
                for _ in blocks:
                    pass
                timer.join()
            self.assertIsNotNone(capture.process.poll())
        finally:
            target.terminate(); target.wait(timeout=3)

    def test_target_exit_stops_capture(self):
        target = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)'], creationflags=FLAGS)
        stop = threading.Event()
        try:
            with ProcessAudio(target.pid) as capture:
                blocks = capture.blocks(stop)
                self.assertIsNone(next(blocks))
                target.terminate(); target.wait(timeout=3)
                deadline = threading.Timer(3, stop.set)
                deadline.start()
                try:
                    with self.assertRaises(RuntimeError):
                        for _ in blocks:
                            pass
                finally:
                    deadline.cancel()
        finally:
            if target.poll() is None:
                target.terminate(); target.wait(timeout=3)


if __name__ == '__main__':
    unittest.main()
