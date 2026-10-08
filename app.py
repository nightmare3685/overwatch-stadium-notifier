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
from process_audio import ProcessAudio, find_overwatch, OverwatchNotRunningError
from detector import Detector, LABELS
from language import translate, format_duration


class App:
    def __init__(self, root):
        self.root = root
        self.language = tk.StringVar(value='JPN')
        self.translated_widgets = []
        self.translated_values = {}
        self.log_entries = []
        self.current_scores = None
        root.title('Overwatch Stadium — 音検知テスト')
        root.geometry('840x660')
        root.minsize(840, 660)
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
        self.capture_active = False
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
        language_bar = ttk.Frame(body)
        language_bar.pack(fill='x')
        ttk.Label(language_bar, text='Language / 言語').pack(side='left')
        self.language_selector = ttk.Combobox(language_bar, textvariable=self.language,
                                              values=('JPN', 'ENG'), state='readonly', width=5)
        self.language_selector.pack(side='left', padx=8)
        self.language_selector.bind('<<ComboboxSelected>>', self.change_language)
        self.label(body, '音を検知して、ここに表示します', font=(self.font_family, 17, 'bold')).pack(anchor='w')
        self.label(body, 'OWの音だけを使用 • マイク不使用 • 録音保存なし • Discord送信なし', wraplength=780).pack(anchor='w', pady=(5, 14))
        self.label(body, 'Overwatch.exe を自動選択 • YouTube / Discord の再生音は対象外', wraplength=780).pack(anchor='w')
        self.label(body, 'Overwatch起動中のみ利用できます。先にゲームを起動してください。', wraplength=780).pack(anchor='w')
        self.label(body, '動作確認はSteam版のみです。Battle.net版は未検証です。', wraplength=780).pack(anchor='w')
        options = ttk.Frame(body)
        options.pack(fill='x', pady=12)
        self.label(options, '検知しきい値').pack(side='left')
        self.threshold = tk.StringVar(value='0.90')
        ttk.Entry(options, textvariable=self.threshold, width=7, font=(self.font_family, 11)).pack(side='left', padx=8)
        self.label(options, '連続通知を抑える時間: 30秒').pack(side='left')
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
        self.notification = tk.StringVar(value='停止中')
        ttk.Label(monitor, textvariable=self.notification, font=(self.font_family, 28, 'bold'),
                  foreground='#12652e', anchor='center', wraplength=740).pack(fill='both', expand=True)
        self.notification_hint = tk.StringVar(value='')
        ttk.Label(monitor, textvariable=self.notification_hint, anchor='center',
                  wraplength=740).pack(fill='x', pady=(0, 12))
        self.last_match = tk.StringVar()
        self.set_text(self.last_match, '最後にマッチングした時間: まだ検知していません')
        ttk.Label(monitor, textvariable=self.last_match, anchor='center',
                  wraplength=740).pack(fill='x', pady=(0, 8))
        self.scores = tk.StringVar(value='—')
        ttk.Label(details, textvariable=self.scores, wraplength=630).pack(anchor='w')
        self.log = tk.Text(details, height=10, state='disabled', wrap='word',
                           font=(self.font_family, 11), padx=10, pady=8, spacing1=3, spacing3=3)
        self.log.pack(fill='both', expand=True, pady=(10, 0))
        self.set_text(self.status, '停止中 — Overwatchを起動して「検知開始」を押してください')
        self.set_text(self.input_status, '音声受信: 未開始')
        self.append('準備完了。検知開始後は、開始・音声受信・一致度をここに表示します。')
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(100, self.poll)

    def tr(self, text, **values):
        values = values.copy()
        if 'seconds' in values:
            values['duration'] = format_duration(values.pop('seconds'), self.language.get())
        if 'sound' in values:
            values['sound'] = translate(LABELS[values['sound']], self.language.get())
        if 'error' in values:
            values['error'] = translate(values['error'], self.language.get())
        return translate(text, self.language.get()).format(**values)

    def label(self, parent, text, **options):
        widget = ttk.Label(parent, text=self.tr(text), **options)
        self.translated_widgets.append((widget, text))
        return widget

    def set_text(self, variable, text, **values):
        self.translated_values[str(variable)] = (variable, text, values)
        variable.set(self.tr(text, **values))

    def change_language(self, _event=None):
        self.root.title(self.tr('Overwatch Stadium — 音検知テスト'))
        for widget, text in self.translated_widgets:
            widget.configure(text=self.tr(text))
        for variable, text, values in self.translated_values.values():
            variable.set(self.tr(text, **values))
        self.start_button.configure(text=self.tr('検知開始'))
        self.stop_button.configure(text=self.tr('停止'))
        self.tabs.tab(0, text=self.tr('検知画面'))
        self.tabs.tab(1, text=self.tr('詳細ログ'))
        if self.notification_timer is not None:
            self.notification.set(self.tr('マッチが見つかりました！'))
            self.notification_hint.set(self.tr('この表示は10秒後に自動で消えます'))
        else:
            self.clear_notification()
        self.render_scores()
        self.render_log()

    def render_scores(self):
        self.scores.set('—' if self.current_scores is None else
                        '   '.join(f'{self.tr(LABELS[k])}: {v:.2f}'
                                   for k, v in self.current_scores.items()))

    def start(self):
        if self.worker and self.worker.is_alive():
            return
        try:
            threshold = float(self.threshold.get())
            if not .5 <= threshold <= 1:
                raise ValueError('しきい値は0.50〜1.00で指定してください。')
            pid = find_overwatch()
        except (ValueError, OSError, RuntimeError) as exc:
            self.append('開始できません: {error}', error=str(exc))
            if isinstance(exc, OverwatchNotRunningError):
                self.set_text(self.status, 'Overwatchを起動してください')
                messagebox.showinfo(self.tr('Overwatchを起動してください'), translate(str(exc), self.language.get()))
                return
            messagebox.showerror(self.tr('設定を確認'), translate(str(exc), self.language.get()))
            return
        self.stop.clear()
        self.capture_active = False
        self.clear_notification()
        self.received_seconds = 0.
        self.maximum_scores = dict.fromkeys(LABELS, 0.)
        self.last_input = time.monotonic()
        self.last_wait_log = self.last_input
        self.set_text(self.input_status, '音声受信: 接続待ち')
        self.current_scores = None
        self.scores.set('—')
        self.append('検知開始を受付: Overwatch PID {pid} / しきい値 {threshold:.2f}', pid=pid, threshold=threshold)
        self.start_button.config(state='disabled')
        self.stop_button.config(state='normal')
        self.set_text(self.status, 'OW専用の音声取得を開始しています…')
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
                        self.messages.put(('status', pid))
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
                            event['detected_at'] = datetime.now().astimezone()
                            self.messages.put(('event', event))
        except Exception as exc:
            try:
                find_overwatch()
            except OverwatchNotRunningError:
                self.messages.put(('not_running', None))
            except Exception:
                self.messages.put(('error', str(exc)))
            else:
                self.messages.put(('error', str(exc)))
        finally:
            self.messages.put(('done', None))

    def append(self, text, **values):
        self.logger.info(self.tr(text, **values))
        self.log_entries.append((datetime.now().strftime('%H:%M:%S'), text, values))
        self.log_entries = self.log_entries[-500:]
        self.render_log()

    def render_log(self):
        self.log.config(state='normal')
        self.log.delete('1.0', 'end')
        self.log.insert('end', ''.join(f'{stamp} {self.tr(text, **values)}\n'
                                      for stamp, text, values in self.log_entries))
        self.log.see('end')
        self.log.config(state='disabled')

    def clear_notification(self):
        if self.notification_timer is not None:
            self.root.after_cancel(self.notification_timer)
            self.notification_timer = None
        self.notification.set(self.tr('マッチ成立音を検知中…' if self.capture_active else '停止中'))
        self.notification_hint.set('')

    def show_match(self, detected_at=None):
        self.clear_notification()
        detected_at = detected_at or datetime.now().astimezone()
        self.set_text(self.last_match, '最後にマッチングした時間: {timestamp}',
                      timestamp=detected_at.strftime('%Y/%m/%d %H:%M:%S'))
        self.notification.set(self.tr('マッチが見つかりました！'))
        self.notification_hint.set(self.tr('この表示は10秒後に自動で消えます'))
        self.tabs.select(0)
        self.notification_timer = self.root.after(10000, self.clear_notification)

    def poll(self):
        try:
            while True:
                kind, value = self.messages.get_nowait()
                if kind == 'status':
                    self.capture_active = True
                    if self.notification_timer is None:
                        self.clear_notification()
                    self.set_text(self.status, '検知中 — Overwatchのみ (PID {pid})', pid=value)
                    self.append('検知中 — Overwatchのみ (PID {pid})', pid=value)
                elif kind == 'input':
                    self.last_input = time.monotonic()
                    self.received_seconds += value
                    self.set_text(self.input_status, '音声取得中… {duration}', seconds=self.received_seconds)
                elif kind == 'diagnostic':
                    for key, score in value['scores'].items():
                        self.maximum_scores[key] = max(self.maximum_scores[key], score)
                    self.append('音声受信 {duration} / 入力ピーク {db:.0f} dBFS / 区間最大 {match:.2f}',
                                seconds=value['seconds'], db=value['db'], **value['scores'])
                elif kind == 'scores':
                    for key, score in value.items():
                        self.maximum_scores[key] = max(self.maximum_scores[key], score)
                    self.current_scores = value.copy()
                    self.render_scores()
                elif kind == 'event':
                    self.show_match(value.get('detected_at'))
                    self.append('マッチが見つかりました！ {sound} ({score:.2f})', sound=value['sound'], score=value['score'])
                elif kind == 'error':
                    self.set_text(self.status, '音声入力エラー — 停止しました')
                    self.append('エラー: {error}\nOverwatchを確認して検知を再開してください。', error=value)
                elif kind == 'not_running':
                    self.set_text(self.status, 'Overwatchを起動してください')
                    self.append('Overwatchが起動していません。Overwatchを起動してから「検知開始」を押してください。')
                elif kind == 'done':
                    self.capture_active = False
                    if self.notification_timer is None:
                        self.clear_notification()
                    self.set_text(self.input_status, '音声取得終了 — {duration}', seconds=self.received_seconds)
                    self.append('監視終了: 受信 {duration} / 最大一致度 {match:.2f}',
                                seconds=self.received_seconds, **self.maximum_scores)
                    self.start_button.config(state='normal')
                    self.stop_button.config(state='disabled')
                    if self.stop.is_set() or self.translated_values[str(self.status)][1] == '検知中 — Overwatchのみ (PID {pid})':
                        self.set_text(self.status, '停止中')
        except queue.Empty:
            pass
        now = time.monotonic()
        if (self.worker and self.worker.is_alive() and self.last_input is not None
                and now - self.last_input >= 5 and now - self.last_wait_log >= 10):
            self.set_text(self.input_status, '音声データ待ち — OW側で音が鳴っているか確認してください')
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
