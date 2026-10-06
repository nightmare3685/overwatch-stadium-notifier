"""Windows GUI: listen only to the Overwatch process and display local detections."""
import queue
import threading
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox
import numpy as np
import time
from process_audio import ProcessAudio, find_overwatch
from detector import Detector, LABELS


class App:
    def __init__(self, root):
        self.root = root
        root.title('Overwatch Stadium — 音検知テスト')
        root.geometry('680x450')
        self.messages = queue.Queue()
        self.stop = threading.Event()
        self.worker = None
        self.closing = False
        body = ttk.Frame(root, padding=18)
        body.pack(fill='both', expand=True)
        ttk.Label(body, text='② / ③ の音を検知して、ここに表示します', font=('', 15)).pack(anchor='w')
        ttk.Label(body, text='OWの音だけを使用 • マイク不使用 • 録音保存なし • Discord送信なし').pack(anchor='w', pady=(5, 14))
        ttk.Label(body, text='Overwatch.exe を自動選択 • YouTube / Discord の再生音は対象外').pack(anchor='w')
        options = ttk.Frame(body)
        options.pack(fill='x', pady=12)
        ttk.Label(options, text='検知しきい値').pack(side='left')
        self.threshold = tk.StringVar(value='0.90')
        ttk.Entry(options, textvariable=self.threshold, width=7).pack(side='left', padx=8)
        ttk.Label(options, text='連続通知を抑える時間: 30秒').pack(side='left')
        buttons = ttk.Frame(body)
        buttons.pack(fill='x')
        self.start_button = ttk.Button(buttons, text='検知開始', command=self.start)
        self.start_button.pack(side='left')
        self.stop_button = ttk.Button(buttons, text='停止', command=self.stop.set, state='disabled')
        self.stop_button.pack(side='left', padx=8)
        self.status = tk.StringVar(value='停止中 — Overwatchを起動して「検知開始」を押してください')
        ttk.Label(body, textvariable=self.status, wraplength=630).pack(anchor='w', pady=12)
        self.scores = tk.StringVar(value='② —   ③ —')
        ttk.Label(body, textvariable=self.scores).pack(anchor='w')
        self.log = tk.Text(body, height=10, state='disabled', wrap='word')
        self.log.pack(fill='both', expand=True, pady=(10, 0))
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
            messagebox.showerror('設定を確認', str(exc))
            return
        self.stop.clear()
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
                    events, scores = detector.feed(samples)
                    self.messages.put(('scores', scores))
                    for event in events:
                        if now - last_event >= 30:
                            last_event = now
                            self.messages.put(('event', event))
        except Exception as exc:
            self.messages.put(('error', str(exc)))
        finally:
            self.messages.put(('done', None))

    def append(self, text):
        self.log.config(state='normal')
        self.log.insert('end', text + '\n')
        self.log.see('end')
        self.log.config(state='disabled')

    def poll(self):
        try:
            while True:
                kind, value = self.messages.get_nowait()
                if kind == 'status':
                    self.status.set(value)
                elif kind == 'scores':
                    self.scores.set('   '.join(f'{LABELS[k]}: {v:.2f}' for k, v in value.items()))
                elif kind == 'event':
                    text = f"{datetime.now():%H:%M:%S} マッチが見つかりました！ {LABELS[value['sound']]} ({value['score']:.2f})"
                    self.status.set(text)
                    self.append(text)
                elif kind == 'error':
                    self.status.set('音声入力エラー — 停止しました')
                    self.append('エラー: ' + value + '\nOverwatchを確認して検知を再開してください。')
                elif kind == 'done':
                    self.start_button.config(state='normal')
                    self.stop_button.config(state='disabled')
                    if self.stop.is_set():
                        self.status.set('停止中')
        except queue.Empty:
            pass
        if self.closing and (not self.worker or not self.worker.is_alive()):
            self.root.destroy()
        else:
            self.root.after(100, self.poll)

    def close(self):
        self.closing = True
        self.stop.set()


if __name__ == '__main__':
    root = tk.Tk()
    App(root)
    root.mainloop()
