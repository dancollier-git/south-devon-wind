import unittest
from record import classify

class AlertTests(unittest.TestCase):
    def reading(self, **changes):
        value = {'stale': False, 'warnings': [], 'wind_speed_knots': 20, 'gust_knots': 30}
        value.update(changes)
        return classify(value)

    def test_threshold(self):
        self.assertTrue(self.reading()['wind_alert'])
        self.assertFalse(self.reading(wind_speed_knots=19.9)['wind_alert'])
        self.assertFalse(self.reading(wind_speed_knots=10, gust_knots=25)['wind_alert'])

    def test_unusable_reading_cannot_alert(self):
        for changes in [{'stale': True}, {'stale': None}, {'warnings': ['Sensor contact lost']},
                        {'error': 'HTTP 403'}, {'wind_speed_knots': None}]:
            with self.subTest(changes=changes):
                self.assertFalse(self.reading(**changes)['wind_alert'])
                self.assertEqual(self.reading(**changes)['status'], 'warning')

class RecordingTests(unittest.TestCase):
    def test_publish_success_and_failure_without_network(self):
        import contextlib
        import io
        import json
        from pathlib import Path
        import subprocess
        import tempfile
        from unittest.mock import patch
        import record
        fresh = {'stale': False, 'warnings': [], 'wind_speed_knots': 21,
                 'observation_time': '2026-10-16T20:02:20+00:00'}
        failed = {'error': 'HTTP Error 403: Forbidden', 'stale': None,
                  'warnings': ['No usable reading; freshness unknown']}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(record, 'ROOT', root), contextlib.redirect_stdout(io.StringIO()):
                for payload, code in [(fresh, 0), (failed, 1)]:
                    response = subprocess.CompletedProcess([], code, json.dumps(payload), '')
                    with patch.object(record.subprocess, 'run', return_value=response) as run:
                        self.assertEqual(record.main(), code)
                        run.assert_called_once()
            latest = json.loads((root/'docs/latest.json').read_text())
            history = json.loads((root/'docs/history.json').read_text())
            self.assertEqual(len(history), 2)
            self.assertTrue(history[0]['wind_alert'])
            self.assertEqual(latest['error'], failed['error'])
            self.assertFalse(latest['wind_alert'])
