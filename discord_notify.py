"""Send text only to Discord. Never include URLs or server error bodies in errors."""
import json
import re
import sys
from pathlib import Path
from urllib import request, error
from urllib.parse import urlsplit


class NotificationError(Exception):
    pass


def read_webhook_file(path=None):
    if path is None:
        folder = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent
        path = folder / 'webhook.txt'
    try:
        with Path(path).open('r', encoding='utf-8-sig') as stream:
            content = stream.read(4097)
    except FileNotFoundError:
        return None
    except (OSError, UnicodeError):
        raise NotificationError('webhook.txtを読み込めません。UTF-8で保存してください。') from None
    lines = content.strip().splitlines()
    if len(content) > 4096 or len(lines) != 1:
        raise NotificationError('webhook.txtにはWebhook URLだけを1行で記入してください。')
    url = lines[0].strip()
    validate_webhook(url)
    return url


def validate_webhook(url):
    try:
        parsed = urlsplit(url.strip())
        valid = (parsed.scheme == 'https' and parsed.netloc in ('discord.com', 'discordapp.com')
                 and not parsed.query and not parsed.fragment
                 and re.fullmatch(r'/api(?:/v\d+)?/webhooks/[0-9]+/[A-Za-z0-9_-]+', parsed.path))
    except ValueError:
        valid = False
    if not valid:
        raise NotificationError('DiscordのWebhook URLを入力してください。')
    return 'https://discord.com' + parsed.path + '?wait=true'


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate_user_id(user_id):
    user_id = user_id.strip()
    if user_id and (not re.fullmatch(r'[0-9]{17,20}', user_id) or int(user_id) >= 2**64):
        raise NotificationError('メンション先には数字のユーザーIDを入力してください（空欄ならメンションなし）。')
    return user_id


def send_notification(url, content, user_id=''):
    endpoint = validate_webhook(url)
    user_id = validate_user_id(user_id)
    mentions = {'parse': []}
    if user_id:
        content = f'<@{user_id}>\n' + content
        mentions['users'] = [user_id]
    payload = json.dumps({'content': content, 'allowed_mentions': mentions},
                         ensure_ascii=False).encode('utf-8')
    req = request.Request(endpoint, data=payload, method='POST', headers={
        'Content-Type': 'application/json', 'User-Agent': 'OverwatchStadiumNotifier/0.1'})
    try:
        with request.build_opener(NoRedirect()).open(req, timeout=10) as response:
            if response.status != 200:
                raise NotificationError('Discordへの送信を確認できませんでした。')
    except error.HTTPError as exc:
        code = exc.code
        exc.close()
        if code == 429:
            raise NotificationError('Discordの送信制限です。少し待ってから再送してください。') from None
        if code in (401, 403, 404):
            raise NotificationError('Webhookが無効、または送信権限がありません。URLを確認してください。') from None
        raise NotificationError('Discordへの送信に失敗しました。') from None
    except (error.URLError, OSError, TimeoutError):
        raise NotificationError('Discordに接続できませんでした。通信環境を確認してください。') from None
