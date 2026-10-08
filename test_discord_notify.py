"""Offline tests: no requests are sent to Discord."""
import json
import io
import unittest
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError, URLError
from discord_notify import validate_webhook, send_notification, NotificationError, NoRedirect

URL = 'https://discord.com/api/webhooks/123/test_token'


class DiscordTests(unittest.TestCase):
    def test_rejects_other_destinations_without_network(self):
        with patch('discord_notify.request.build_opener') as opener:
            for url in ('', 'http://discord.com/api/webhooks/123/x',
                        'https://discord.com.evil.test/api/webhooks/123/x',
                        'https://discord.com@evil.test/api/webhooks/123/x',
                        URL + '?redirect=elsewhere', URL + '/messages/123'):
                with self.subTest(url=url), self.assertRaises(NotificationError):
                    send_notification(url, 'test')
            opener.assert_not_called()

    def test_text_only_payload_and_confirmed_delivery(self):
        with patch('discord_notify.request.build_opener') as builder:
            builder.return_value.open.return_value.__enter__.return_value.status = 200
            send_notification(URL, 'Match found!\n2026-10-08T12:00:00+09:00')
            req = builder.return_value.open.call_args.args[0]
            self.assertEqual(req.full_url, URL + '?wait=true')
            self.assertEqual(req.method, 'POST')
            payload = json.loads(req.data)
            self.assertEqual(set(payload), {'content', 'allowed_mentions'})
            self.assertEqual(payload['allowed_mentions'], {'parse': []})
            self.assertEqual(builder.return_value.open.call_args.kwargs['timeout'], 10)

    def test_errors_do_not_expose_url_or_token_and_do_not_retry(self):
        for code in (401, 403, 404, 429, 500, 302):
            with self.subTest(code=code), patch('discord_notify.request.build_opener') as builder:
                builder.return_value.open.side_effect = HTTPError(URL, code, URL, {}, io.BytesIO(b'error'))
                with self.assertRaises(NotificationError) as caught:
                    send_notification(URL, 'test')
                self.assertNotIn('test_token', str(caught.exception))
                self.assertEqual(builder.return_value.open.call_count, 1)
        with patch('discord_notify.request.build_opener') as builder:
            builder.return_value.open.side_effect = URLError(URL)
            with self.assertRaises(NotificationError) as caught:
                send_notification(URL, 'test')
            self.assertNotIn('test_token', str(caught.exception))

    def test_redirects_are_not_followed(self):
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, '', {}, 'https://example.com'))


if __name__ == '__main__':
    unittest.main()
