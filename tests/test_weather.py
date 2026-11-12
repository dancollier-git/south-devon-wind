import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from weather import normalize

class WeatherTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(Path(__file__).with_name('recorded-feed.json').read_text())
        self.now = datetime(2026, 10, 16, 20, 3, 20, tzinfo=timezone.utc)

    def test_offset_and_units(self):
        result = normalize(self.data, now=self.now)
        self.assertEqual(result['observation_time'], '2026-10-16T20:02:20+00:00')
        self.assertEqual(result['age_seconds'], 60)
        self.assertEqual(result['wind_speed_knots'], 13.9)
        self.assertFalse(result['stale'])

    def test_stale_and_missing_timestamp(self):
        self.assertTrue(normalize(self.data, now=self.now+timedelta(hours=1))['stale'])
        self.data['obstime'] = 'invalid'
        result = normalize(self.data, now=self.now)
        self.assertIsNone(result['stale'])
        self.assertTrue(result['warnings'])

    def test_invalid_sensor_and_units(self):
        self.data['wspeed'] = 'NaN'
        self.data['SensorContactLost'] = '1'
        result = normalize(self.data, now=self.now)
        self.assertIsNone(result['wind_speed_knots'])
        self.assertEqual(len(result['warnings']), 2)
        self.data['windunit'] = 'unknown'
        with self.assertRaises(ValueError):
            normalize(self.data, now=self.now)

    def test_pressure_fields(self):
        result = normalize(self.data, now=self.now)
        self.assertEqual(result['pressure_hpa'], 1030.4)
        self.assertEqual(result['pressure_today_low_hpa'], 1017.8)
        self.assertEqual(result['pressure_today_high_hpa'], 1030.4)
        self.assertEqual(result['pressure_trend'], 'Rising Slowly')
        self.assertEqual(result['pressure_warnings'], [])

    def test_optional_pressure_does_not_affect_wind(self):
        from record import classify
        for value in [None, 'NaN', 'inf', 'bad', 0, 1200]:
            with self.subTest(value=value):
                self.data['press'] = value
                self.data['wspeed'] = '25'
                result = classify(normalize(self.data, now=self.now))
                self.assertIsNone(result['pressure_hpa'])
                self.assertTrue(result['pressure_warnings'])
                self.assertEqual(result['warnings'], [])
                self.assertTrue(result['wind_alert'])
        for key in ('press', 'pressTL', 'pressTH', 'presstrend'):
            self.data.pop(key, None)
        result = normalize(self.data, now=self.now)
        self.assertIsNone(result['pressure_hpa'])
        self.assertIsNone(result['pressure_trend'])
        self.assertEqual(len(result['pressure_warnings']), 3)

    def test_mph_conversion(self):
        self.data['windunit'] = 'mph'
        self.data['wspeed'] = '11.50779448'
        self.assertEqual(normalize(self.data, now=self.now)['wind_speed_knots'], 10)

if __name__ == '__main__':
    unittest.main()
