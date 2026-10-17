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
