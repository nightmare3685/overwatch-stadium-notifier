"""UI translations only; changing language does not change audio templates."""
ENGLISH = {
    'OWの音だけを使用 • マイク不使用 • 録音保存なし • Discord通知は任意':
        'OW audio only • No microphone • No recordings • Optional Discord alerts',
    'Discord設定': 'Discord settings',
    '検知時にDiscordへ送信する': 'Send to Discord when a match is detected',
    'テスト送信': 'Send test',
    '音声は送信しません。通知文と時刻だけを送信します。':
        'No audio is sent. Only notification text and the time are sent.',
    'URLは今回の起動中のみ保持します。再起動後は再入力してください。':
        'The URL is kept only for this session. Enter it again after restarting.',
    'Discord: 未送信': 'Discord: no messages sent',
    'Discord: 送信中…': 'Discord: sending…',
    'OW通知のテスト送信です。': 'This is an Overwatch notification test.',
    'テスト送信が完了しました。': 'Test message sent.',
    'マッチ通知を送信しました。': 'Match notification sent.',
    'DiscordのWebhook URLを入力してください。': 'Enter a valid Discord webhook URL.',
    'Discordへの送信を確認できませんでした。': 'Could not confirm delivery to Discord.',
    'Discordの送信制限です。少し待ってから再送してください。':
        'Discord rate limit reached. Wait before trying again.',
    'Webhookが無効、または送信権限がありません。URLを確認してください。':
        'The webhook is invalid or access is denied. Check the URL.',
    'Discordへの送信に失敗しました。': 'Failed to send to Discord.',
    'Discordに接続できませんでした。通信環境を確認してください。':
        'Could not connect to Discord. Check your internet connection.',
    '動作確認はSteam版のみです。Battle.net版は未検証です。':
        'Tested only with the Steam version. The Battle.net version has not been tested.',
    'マッチ成立音を検知中…': 'Listening for the match-found sound…',
    '最後にマッチングした時間: まだ検知していません': 'Last match detected: none yet',
    '最後にマッチングした時間: {timestamp}': 'Last match detected: {timestamp}',
    'Overwatch起動中のみ利用できます。先にゲームを起動してください。':
        'Only available while Overwatch is running. Please launch the game first.',
    'Overwatchを起動してください': 'Please launch Overwatch',
    'Overwatchが起動していません。Overwatchを起動してから「検知開始」を押してください。':
        'Overwatch is not running. Please launch Overwatch, then click Start detection.',
    'Overwatchが起動していません。ゲームを起動してから検知開始を押してください。':
        'Overwatch is not running. Open the game, then click Start detection.',
    'Overwatchが複数あります。1つだけ起動した状態で検知を開始してください。':
        'Multiple Overwatch processes found. Run only one instance before starting detection.',
    'OWの音声取得を開始できませんでした。': 'Could not start Overwatch audio capture.',
    'OWの音声取得がタイムアウトしました。': 'Overwatch audio capture timed out.',
    'OWの音声取得が終了しました。ゲームを確認して再開してください。':
        'Overwatch audio capture ended. Check the game and restart detection.',
    'Overwatch Stadium — 音検知テスト': 'Overwatch Stadium — Sound Detector',
    '音を検知して、ここに表示します': 'Detected sounds appear here',
    'OWの音だけを使用 • マイク不使用 • 録音保存なし • Discord送信なし':
        'OW audio only • No microphone • No recordings • No Discord sending',
    'Overwatch.exe を自動選択 • YouTube / Discord の再生音は対象外':
        'Auto-selects Overwatch.exe • Excludes YouTube / Discord audio',
    '検知しきい値': 'Detection threshold',
    '連続通知を抑える時間: 30秒': 'Notification cooldown: 30 seconds',
    '検知開始': 'Start detection',
    '停止': 'Stop',
    '停止中 — Overwatchを起動して「検知開始」を押してください':
        'Stopped — Open Overwatch and click Start detection',
    '検知画面': 'Detection',
    '詳細ログ': 'Detailed log',
    '音声受信: 未開始': 'Audio: not started',
    '準備完了。検知開始後は、開始・音声受信・一致度をここに表示します。':
        'Ready. Capture status, audio input and similarity scores appear here.',
    'しきい値は0.50〜1.00で指定してください。': 'Enter a threshold between 0.50 and 1.00.',
    '開始できません: {error}': 'Cannot start: {error}',
    '設定を確認': 'Check settings',
    '音声受信: 接続待ち': 'Audio: connecting',
    '検知開始を受付: Overwatch PID {pid} / しきい値 {threshold:.2f}':
        'Starting detection: Overwatch PID {pid} / threshold {threshold:.2f}',
    'OW専用の音声取得を開始しています…': 'Connecting to Overwatch audio…',
    '検知中 — Overwatchのみ (PID {pid})': 'Detecting — Overwatch only (PID {pid})',
    'マッチが見つかりました！': 'Match found!',
    'この表示は10秒後に自動で消えます': 'This message disappears automatically after 10 seconds.',
    '音声取得中… {duration}': 'Capturing audio… {duration}',
    '音声受信 {duration} / 入力ピーク {db:.0f} dBFS / 区間最大 {match:.2f}':
        'Audio received {duration} / peak {db:.0f} dBFS / interval max {match:.2f}',
    'マッチが見つかりました！ {sound} ({score:.2f})': 'Match found! {sound} ({score:.2f})',
    '音声入力エラー — 停止しました': 'Audio input error — stopped',
    'エラー: {error}\nOverwatchを確認して検知を再開してください。':
        'Error: {error}\nCheck Overwatch and restart detection.',
    '音声取得終了 — {duration}': 'Audio capture ended — {duration}',
    '監視終了: 受信 {duration} / 最大一致度 {match:.2f}':
        'Detection ended: received {duration} / max similarity {match:.2f}',
    '停止中': 'Stopped',
    '音声データ待ち — OW側で音が鳴っているか確認してください':
        'Waiting for audio — check that Overwatch is playing sound',
    '音声データが5秒以上届いていません。OWが無音の場合もこの表示になります。':
        'No audio received for over 5 seconds. Overwatch may be silent.',
    'マッチ成立音': 'Match-found sound',
}


def translate(text, language='JPN'):
    return ENGLISH.get(text, text) if language == 'ENG' else text


def format_duration(seconds, language='JPN'):
    total = max(0, int(seconds + 1e-6))
    minutes, seconds = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if language == 'ENG':
        if hours:
            return f'{hours}h {minutes}m {seconds}s'
        if minutes:
            return f'{minutes}m {seconds}s'
        return f'{seconds}s'
    if hours:
        return f'{hours}時間{minutes}分{seconds}秒'
    if minutes:
        return f'{minutes}分{seconds}秒'
    return f'{seconds}秒'
