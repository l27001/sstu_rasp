"""Network-failure regression tests; no production config or database required."""
import ast
import argparse
import io
import logging
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch


class RequestException(Exception):
    pass


class ParseLoggingTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / 'parse.py'
        tree = ast.parse(path.read_text())
        tree.body = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name in ('configure_logging', 'main', 'fetch_page')]
        self.env = {
            'argparse': argparse, 'logging': logging,
            'logger': Mock(spec=logging.Logger),
            'parse_groups': Mock(return_value=[42]), 'parse_rasp': Mock(),
            'parse_weather': Mock(), 'notify_tomorrow': Mock(), 'Pool': MagicMock(),
        }
        exec(compile(tree, str(path), 'exec'), self.env)
        self.configure_logging = self.env['configure_logging']
        self.env['configure_logging'] = Mock()

    def test_logging_levels(self):
        for debug, level in ((False, logging.ERROR), (True, logging.DEBUG)):
            with self.subTest(debug=debug), patch.object(logging, 'basicConfig') as configure:
                self.configure_logging(debug)
                self.assertEqual(configure.call_args.kwargs['level'], level)

    def test_debug_before_and_after_command(self):
        for argv in (['--debug', 'group', '42'], ['group', '42', '--debug']):
            with self.subTest(argv=argv):
                self.assertEqual(self.env['main'](argv), 0)
                self.env['configure_logging'].assert_called_with(True)
                self.env['parse_rasp'].assert_called_with(42)

    def test_existing_commands_work_without_debug(self):
        for command in ('weather', 'groups', 'notify'):
            with self.subTest(command=command):
                self.assertEqual(self.env['main']([command]), 0)
                self.env['configure_logging'].assert_called_with(False)
                function = 'notify_tomorrow' if command == 'notify' else 'parse_' + command
                self.env[function].assert_called_once_with()

    def test_pool_workers_receive_logging_setting(self):
        for debug in (False, True):
            with self.subTest(debug=debug):
                self.assertEqual(self.env['main'](['--debug'] if debug else []), 0)
                self.env['Pool'].assert_called_with(
                    initializer=self.env['configure_logging'], initargs=(debug,))

    def test_fatal_error_returns_failure_and_optional_traceback(self):
        self.env['parse_groups'].side_effect = RuntimeError('database unavailable')
        for debug in (False, True):
            with self.subTest(debug=debug):
                argv = ['groups', '--debug'] if debug else ['groups']
                self.assertEqual(self.env['main'](argv), 1)
                self.env['logger'].error.assert_called_with(
                    'Parser failed: %s', self.env['parse_groups'].side_effect,
                    exc_info=debug)

    def test_fetch_failures_are_silent_unless_debug_enabled(self):
        output = io.StringIO()
        logger = logging.getLogger('parse_test')
        handler = logging.StreamHandler(output)
        self.addCleanup(logger.setLevel, logger.level)
        self.addCleanup(logger.removeHandler, handler)
        logger.addHandler(handler)
        self.env.update({
            'logger': logger, 'headers': {}, 'sleep': Mock(),
            'requests': SimpleNamespace(get=Mock(side_effect=RequestException('timeout')),
                                        RequestException=RequestException),
        })
        logger.setLevel(logging.ERROR)
        self.env['fetch_page']('https://example.test', attempts=1)
        self.assertEqual(output.getvalue(), '')
        logger.setLevel(logging.DEBUG)
        self.env['fetch_page']('https://example.test', attempts=1)
        self.assertIn("Can't fetch https://example.test", output.getvalue())
        self.assertIn('Traceback', output.getvalue())
        self.assertIn('timeout', output.getvalue())

    def test_group_requires_id(self):
        with patch('sys.stderr', new=io.StringIO()), self.assertRaises(SystemExit) as error:
            self.env['main'](['group'])
        self.assertEqual(error.exception.code, 2)
        self.env['parse_rasp'].assert_not_called()


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
        self.assertEqual(self.env['logger'].debug.call_count, 5)

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
