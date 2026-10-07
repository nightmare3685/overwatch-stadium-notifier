"""Windows GUI: listen only to the Overwatch process and display local detections."""
import queue
import threading
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import font as tkfont
import numpy as np
import time
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from process_audio import ProcessAudio, find_overwatch
from detector import Detector, LABELS


class App:
    def __init__(self, root):
        self.root = root
        root.title('Overwatch Stadium — 音検知テスト')
        root.geometry('840x600')
        root.minsize(840, 600)
        available_fonts = set(tkfont.families(root))
        self.font_family = next((name for name in ('Meiryo', 'メイリオ', 'Yu Gothic UI')
                                 if name in available_fonts),
                                tkfont.nametofont('TkDefaultFont').actual('family'))
        for name in ('TkDefaultFont', 'TkTextFont', 'TkMenuFont', 'TkHeadingFont'):
            tkfont.nametofont(name).configure(family=self.font_family, size=11)
        style = ttk.Style(root)
        style.configure('.', font=(self.font_family, 11))
        style.configure('TButton', padding=(12, 6))
        style.configure('TNotebook.Tab', padding=(14, 7))
        self.messages = queue.Queue()
        self.stop = threading.Event()
        self.worker = None
        self.closing = False
        self.notification_timer = None
        self.last_input = None
        self.last_wait_log = 0.
        self.received_seconds = 0.
        self.maximum_scores = dict.fromkeys(LABELS, 0.)
        self.logger = logging.getLogger('stadium.diagnostics')
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        if not self.logger.handlers:
            try:
                handler = RotatingFileHandler(Path(__file__).with_name('diagnostics.log'),
                                             maxBytes=500000, backupCount=2, encoding='utf-8')
                handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
                self.logger.addHandler(handler)
            except OSError:
                self.logger.addHandler(logging.NullHandler())
        body = ttk.Frame(root, padding=18)
        body.pack(fill='both', expand=True)
        ttk.Label(body, text='音を検知して、ここに表示します', font=(self.font_family, 17, 'bold')).pack(anchor='w')
        ttk.Label(body, text='OWの音だけを使用 • マイク不使用 • 録音保存なし • Discord送信なし').pack(anchor='w', pady=(5, 14))
        ttk.Label(body, text='Overwatch.exe を自動選択 • YouTube / Discord の再生音は対象外').pack(anchor='w')
        options = ttk.Frame(body)
        options.pack(fill='x', pady=12)
        ttk.Label(options, text='検知しきい値').pack(side='left')
        self.threshold = tk.StringVar(value='0.90')
        ttk.Entry(options, textvariable=self.threshold, width=7, font=(self.font_family, 11)).pack(side='left', padx=8)
        ttk.Label(options, text='連続通知を抑える時間: 30秒').pack(side='left')
        buttons = ttk.Frame(body)
        buttons.pack(fill='x')
        self.start_button = ttk.Button(buttons, text='検知開始', command=self.start)
        self.start_button.pack(side='left')
        self.stop_button = ttk.Button(buttons, text='停止', command=self.stop.set, state='disabled')
        self.stop_button.pack(side='left', padx=8)
        self.status = tk.StringVar(value='停止中 — Overwatchを起動して「検知開始」を押してください')
        ttk.Label(body, textvariable=self.status, wraplength=630).pack(anchor='w', pady=12)
        self.tabs = ttk.Notebook(body)
        self.tabs.pack(fill='both', expand=True)
        monitor = ttk.Frame(self.tabs, padding=12)
        details = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(monitor, text='検知画面')
        self.tabs.add(details, text='詳細ログ')
        self.input_status = tk.StringVar(value='音声受信: 未開始')
        ttk.Label(monitor, textvariable=self.input_status, font=(self.font_family, 16), wraplength=740).pack(anchor='w', pady=5)
        self.notification = tk.StringVar(value='')
        ttk.Label(monitor, textvariable=self.notification, font=(self.font_family, 28, 'bold'),
                  foreground='#12652e', anchor='center', wraplength=740).pack(fill='both', expand=True)
        self.scores = tk.StringVar(value='② —   ③ —')
        ttk.Label(details, textvariable=self.scores, wraplength=630).pack(anchor='w')
        self.log = tk.Text(details, height=10, state='disabled', wrap='word',
                           font=(self.font_family, 11), padx=10, pady=8, spacing1=3, spacing3=3)
        self.log.pack(fill='both', expand=True, pady=(10, 0))
        self.append('準備完了。検知開始後は、開始・音声受信・一致度をここに表示します。')
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(100, self.poll)

    def start(self):
        if self.worker and self.worker.is_alive():
            return
        try:
            threshold = float(self.threshold.get())
            if not .5 <= threshold <= 1:
                raise ValueError('しきい値は0.50〜1.00で指定してください。')
            pid = find_overwatch()
        except (ValueError, OSError, RuntimeError) as exc:
            self.append('開始できません: ' + str(exc))
            messagebox.showerror('設定を確認', str(exc))
            return
        self.stop.clear()
        self.clear_notification()
        self.received_seconds = 0.
        self.maximum_scores = dict.fromkeys(LABELS, 0.)
        self.last_input = time.monotonic()
        self.last_wait_log = self.last_input
        self.input_status.set('音声受信: 接続待ち')
        self.scores.set('② —   ③ —')
        self.append(f'検知開始を受付: Overwatch PID {pid} / しきい値 {threshold:.2f}')
        self.start_button.config(state='disabled')
        self.stop_button.config(state='normal')
        self.status.set('OW専用の音声取得を開始しています…')
        self.worker = threading.Thread(target=self.listen, args=(pid, threshold), daemon=True)
        self.worker.start()

    def listen(self, pid, threshold):
        try:
            detector = Detector(threshold, cooldown=0)
            last_event = -float('inf')
            last_audio = time.monotonic()
            last_report = 0.
            peak = 0.
            received = 0.
            interval_scores = dict.fromkeys(LABELS, 0.)
            with ProcessAudio(pid) as audio:
                for raw in audio.blocks(self.stop):
                    if raw is None:
                        self.messages.put(('status', f'検知中 — Overwatchのみ (PID {pid})'))
                        continue
                    now = time.monotonic()
                    if now - last_audio > .5:
                        detector = Detector(threshold, cooldown=0)
                    last_audio = now
                    samples = np.frombuffer(raw, dtype='<i2').astype(np.float32) / 32768.
                    received += len(samples) / 16000
                    peak = max(peak, float(np.max(np.abs(samples))) if len(samples) else 0.)
                    events, scores = detector.feed(samples)
                    self.messages.put(('scores', scores))
                    for key, score in scores.items():
                        interval_scores[key] = max(interval_scores[key], score)
                    self.messages.put(('input', len(samples) / 16000))
                    if now - last_report >= 5:
                        db = 20 * np.log10(max(peak, 1e-8))
                        self.messages.put(('diagnostic', {'seconds': received, 'db': db,
                                                         'scores': interval_scores.copy()}))
                        peak = 0.
                        interval_scores = dict.fromkeys(LABELS, 0.)
                        last_report = now
                    for event in events:
                        if now - last_event >= 30:
                            last_event = now
                            self.messages.put(('event', event))
        except Exception as exc:
            self.messages.put(('error', str(exc)))
        finally:
            self.messages.put(('done', None))

    def append(self, text):
        self.logger.info(text)
        self.log.config(state='normal')
        self.log.insert('end', f'{datetime.now():%H:%M:%S} {text}\n')
        if int(self.log.index('end-1c').split('.')[0]) > 500:
            self.log.delete('1.0', '101.0')
        self.log.see('end')
        self.log.config(state='disabled')

    def clear_notification(self):
        if self.notification_timer is not None:
            self.root.after_cancel(self.notification_timer)
            self.notification_timer = None
        self.notification.set('')

    def show_match(self):
        self.clear_notification()
        self.notification.set('マッチが見つかりました！')
        self.tabs.select(0)
        self.notification_timer = self.root.after(5000, self.clear_notification)

    def poll(self):
        try:
            while True:
                kind, value = self.messages.get_nowait()
                if kind == 'status':
                    self.status.set(value)
                    self.append(value)
                elif kind == 'input':
                    self.last_input = time.monotonic()
                    self.received_seconds += value
                    self.input_status.set(f'音声取得中… {int(self.received_seconds + 1e-6)}秒')
                elif kind == 'diagnostic':
                    for key, score in value['scores'].items():
                        self.maximum_scores[key] = max(self.maximum_scores[key], score)
                    text = (f"音声受信 {value['seconds']:.1f}秒 / 入力ピーク {value['db']:.0f} dBFS / "
                            f"区間最大 ② {value['scores']['match']:.2f}・③ {value['scores']['stadium']:.2f}")
                    self.append(text)
                elif kind == 'scores':
                    for key, score in value.items():
                        self.maximum_scores[key] = max(self.maximum_scores[key], score)
                    self.scores.set('   '.join(f'{LABELS[k]}: {v:.2f}' for k, v in value.items()))
                elif kind == 'event':
                    text = f"{datetime.now():%H:%M:%S} マッチが見つかりました！ {LABELS[value['sound']]} ({value['score']:.2f})"
                    self.show_match()
                    self.append(text)
                elif kind == 'error':
                    self.status.set('音声入力エラー — 停止しました')
                    self.append('エラー: ' + value + '\nOverwatchを確認して検知を再開してください。')
                elif kind == 'done':
                    self.input_status.set(f'音声取得終了 — {int(self.received_seconds + 1e-6)}秒')
                    self.append(f"監視終了: 受信 {self.received_seconds:.1f}秒 / 最大一致度 "
                                f"② {self.maximum_scores['match']:.2f}・③ {self.maximum_scores['stadium']:.2f}")
                    self.start_button.config(state='normal')
                    self.stop_button.config(state='disabled')
                    if self.stop.is_set():
                        self.status.set('停止中')
        except queue.Empty:
            pass
        now = time.monotonic()
        if (self.worker and self.worker.is_alive() and self.last_input is not None
                and now - self.last_input >= 5 and now - self.last_wait_log >= 10):
            self.input_status.set('音声データ待ち — OW側で音が鳴っているか確認してください')
            self.append('音声データが5秒以上届いていません。OWが無音の場合もこの表示になります。')
            self.last_wait_log = now
        if self.closing and (not self.worker or not self.worker.is_alive()):
            self.root.destroy()
        else:
            self.root.after(100, self.poll)

    def close(self):
        self.closing = True
        self.clear_notification()
        self.stop.set()


if __name__ == '__main__':
    root = tk.Tk()
    App(root)
    root.mainloop()

