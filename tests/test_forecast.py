import copy
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import forecast as f
from accuracy import report

NOW = datetime(2026, 10, 18, 12, tzinfo=timezone.utc)


def payload(fields=f.WIND):
    start = NOW.replace(hour=0)
    return {'latitude': 50.2, 'longitude': -3.7, 'utc_offset_seconds': 0,
            'hourly_units': fields.copy(),
            'hourly': {'time': [(start + timedelta(hours=i)).strftime('%Y-%m-%dT%H:%M') for i in range(168)],
                       **{k: [20 if k == 'wind_speed_10m' else 25 if k == 'wind_gusts_10m' else 2 for _ in range(168)] for k in fields}}}


class ForecastTests(unittest.TestCase):
    def test_normalization_and_rejections(self):
        good = payload()
        rows = f.normalize(good, f.WIND, NOW)
        self.assertEqual(len(rows), 168)
        self.assertEqual(rows[0]['valid_time'], '2026-10-18T00:00:00+00:00')
        for mutate in (lambda p: p['hourly_units'].update(wind_speed_10m='km/h'),
                       lambda p: p['hourly']['wind_speed_10m'].__setitem__(0, None),
                       lambda p: p['hourly']['wind_speed_10m'].__setitem__(0, float('nan')),
                       lambda p: p['hourly']['time'].pop(),
                       lambda p: p.update(utc_offset_seconds=3600)):
            bad = copy.deepcopy(good)
            mutate(bad)
            with self.assertRaises(ValueError):
                f.normalize(bad, f.WIND, NOW)

    def test_collection_failure_and_freshness(self):
        with patch.object(f, 'request_json', side_effect=ValueError('bad source')):
            s = f.collect('prawle', 'wind', NOW)
        self.assertEqual(s['status'], 'error')
        self.assertFalse(f.fresh(s, NOW))
        self.assertEqual(s['rows'], [])
        with patch.object(f, 'request_json', return_value=payload()):
            s = f.collect('prawle', 'wind', NOW)
        self.assertIsNone(s['issue_time'])
        self.assertTrue(f.fresh(s, NOW))
        self.assertFalse(f.fresh(s, NOW + timedelta(hours=4)))
        self.assertFalse(f.fresh(s, NOW - timedelta(seconds=1)))

    def test_missing_feeds_still_seven_days(self):
        result = f.assessments([], {'south_milton': None, 'bigbury': None}, NOW)
        for place in result['locations'].values():
            self.assertEqual(len(place['daily']), 7)
            self.assertTrue(all(d['status'] == 'HEADS-UP' for d in place['daily']))

    def test_config_validation(self):
        with self.assertRaises((KeyError, ValueError)):
            f.validate_rules({'south_milton': {'min_wind_knots': -1}, 'bigbury': None})

    def test_accuracy_deduplicates_and_excludes_hindsight(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'docs').mkdir()
            (root / 'archive/forecasts').mkdir(parents=True)
            obs = {'observation_time': NOW.isoformat(), 'wind_speed_knots': 18,
                   'status': 'ok', 'stale': False, 'warnings': []}
            (root / 'docs/history.json').write_text(json.dumps([obs, obs, {**obs, 'stale': True}]))
            snapshots = []
            for hours, speed in ((2, 19), (1, 20), (-1, 99)):
                snapshots.append({'snapshots': [{'location': 'prawle', 'kind': 'wind', 'status': 'ok',
                    'retrieved_at': (NOW - timedelta(hours=hours)).isoformat(),
                    'rows': [{'valid_time': NOW.isoformat(), 'wind_speed_10m': speed}]}]})
            (root / 'archive/forecasts/2026-10-18.jsonl').write_text('\n'.join(map(json.dumps, snapshots)))
            metric = report(root, NOW)['metrics'][0]
            self.assertEqual(metric['samples'], 1)
            self.assertEqual(metric['bias_knots'], 2)
            self.assertEqual(metric['mae_knots'], 2)

    def test_main_preserves_attempts_and_publishes_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'config').mkdir()
            (root / 'config/wingfoil.json').write_text('{"south_milton":null,"bigbury":null}')
            original = f.collect
            def failure(loc, kind, now):
                with patch.object(f, 'request_json', side_effect=ValueError('offline failure')):
                    return original(loc, kind, now)
            with patch.object(f, 'ROOT', root), patch.object(f, 'collect', side_effect=failure):
                self.assertEqual(f.main(), 1)
                self.assertEqual(f.main(), 1)
            lines = next((root / 'archive/forecasts').glob('*.jsonl')).read_text().splitlines()
            self.assertEqual(len(lines), 2)
            public = json.loads((root / 'docs/forecast.json').read_text())
            self.assertEqual(len(public['snapshots']), 5)
            self.assertTrue(all(s['status'] == 'error' for s in public['snapshots']))


class RetryAndHealthTests(unittest.TestCase):
    def test_retry_only_transient_http_errors(self):
        from urllib.error import HTTPError
        for code, attempts in ((403, 1), (429, 3), (503, 3)):
            with patch.object(f, 'urlopen', side_effect=HTTPError('https://example.com', code, 'failure', {}, None)) as get, patch.object(f.time, 'sleep'):
                with self.assertRaises(HTTPError):
                    f.request_json('https://example.com')
                self.assertEqual(get.call_count, attempts)

    def test_read_time_health_rejects_stopped_and_partial_collection(self):
        from forecast_health import check
        sources = [{'location': loc, 'kind': kind, 'status': 'ok', 'retrieved_at': NOW.isoformat()}
                   for loc in f.LOCATIONS for kind in ('wind', 'marine')
                   if loc != 'prawle' or kind == 'wind']
        ratings = {'generated_at': NOW.isoformat(), 'locations': {'south_milton': {}, 'bigbury': {}}}
        self.assertTrue(check({'snapshots': sources}, ratings, NOW))
        self.assertFalse(check({'snapshots': sources}, ratings, NOW + timedelta(hours=4)))
        self.assertFalse(check({'snapshots': sources[:-1]}, ratings, NOW))
