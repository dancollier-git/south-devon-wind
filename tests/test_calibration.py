"""Owner calibration, session selection, clock changes and safety separation."""
from datetime import datetime, timedelta, timezone
import copy
import json
from pathlib import Path
import unittest
import forecast as f

RULES = json.loads((Path(__file__).resolve().parents[1] / 'config/wingfoil.json').read_text())
NOW = datetime(2026, 10, 19, 6, tzinfo=timezone.utc)


def wind(speed=20, direction=225, gust=None):
    return {'wind_speed_10m': speed, 'wind_gusts_10m': gust if gust is not None else speed + 5,
            'wind_direction_10m': direction}


MARINE = {'swell_wave_height': 2, 'swell_wave_period': 10, 'swell_wave_direction': 240}


def rated(speed=20, direction=225, location='south_milton', **kwargs):
    return f.assess(wind(speed, direction), MARINE, RULES[location], NOW, location, **kwargs)


def surf(low, high):
    return {'source': 'licensed provider test fixture', 'min_ft': low, 'max_ft': high, 'units': 'ft'}


def snapshots(now=NOW, schedule=None):
    result = []
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    for loc in ('south_milton', 'bigbury'):
        for kind in ('wind', 'marine'):
            rows = []
            for i in range(168):
                t = start + timedelta(hours=i)
                values = (schedule(t, loc) if schedule else wind(20, 225 if loc == 'south_milton' else 90)) if kind == 'wind' else MARINE
                rows.append({'valid_time': t.isoformat(), **values})
            result.append({'location': loc, 'kind': kind, 'status': 'ok', 'retrieved_at': now.isoformat(), 'rows': rows})
    return result


class CalibrationTests(unittest.TestCase):
    def test_owner_examples(self):
        for location, direction, speed, expected in [
            ('south_milton', 225, 14, 'WATCH'), ('south_milton', 225, 17, 'GO CANDIDATE'),
            ('south_milton', 225, 20, 'STRONG GO CANDIDATE'), ('south_milton', 315, 17, 'WATCH'),
            ('south_milton', 315, 20, 'GO CANDIDATE'), ('bigbury', 45, 16, 'WATCH'),
            ('bigbury', 45, 19, 'GO CANDIDATE')]:
            with self.subTest(location=location, direction=direction, speed=speed):
                r = rated(speed, direction, location)
                self.assertEqual(r['wind_suitability'], expected)
                self.assertEqual(r['status'], expected)
                self.assertIn('WAVE HEIGHT UNVERIFIED', r['cautions'])
                self.assertNotEqual(r['status'], 'GO')

    def test_thresholds_and_direction_edges(self):
        for direction, minimum, candidate, strong in ((225, 13, 16, 18), (270, 13, 16, 18),
                                                    (292.5, 14.5, 17.5, 19.5), (315, 16, 19, 21)):
            for speed, expected in ((minimum - .01, 'NO GO'), (minimum, 'WATCH'),
                                    (candidate, 'GO CANDIDATE'), (strong, 'STRONG GO CANDIDATE')):
                self.assertEqual(rated(speed, direction)['wind_suitability'], expected)
        self.assertEqual(rated(20, 330)['status'], 'GO CANDIDATE')
        self.assertEqual(rated(20, 338)['status'], 'NO GO')
        self.assertEqual(rated(20, 180)['status'], 'WATCH')
        self.assertEqual(rated(20, 202.5)['status'], 'WATCH')
        self.assertEqual(rated(20, 90)['status'], 'NO GO')
        self.assertEqual(rated(14.9, 90, 'bigbury')['status'], 'NO GO')
        self.assertEqual(rated(20, 135, 'bigbury')['status'], 'GO CANDIDATE')
        self.assertEqual(rated(20, 136, 'bigbury')['status'], 'NO GO')

    def test_breaking_not_swell_and_launch_gates(self):
        for low, high in ((6, 10), (8, 12)):
            self.assertEqual(rated(breaking=surf(low, high))['status'], 'NO GO')
        self.assertEqual(rated(breaking=surf(6, 8))['status'], 'WATCH')
        self.assertIn('excellent', rated(breaking=surf(4, 6))['wave_riding_potential'])
        self.assertIn('manageable', rated(breaking=surf(2, 4))['wave_riding_potential'])
        self.assertEqual(rated(breaking=surf(2, 4))['status'], 'STRONG GO CANDIDATE')
        self.assertEqual(rated(breaking=surf(2, 4), reef_confirmed=True, launch_confirmed=True)['status'], 'GO')
        r = f.assess(wind(), {**MARINE, 'swell_wave_height': 10}, RULES['south_milton'], NOW, 'south_milton')
        self.assertEqual(r['status'], 'STRONG GO CANDIDATE')
        self.assertIsNone(r['breaking_wave_range'])
        self.assertEqual(rated(hazards=['Dangerous launch confirmed locally'])['status'], 'NO GO')

    def test_strong_wind_review_is_not_veto(self):
        r = f.assess(wind(38, 250, 55), MARINE, RULES['south_milton'], NOW, 'south_milton')
        self.assertEqual(r['wind_suitability'], 'STRONG GO CANDIDATE')
        self.assertEqual(r['status'], 'STRONG GO CANDIDATE')
        self.assertTrue(any('VERY STRONG' in c for c in r['cautions']))

    def test_good_morning_not_hidden_by_afternoon(self):
        def schedule(t, loc):
            return wind(20 if 8 <= t.hour < 11 else 5, 225 if loc == 'south_milton' else 90)
        output = f.assessments(snapshots(schedule=schedule), RULES, NOW)
        day = output['locations']['south_milton']['daily'][0]
        self.assertEqual(day['status'], 'GO CANDIDATE')
        self.assertEqual(day['windows'][0]['start_local'], '2026-10-19T09:00:00+01:00')
        self.assertEqual(day['windows'][0]['end_local'], '2026-10-19T12:00:00+01:00')
        self.assertEqual(len(day['windows']), 1)
        afternoon = [h for h in output['locations']['south_milton']['hourly'] if h['local_time'].startswith('2026-10-19T16')][0]
        self.assertEqual(afternoon['status'], 'NO GO')

    def test_later_days_heads_up_and_only_daylight(self):
        output = f.assessments(snapshots(), RULES, NOW)
        for loc in output['locations'].values():
            self.assertEqual(len(loc['daily']), 7)
            for day in loc['daily'][3:]:
                self.assertEqual(day['status'], 'HEADS-UP')
                self.assertTrue(day['windows'])
                self.assertTrue(all(w['status'] == 'HEADS-UP' for w in day['windows']))
            for day in loc['daily']:
                for w in day['windows']:
                    self.assertTrue(1 <= w['duration_hours'] <= 3)
                    self.assertGreaterEqual(datetime.fromisoformat(w['start_local']).hour, 7)
                    self.assertLessEqual(datetime.fromisoformat(w['end_local']).hour, 18)

    def test_clock_change_repeated_hour_and_local_day(self):
        now = datetime(2026, 10, 24, 0, tzinfo=timezone.utc)
        output = f.assessments(snapshots(now), RULES, now)
        hours = output['locations']['south_milton']['hourly']
        repeated = [h for h in hours if h['local_time'].startswith('2026-10-25T01:00')]
        self.assertEqual([h['local_time'] for h in repeated], ['2026-10-25T01:00:00+01:00', '2026-10-25T01:00:00+00:00'])
        self.assertEqual([h['timezone_abbreviation'] for h in repeated], ['BST', 'GMT'])
        self.assertEqual(len({h['valid_time'] for h in hours}), len(hours))
        self.assertEqual(len([h for h in hours if h['local_date'] == '2026-10-25']), 25)
        self.assertEqual(output['timezone'], 'Europe/London')

    def test_partial_failure_keeps_wind_candidates(self):
        data = [s for s in snapshots() if s['kind'] == 'wind']
        result = f.assessments(data, RULES, NOW)
        self.assertEqual(result['locations']['south_milton']['daily'][0]['status'], 'GO CANDIDATE')
        self.assertTrue(any('marine forecast unavailable' in c for c in result['locations']['south_milton']['hourly'][0]['cautions']))

    def test_valid_configuration_and_no_bias_adjustment(self):
        self.assertEqual(f.validate_rules(copy.deepcopy(RULES)), RULES)
        invalid = copy.deepcopy(RULES)
        invalid['south_milton']['nw_direction_degrees'] = 270
        with self.assertRaises(ValueError):
            f.validate_rules(invalid)
        result = f.assessments(snapshots(), RULES, NOW)
        self.assertEqual(result['locations']['south_milton']['hourly'][0]['sustained_knots'], 20)

    def test_tides_unknown_or_genuine_events_and_staleness(self):
        self.assertEqual(f.tide_context(NOW)['state'], 'unknown')
        tide = {'source': 'licensed local tide test fixture', 'local_station_verified': True,
                'retrieved_at': NOW.isoformat(), 'coverage_start': '2026-10-19T00:00:00Z',
                'coverage_end': '2026-10-26T00:00:00Z', 'events': [
                    {'time': '2026-10-19T03:00:00Z', 'type': 'high'},
                    {'time': '2026-10-19T09:00:00Z', 'type': 'low'},
                    {'time': '2026-10-19T15:00:00Z', 'type': 'high'}]}
        self.assertEqual(f.tide_context(NOW + timedelta(hours=2), tide)['minutes_from_low'], -60)
        result = f.assessments(snapshots(), RULES, NOW, {'south_milton': tide})
        morning = [h for h in result['locations']['south_milton']['hourly'] if h['valid_time'] == '2026-10-19T08:00:00+00:00'][0]
        self.assertTrue(morning['tide']['near_low'])
        self.assertIn('LAUNCH UNVERIFIED', morning['cautions'])
        tide['retrieved_at'] = (NOW - timedelta(days=2)).isoformat()
        result = f.assessments(snapshots(), RULES, NOW, {'south_milton': tide})
        self.assertEqual(result['locations']['south_milton']['hourly'][0]['tide']['state'], 'unknown')
