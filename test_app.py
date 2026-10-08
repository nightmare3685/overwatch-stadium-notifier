"""GUI diagnostic lifecycle tests; no live audio capture."""
import time
import threading
import tkinter as tk
import unittest
from unittest.mock import patch
from app import App
from detector import Detector, LABELS
import numpy as np
from datetime import datetime
from process_audio import OverwatchNotRunningError, find_overwatch
from types import SimpleNamespace


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
        for timer in self.root.tk.call('after', 'info'):
            self.root.after_cancel(timer)
        self.root.update_idletasks()
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

    def test_only_match_sound_is_loaded_and_scored(self):
        detector = Detector()
        self.assertEqual(set(LABELS), {'match'})
        self.assertTrue(all(key.split('__', 1)[0] == 'match' for key in detector.templates))
        events, scores = detector.feed(np.zeros(16000, dtype=np.float32))
        self.assertEqual(set(scores), {'match'})
        self.assertEqual(events, [])

    def test_start_failure_is_logged(self):
        with patch('app.find_overwatch', side_effect=ValueError('OW is not running')), patch('app.messagebox.showerror'):
            self.app.start()
        self.assertIn('開始できません: OW is not running', self.app.log.get('1.0', 'end'))

    def test_input_updates_one_counter_and_keeps_details_off_main_tab(self):
        for _ in range(25):
            self.app.messages.put(('input', .1))
        self.app.messages.put(('diagnostic', {'seconds': 2.5, 'db': -12,
                                             'scores': {'match': .4}}))
        self.app.poll()
        self.assertEqual(self.app.input_status.get(), '音声取得中… 2秒')
        self.assertEqual(self.app.tabs.index(self.app.tabs.select()), 0)
        self.assertIn('入力ピーク', self.app.log.get('1.0', 'end'))
        self.assertEqual(str(self.app.log.master), self.app.tabs.tabs()[1])

    def test_match_is_immediate_and_expires_without_erasing_status_or_log(self):
        self.app.tabs.select(1)
        self.app.capture_active = True
        self.app.status.set('検知中')
        self.app.messages.put(('event', {'sound': 'match', 'score': .95,
                                         'detected_at': datetime(2026, 10, 8, 12, 34, 56)}))
        self.app.poll()
        self.assertEqual(self.app.notification.get(), 'マッチが見つかりました！')
        self.assertEqual(self.app.notification_hint.get(), 'この表示は10秒後に自動で消えます')
        self.assertEqual(self.app.tabs.index(self.app.tabs.select()), 0)
        deadline = time.monotonic() + 10.2
        while time.monotonic() < deadline:
            self.root.update()
            time.sleep(.02)
        self.assertEqual(self.app.notification.get(), 'マッチ成立音を検知中…')
        self.assertEqual(self.app.last_match.get(), '最後にマッチングした時間: 2026/10/08 12:34:56')
        self.assertEqual(self.app.notification_hint.get(), '')
        self.assertEqual(self.app.status.get(), '検知中')
        self.assertIn('マッチが見つかりました！', self.app.log.get('1.0', 'end'))

    def test_new_notification_cancels_previous_expiry(self):
        self.app.show_match()
        previous_timer = self.app.notification_timer
        self.app.show_match()
        self.assertNotEqual(previous_timer, self.app.notification_timer)
        self.assertNotIn(previous_timer, self.root.tk.call('after', 'info'))

    def test_language_switch_preserves_capture_and_notification_timer(self):
        self.app.messages.put(('status', 123))
        self.app.messages.put(('input', 65))
        self.app.messages.put(('scores', {'match': .95}))
        self.app.messages.put(('event', {'sound': 'match', 'score': .95}))
        self.app.poll()
        timer = self.app.notification_timer
        self.app.language.set('ENG')
        self.app.change_language()
        self.assertEqual(self.app.input_status.get(), 'Capturing audio… 1m 5s')
        self.assertEqual(self.app.notification.get(), 'Match found!')
        self.assertEqual(self.app.notification_hint.get(), 'This message disappears automatically after 10 seconds.')
        self.assertEqual(self.app.start_button.cget('text'), 'Start detection')
        self.assertEqual(self.app.tabs.tab(1, 'text'), 'Detailed log')
        self.assertIn('Overwatch only (PID 123)', self.app.status.get())
        self.assertIn('Match-found sound', self.app.scores.get())
        self.assertIn('Match found!', self.app.log.get('1.0', 'end'))
        self.assertNotIn('マッチが見つかりました', self.app.log.get('1.0', 'end'))
        self.assertEqual(self.app.notification_timer, timer)
        self.app.language.set('JPN')
        self.app.change_language()
        self.assertEqual(self.app.input_status.get(), '音声取得中… 1分5秒')
        self.assertEqual(self.app.notification.get(), 'マッチが見つかりました！')
        self.assertEqual(self.app.notification_timer, timer)
        self.assertEqual(self.app.received_seconds, 65)

    def test_english_start_error_and_completed_capture(self):
        self.app.language.set('ENG')
        self.app.change_language()
        with patch('app.find_overwatch', side_effect=OverwatchNotRunningError()), patch('app.messagebox.showinfo') as dialog:
            self.app.start()
        self.assertEqual(dialog.call_args.args[0], 'Please launch Overwatch')
        self.assertIn('Overwatch is not running', dialog.call_args.args[1])
        self.assertEqual(self.app.status.get(), 'Please launch Overwatch')
        self.app.messages.put(('input', 3723))
        self.app.messages.put(('done', None))
        self.app.stop.set()
        self.app.poll()
        self.assertEqual(self.app.input_status.get(), 'Audio capture ended — 1h 2m 3s')
        self.assertEqual(self.app.status.get(), 'Stopped')

    def test_missing_game_is_identified_and_guidance_survives_done(self):
        with patch('process_audio.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout='', stderr='')):
            with self.assertRaises(OverwatchNotRunningError):
                find_overwatch()
        self.app.messages.put(('status', 123))
        self.app.messages.put(('not_running', None))
        self.app.messages.put(('done', None))
        self.app.poll()
        self.assertEqual(self.app.status.get(), 'Overwatchを起動してください')
        self.assertEqual(self.app.notification.get(), '停止中')
        self.assertFalse(self.app.capture_active)

    def test_waiting_and_last_match_translate_and_remain_after_stop(self):
        self.app.messages.put(('status', 123))
        self.app.poll()
        self.assertEqual(self.app.notification.get(), 'マッチ成立音を検知中…')
        self.app.show_match(datetime(2026, 10, 8, 12, 34, 56))
        self.app.clear_notification()
        self.app.language.set('ENG')
        self.app.change_language()
        self.assertEqual(self.app.notification.get(), 'Listening for the match-found sound…')
        self.assertEqual(self.app.last_match.get(), 'Last match detected: 2026/10/08 12:34:56')
        self.app.messages.put(('done', None))
        self.app.poll()
        self.assertEqual(self.app.notification.get(), 'Stopped')
        self.assertIn('12:34:56', self.app.last_match.get())

    def test_waiting_for_audio_is_visible(self):
        class Worker:
            def is_alive(self): return True
        self.app.worker = Worker()
        self.app.last_input = time.monotonic() - 20
        self.app.last_wait_log = 0
        self.app.poll()
        self.assertIn('音声データ待ち', self.app.input_status.get())
        self.assertIn('5秒以上', self.app.log.get('1.0', 'end'))

    def test_discord_is_opt_in_and_duplicate_events_are_suppressed(self):
        event = {'sound': 'match', 'score': .95}
        with patch('app.send_notification') as send:
            self.app.messages.put(('event', event))
            self.app.poll()
            send.assert_not_called()
            self.app.webhook_url.set('https://discord.com/api/webhooks/123/test_token')
            self.app.discord_enabled.set(True)
            self.app.messages.put(('event', event))
            self.app.messages.put(('event', event))
            self.app.poll()
            for worker in self.app.discord_workers:
                worker.join(timeout=2)
            self.app.poll()
            send.assert_called_once()
            self.assertIn('マッチが見つかりました！', send.call_args.args[1])
            self.assertIn('マッチ通知を送信しました', self.app.discord_status.get())
            self.assertNotIn('test_token', self.app.log.get('1.0', 'end'))

    def test_discord_test_send_does_not_require_game_or_enable_auto_send(self):
        self.app.webhook_url.set('https://discord.com/api/webhooks/123/test_token')
        with patch('app.send_notification') as send:
            self.app.test_discord()
            for worker in self.app.discord_workers:
                worker.join(timeout=2)
            self.app.poll()
            send.assert_called_once()
        self.assertFalse(self.app.discord_enabled.get())
        self.assertIn('テスト送信が完了', self.app.discord_status.get())
        self.app.language.set('ENG')
        self.app.change_language()
        self.assertIn('Test message sent.', self.app.discord_status.get())

    def test_slow_discord_failure_does_not_block_audio_or_leak_url(self):
        entered, release = threading.Event(), threading.Event()
        def slow_send(*_):
            entered.set()
            release.wait(timeout=3)
            raise RuntimeError('https://discord.com/api/webhooks/123/test_token')
        self.app.webhook_url.set('https://discord.com/api/webhooks/123/test_token')
        with patch('app.send_notification', side_effect=slow_send):
            self.app.test_discord()
            try:
                self.assertTrue(entered.wait(timeout=2))
                self.app.messages.put(('input', 65))
                self.app.poll()
                self.assertEqual(self.app.input_status.get(), '音声取得中… 1分5秒')
            finally:
                release.set()
                for worker in self.app.discord_workers:
                    worker.join(timeout=2)
            self.app.poll()
        self.assertIn('送信に失敗', self.app.discord_status.get())
        self.assertNotIn('test_token', self.app.log.get('1.0', 'end'))
        self.assertEqual(str(self.app.test_send_button.cget('state')), 'normal')


if __name__ == '__main__':
    unittest.main()
