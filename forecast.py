"""Documented non-commercial Open-Meteo APIs; no XCWeather/Surfline extraction."""
from datetime import datetime, timezone, timedelta
import json
import math
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
LOCATIONS = {'south_milton': (50.263, -3.862), 'bigbury': (50.279, -3.884),
             'prawle': (50.202, -3.721)}
WIND = {'wind_speed_10m': 'kn', 'wind_gusts_10m': 'kn', 'wind_direction_10m': '°'}
MARINE = {'wave_height': 'm', 'swell_wave_height': 'm',
          'swell_wave_period': 's', 'swell_wave_direction': '°'}
MAX_AGE = 3 * 3600


def utc(value):
    stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if stamp.tzinfo is None:
        raise ValueError('Timestamp lacks timezone')
    return stamp.astimezone(timezone.utc)


def fresh(snapshot, now):
    try:
        age = (now - utc(snapshot['retrieved_at'])).total_seconds()
        return snapshot['status'] == 'ok' and 0 <= age <= MAX_AGE
    except (KeyError, TypeError, ValueError):
        return False


def request_json(url):
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={'User-Agent': 'SouthDevonWindArchive/1.0',
                                               'Accept': 'application/json'}), timeout=20) as response:
                raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ValueError('Response exceeds size limit')
            return json.loads(raw)
        except HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise
        except (URLError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep(2 ** attempt)


def normalize(data, fields, now):
    if data.get('utc_offset_seconds') != 0:
        raise ValueError('Expected UTC response')
    hourly = data['hourly']
    times = hourly['time']
    if len(times) != 168 or len(set(times)) != len(times):
        raise ValueError('Expected seven complete days of unique hourly times')
    stamps = [utc(t + '+00:00') for t in times]
    if any(b - a != timedelta(hours=1) for a, b in zip(stamps, stamps[1:])):
        raise ValueError('Forecast hours are not consecutive')
    if stamps[0].date() != now.date():
        raise ValueError('Forecast starts on wrong UTC day')
    for field, unit in fields.items():
        if data['hourly_units'].get(field) != unit:
            raise ValueError(f'Unexpected units for {field}')
        values = hourly[field]
        if len(values) != len(times):
            raise ValueError(f'Unaligned {field}')
        for value in values:
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or value < 0
                    or ('direction' in field and value > 360)):
                raise ValueError(f'Missing or invalid {field}')
    return [{'valid_time': stamp.isoformat(), **{f: hourly[f][i] for f in fields}}
            for i, stamp in enumerate(stamps)]


def collect(location, kind, now):
    lat, lon = LOCATIONS[location]
    fields = WIND if kind == 'wind' else MARINE
    endpoint = ('https://api.open-meteo.com/v1/forecast' if kind == 'wind'
                else 'https://marine-api.open-meteo.com/v1/marine')
    params = {'latitude': lat, 'longitude': lon, 'hourly': ','.join(fields),
              'forecast_days': 7, 'timezone': 'GMT'}
    if kind == 'wind':
        params['wind_speed_unit'] = 'kn'
    else:
        params['cell_selection'] = 'sea'
    result = {'location': location, 'coordinates_requested': [lat, lon],
              'source': 'open-meteo', 'kind': kind, 'endpoint': endpoint,
              'model_selection': 'best_match', 'units': fields,
              'retrieved_at': now.isoformat(), 'issue_time': None,
              'issue_time_basis': 'unavailable', 'stale_after_seconds': MAX_AGE,
              'status': 'error', 'rows': []}
    try:
        data = request_json(endpoint + '?' + urlencode(params))
        result['raw'] = data
        result['rows'] = normalize(data, fields, now)
        result['coordinates_returned'] = [data['latitude'], data['longitude']]
        result['status'] = 'ok'
    except Exception as exc:
        result['error'] = f'{type(exc).__name__}: {exc}'
    return result


def assess(wind, marine, rules, now, location, breaking=None, reef_confirmed=False):
    """Breaking input is reserved for a future licensed adapter, never swell."""
    reasons = []
    if breaking is not None:
        low, high = breaking
        if (not all(isinstance(v, (int, float)) and math.isfinite(v) for v in breaking)
                or not 0 <= low <= high):
            return {'status': 'HEADS-UP', 'reasons': ['Invalid breaking-wave range']}
        if high >= 6:
            return {'status': 'NO GO', 'reasons': [f'Breaking waves {low:g}–{high:g} ft: upper bound >=6 ft']}
    if not wind or not marine:
        return {'status': 'HEADS-UP', 'reasons': ['Wind or marine forecast missing for this hour']}
    if not rules:
        reasons.append('Owner wind/direction thresholds not configured')
    else:
        speed, gust, direction = (wind[k] for k in WIND)
        if speed > rules['max_wind_knots'] or gust > rules['max_gust_knots']:
            return {'status': 'NO GO', 'reasons': ['Configured wind or gust ceiling exceeded']}
        allowed = any((a <= direction % 360 <= b if a <= b else direction % 360 >= a or direction % 360 <= b)
                      for a, b in rules['direction_sectors'])
        if not allowed:
            return {'status': 'NO GO', 'reasons': ['Wind direction outside configured sectors']}
        if speed < rules['min_wind_knots']:
            reasons.append('Wind below configured minimum')
    if breaking is None:
        reasons.append('Breaking-wave range unavailable; offshore swell is not surf height')
    if location == 'south_milton' and not reef_confirmed:
        reasons.append('Low-tide reef shelter unconfirmed; check local tide and exposed reef')
    if marine['swell_wave_height'] > 0:
        reasons.append('Offshore swell energy present; wave-riding potential needs local breaking-wave check')
    blocked = not rules or breaking is None or (location == 'south_milton' and not reef_confirmed)
    status = 'HEADS-UP' if blocked else ('WATCH' if wind['wind_speed_10m'] < rules['min_wind_knots'] else 'GO')
    return {'status': status, 'reasons': reasons or ['Configured checks passed']}


def validate_rules(config):
    for name in ('south_milton', 'bigbury'):
        r = config[name]
        if r is None:
            continue
        for key in ('min_wind_knots', 'max_wind_knots', 'max_gust_knots'):
            v = r[key]
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
                raise ValueError(f'Invalid {name} {key}')
        if not r['min_wind_knots'] <= r['max_wind_knots'] <= r['max_gust_knots']:
            raise ValueError('Require minimum <= maximum wind <= maximum gust')
        if not r['direction_sectors'] or any(len(s) != 2 or any(
                isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
                or not 0 <= v <= 360 for v in s) for s in r['direction_sectors']):
            raise ValueError('Invalid direction sectors')
    return config


def assessments(snapshots, config, now):
    output = {}
    rank = {'GO': 0, 'WATCH': 1, 'HEADS-UP': 2, 'NO GO': 3}
    for location in ('south_milton', 'bigbury'):
        indexed = {}
        for s in snapshots:
            if s['location'] == location and fresh(s, now):
                indexed[s['kind']] = {r['valid_time']: r for r in s['rows']}
        hours = []
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        for n in range(168):
            valid = start + timedelta(hours=n)
            if valid < now.replace(minute=0, second=0, microsecond=0):
                continue
            t = valid.isoformat()
            rating = assess(indexed.get('wind', {}).get(t), indexed.get('marine', {}).get(t),
                            config[location], now, location)
            hours.append({'valid_time': t, **rating})
        daily = []
        for n in range(7):
            date = (start + timedelta(days=n)).date().isoformat()
            group = [h for h in hours if h['valid_time'].startswith(date)]
            worst = max(group, key=lambda h: rank[h['status']])
            daily.append({'date': date, 'status': worst['status'],
                          'reasons': sorted({r for h in group for r in h['reasons']}),
                          'summary_basis': 'most restrictive remaining UTC hour'})
        output[location] = {'daily': daily, 'hourly': hours}
    return {'generated_at': now.isoformat(), 'stale_after_seconds': MAX_AGE,
            'timezone': 'UTC', 'locations': output}


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, separators=(',', ':'), allow_nan=False) + '\n')
    temp.replace(path)


def main():
    now = datetime.now(timezone.utc)
    snapshots = [collect(loc, kind, now) for loc in LOCATIONS
                 for kind in ('wind', 'marine') if loc != 'prawle' or kind == 'wind']
    bundle = {'schema_version': 1, 'retrieved_at': now.isoformat(),
              'attribution': 'Weather data by Open-Meteo and model providers; CC BY 4.0. Normalized and assessed by South Devon Wind.',
              'licence': 'https://creativecommons.org/licenses/by/4.0/',
              'source_documentation': ['https://open-meteo.com/en/docs', 'https://open-meteo.com/en/docs/marine-weather-api'],
              'snapshots': snapshots}
    archive = ROOT / 'archive' / 'forecasts' / f'{now:%Y-%m-%d}.jsonl'
    archive.parent.mkdir(parents=True, exist_ok=True)
    with archive.open('a') as stream:
        stream.write(json.dumps(bundle, separators=(',', ':'), allow_nan=False) + '\n')
    public = {**bundle, 'snapshots': [{k: v for k, v in s.items() if k != 'raw'} for s in snapshots]}
    write_json(ROOT / 'docs/forecast.json', public)
    try:
        config = validate_rules(json.loads((ROOT / 'config/wingfoil.json').read_text()))
        ratings = assessments(snapshots, config, now)
    except Exception as exc:
        ratings = {'generated_at': now.isoformat(), 'status': 'error', 'error': str(exc), 'locations': {}}
    write_json(ROOT / 'docs/assessments.json', ratings)
    from accuracy import report
    write_json(ROOT / 'docs/accuracy.json', report(ROOT, now))
    failures = [s for s in snapshots if not fresh(s, datetime.now(timezone.utc))]
    print(json.dumps({'source_failures': [{k: s[k] for k in ('location', 'kind', 'error') if k in s}
                                         for s in failures], 'assessment_error': ratings.get('error')}))
    return 1 if failures or ratings.get('error') else 0


if __name__ == '__main__':
    raise SystemExit(main())
