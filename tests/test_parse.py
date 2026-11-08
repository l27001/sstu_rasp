"""Network-failure regression tests; no production config or database required."""
import ast
import logging
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


class RequestException(Exception):
    pass


class ParseNetworkTests(unittest.TestCase):
    def setUp(self):
        # Load only the tested functions, avoiding config and optional dependencies.
        path = Path(__file__).resolve().parents[1] / 'parse.py'
        tree = ast.parse(path.read_text())
        tree.body = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name in ('fetch_page', 'parse_groups', 'parse_rasp')]
        self.requests = SimpleNamespace(
            get=Mock(), RequestException=RequestException, HTTPError=RequestException)
        self.mysql = Mock()
        self.mysql.query.return_value = {'sstu_id': 123}
        self.env = {
            'requests': self.requests, 'headers': {}, 'sleep': Mock(),
            'logger': Mock(spec=logging.Logger), 'BeautifulSoup': Mock(),
            'methods': SimpleNamespace(Mysql=Mock(return_value=self.mysql)),
        }
        exec(compile(tree, str(path), 'exec'), self.env)

    def test_success_is_not_retried(self):
        response = Mock(status_code=200)
        self.requests.get.return_value = response
        self.assertIs(self.env['fetch_page']('https://example.test'), response)
        self.requests.get.assert_called_once_with(
            'https://example.test', headers={}, timeout=5)
        self.env['sleep'].assert_not_called()

    def test_network_failure_exhausts_retries(self):
        self.requests.get.side_effect = RequestException('timeout')
        self.assertIsNone(self.env['fetch_page']('https://example.test'))
        self.assertEqual(self.requests.get.call_count, 5)
        self.assertEqual(self.env['sleep'].call_count, 4)
        self.env['sleep'].assert_called_with(5)
        self.assertEqual(self.env['logger'].warning.call_count, 5)

    def test_http_failure_does_not_return_error_page(self):
        self.requests.get.return_value = Mock(status_code=503)
        self.assertIsNone(self.env['fetch_page']('https://example.test'))
        self.assertEqual(self.requests.get.call_count, 5)

    def test_custom_retry_count(self):
        self.requests.get.side_effect = RequestException('timeout')
        self.assertIsNone(self.env['fetch_page']('https://example.test', attempts=2))
        self.assertEqual(self.requests.get.call_count, 2)
        self.env['sleep'].assert_called_once_with(5)

    def test_success_after_http_and_network_failures(self):
        response = Mock(status_code=200)
        self.requests.get.side_effect = [
            Mock(status_code=503), RequestException('timeout'), response]
        self.assertIs(self.env['fetch_page']('https://example.test'), response)

    def test_unavailable_group_preserves_schedule_and_closes_connection(self):
        self.requests.get.side_effect = RequestException('timeout')
        self.env['parse_rasp'](42)
        self.mysql.query.assert_called_once_with(
            'SELECT sstu_id FROM groups WHERE id=%s', (42,))
        self.mysql.commit.assert_not_called()
        self.mysql.close.assert_called_once_with()
        self.env['BeautifulSoup'].assert_not_called()

    def test_query_failure_closes_connection(self):
        self.mysql.query.side_effect = RuntimeError('database unavailable')
        with self.assertRaisesRegex(RuntimeError, 'database unavailable'):
            self.env['parse_rasp'](42)
        self.mysql.close.assert_called_once_with()

    def test_unavailable_group_list_stops_before_database_access(self):
        self.requests.get.return_value = Mock(status_code=503)
        with self.assertRaisesRegex(RuntimeError, "Can't parse group list"):
            self.env['parse_groups']()
        self.env['methods'].Mysql.assert_not_called()
        self.env['BeautifulSoup'].assert_not_called()


if __name__ == '__main__':
    unittest.main()
