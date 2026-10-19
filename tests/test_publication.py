import copy
import unittest
from unittest.mock import patch
from urllib.error import URLError
from publication_check import verify


class PublicationTests(unittest.TestCase):
    def expected(self):
        return {'forecast.json': {'retrieved_at': '2026-10-19T05:00:00Z', 'snapshots': []},
                'assessments.json': {'generated_at': '2026-10-19T05:00:00Z', 'rules_version': 'owner-2026-10-19'}}

    def test_both_files_checked(self):
        seen = []
        def fetch(url):
            seen.append(url)
            name = url.split('/')[-1].split('?')[0]
            return self.expected()[name]
        verify(self.expected(), 'run-123', fetch, attempts=1)
        self.assertEqual(len(seen), 2)
        self.assertIn('forecast.json?', seen[0])
        self.assertIn('assessments.json?', seen[1])
        self.assertTrue(all('run-123' in url for url in seen))

    def test_stale_publication_retried_then_succeeds(self):
        count = 0
        def fetch(url):
            nonlocal count
            count += 1
            name = url.split('/')[-1].split('?')[0]
            return {} if count == 1 else self.expected()[name]
        with patch('publication_check.time.sleep') as sleep:
            verify(self.expected(), 'run', fetch, attempts=2)
        self.assertEqual(count, 3)
        sleep.assert_called_once_with(5)

    def test_bad_assessment_not_hidden_by_good_forecast(self):
        def fetch(url):
            return self.expected()['forecast.json'] if 'forecast.json?' in url else {'error': 'wrong deployment'}
        with self.assertRaisesRegex(RuntimeError, 'assessments.json'):
            verify(self.expected(), 'run', fetch, attempts=1)

    def test_network_failure_is_bounded(self):
        with patch('publication_check.time.sleep') as sleep:
            with patch('publication_check.fetch_json', side_effect=URLError('offline')) as fetch:
                with self.assertRaises(RuntimeError):
                    verify(self.expected(), 'run', fetch, attempts=2)
                self.assertEqual(fetch.call_count, 2)
                self.assertEqual(sleep.call_count, 1)

    def test_full_content_checked_even_when_timestamp_matches(self):
        def fetch(url):
            name = url.split('/')[-1].split('?')[0]
            value = copy.deepcopy(self.expected()[name])
            if name == 'assessments.json':
                value['rules_version'] = 'old-rules'
            return value
        with self.assertRaises(RuntimeError):
            verify(self.expected(), 'run', fetch, attempts=1)

    def test_inconsistent_local_generation_rejected_before_network(self):
        expected = self.expected()
        expected['assessments.json']['generated_at'] = '2026-10-18T00:00:00Z'
        def fetch(url):
            self.fail('Must reject mixed local generations before fetching')
        with self.assertRaises(ValueError):
            verify(expected, 'run', fetch)
