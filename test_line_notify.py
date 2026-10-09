"""LINE tests use mock HTTP only; no real messages or quota consumption."""
import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from line_notify import ENDPOINT, send_line_notification
from discord_notify import NotificationError

TOKEN = 'fake-channel-token'
USER = 'U' + '1' * 32


class LineTests(unittest.TestCase):
    def test_fixed_endpoint_and_text_only_payload(self):
        with patch('line_notify.request.build_opener') as builder:
            builder.return_value.open.return_value.__enter__.return_value.status = 200
            send_line_notification(TOKEN, USER, 'Match found!')
            req = builder.return_value.open.call_args.args[0]
            self.assertEqual(req.full_url, ENDPOINT)
            self.assertEqual(req.get_header('Authorization'), 'Bearer ' + TOKEN)
            self.assertEqual(json.loads(req.data), {'to': USER, 'messages': [
                {'type': 'text', 'text': 'Match found!'}], 'notificationDisabled': False})
            self.assertEqual(builder.return_value.open.call_args.kwargs['timeout'], 10)

    def test_invalid_settings_do_not_send(self):
        with patch('line_notify.request.build_opener') as builder:
            for token, user in (('', USER), ('token\r\nheader', USER), (TOKEN, 'my-line-id'), (TOKEN, 'C' + '1' * 32)):
                with self.assertRaises(NotificationError):
                    send_line_notification(token, user, 'test')
            builder.assert_not_called()

    def test_failures_are_sanitized_and_not_retried(self):
        for code in (400, 401, 403, 429, 500, 302):
            with self.subTest(code=code), patch('line_notify.request.build_opener') as builder:
                builder.return_value.open.side_effect = HTTPError(ENDPOINT, code, TOKEN, {}, io.BytesIO(b'error'))
                with self.assertRaises(NotificationError) as caught:
                    send_line_notification(TOKEN, USER, 'test')
                self.assertNotIn(TOKEN, str(caught.exception))
                self.assertNotIn(USER, str(caught.exception))
                self.assertEqual(builder.return_value.open.call_count, 1)
        with patch('line_notify.request.build_opener') as builder:
            builder.return_value.open.side_effect = URLError(TOKEN)
            with self.assertRaises(NotificationError) as caught:
                send_line_notification(TOKEN, USER, 'test')
            self.assertNotIn(TOKEN, str(caught.exception))


if __name__ == '__main__':
    unittest.main()
