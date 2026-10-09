"""Text-only LINE Messaging API push; secrets never appear in error messages."""
import json
import re
from urllib import request, error
from discord_notify import NoRedirect, NotificationError

ENDPOINT = 'https://api.line.me/v2/bot/message/push'


def validate_line_settings(token, user_id):
    token, user_id = token.strip(), user_id.strip()
    if not token or len(token) > 4096 or not re.fullmatch(r'[A-Za-z0-9._~+/=-]+', token):
        raise NotificationError('LINEのチャネルアクセストークンを入力してください。')
    if not re.fullmatch(r'U[0-9a-f]{32}', user_id):
        raise NotificationError('LINEの送信先にはUから始まるユーザーIDを入力してください。')
    return token, user_id


def send_line_notification(token, user_id, content):
    token, user_id = validate_line_settings(token, user_id)
    payload = json.dumps({'to': user_id, 'messages': [{'type': 'text', 'text': content}],
                          'notificationDisabled': False}, ensure_ascii=False).encode('utf-8')
    req = request.Request(ENDPOINT, data=payload, method='POST', headers={
        'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token})
    try:
        with request.build_opener(NoRedirect()).open(req, timeout=10) as response:
            if response.status != 200:
                raise NotificationError('LINEへの送信を確認できませんでした。')
    except error.HTTPError as exc:
        code = exc.code
        exc.close()
        if code in (401, 403):
            raise NotificationError('LINEの認証に失敗しました。トークンと利用権限を確認してください。') from None
        if code == 400:
            raise NotificationError('LINEの送信先IDとチャネルの設定を確認してください。') from None
        if code == 429:
            raise NotificationError('LINEの送信上限または送信制限に達しました。利用状況を確認してください。') from None
        raise NotificationError('LINEへの送信に失敗しました。') from None
    except (error.URLError, OSError, TimeoutError):
        raise NotificationError('LINEに接続できませんでした。通信環境を確認してください。') from None
