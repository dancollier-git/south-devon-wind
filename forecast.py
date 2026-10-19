"""Documented non-commercial Open-Meteo APIs; no XCWeather/Surfline extraction."""
from datetime import datetime, timezone, timedelta
import json
import math
from pathlib import Path
import time
from zoneinfo import ZoneInfo
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


UK = ZoneInfo('Europe/London')
WIND_RANK = {'NO GO': 0, 'WATCH': 1, 'GO CANDIDATE': 2, 'STRONG GO CANDIDATE': 3}


def wind_suitability(wind, rules, location):
    if wind is None or not rules:
        return 'UNKNOWN', ['Wind forecast or owner calibration unavailable']
    speed = wind['wind_speed_10m']
    direction = wind['wind_direction_10m'] % 360
    if location == 'bigbury':
        if not rules['direction_degrees'][0] <= direction <= rules['direction_degrees'][1]:
            return 'NO GO', ['Direction outside Bigbury NE–SE (45°–135°)']
        minimum, candidate = rules['minimum_knots'], rules['candidate_knots']
        strong = None
        reasons = ['Bigbury NE–SE wind']
    else:
        preferred_start, preferred_end = rules['preferred_direction_degrees']
        nw = rules['nw_direction_degrees']
        if preferred_start <= direction <= rules['nw_sector_end_degrees']:
            # Smoothly increase all speed boundaries from W to NW; no WNW cliff.
            penalty = rules['nw_extra_knots'] * min(1, max(0, direction - preferred_end) / (nw - preferred_end))
            minimum = rules['minimum_knots'] + penalty
            candidate = rules['candidate_knots'] + penalty
            strong = rules['strong_candidate_knots'] + penalty
            reasons = [f'South Milton SW–W/NW calibration; WNW adjustment +{penalty:.1f} kt']
        elif rules['southerly_direction_degrees'][0] <= direction < preferred_start:
            if speed < rules['minimum_knots']:
                return 'NO GO', ['Southerly wind below minimum; direction also less favourable']
            return 'WATCH', ['S/SSW possible but lower confidence; local experience required']
        else:
            return 'NO GO', ['Direction outside owner-supported South Milton sectors']
    if speed < minimum:
        return 'NO GO', reasons + [f'Insufficient sustained wind: below {minimum:g} kt']
    if speed < candidate:
        return 'WATCH', reasons + [f'Marginal wind: candidate threshold {candidate:g} kt']
    if strong is not None and speed >= strong:
        return 'STRONG GO CANDIDATE', reasons + ['Strong wind potentially excellent for wave riding, subject to sea and launch checks']
    return 'GO CANDIDATE', reasons + ['Suitable sustained wind, subject to sea and launch checks']


def tide_context(valid, prediction=None):
    """Only accept fresh, attributed local predictions; no offshore tide inference.

    Optional internal input for a future permitted tide adapter. ±90 minutes is
    a session-ranking heuristic, never a claim that the reef is safely exposed.
    """
    unknown = {'state': 'unknown', 'source': None, 'nearest_low_local': None,
               'minutes_from_low': None, 'near_low': None,
               'reason': 'No permitted local tide prediction feed configured (ADMIRALTY requires subscription/key)'}
    if not prediction:
        return unknown
    try:
        if (not prediction['source'] or not prediction['local_station_verified']
                or not utc(prediction['coverage_start']) <= valid <= utc(prediction['coverage_end'])):
            return unknown
        events = sorted((utc(e['time']), e['type']) for e in prediction['events'])
        before = [e for e in events if e[0] <= valid]
        after = [e for e in events if e[0] > valid]
        lows = [e[0] for e in events if e[1] == 'low']
        if (not before or not after or not lows or any(kind not in ('high', 'low') for _, kind in events)
                or any(a[1] == b[1] for a, b in zip(events, events[1:]))):
            return unknown
        low = min(lows, key=lambda t: abs((valid - t).total_seconds()))
        minutes = round((valid - low).total_seconds() / 60)
        return {'state': 'low' if abs(minutes) <= 30 else ('rising' if before[-1][1] == 'low' else 'falling'),
                'source': prediction['source'], 'nearest_low_local': low.astimezone(UK).isoformat(),
                'minutes_from_low': minutes, 'near_low': abs(minutes) <= 90,
                'reason': 'Predicted tide only; verify actual reef and launch on site'}
    except (KeyError, ValueError, TypeError):
        return unknown


def assess(wind, marine, rules, now, location, breaking=None, reef_confirmed=False,
           tide=None, launch_confirmed=False, hazards=None):
    """Wind candidates remain visible without surf. Only explicit checks confirm GO."""
    suitability, reasons = wind_suitability(wind, rules, location)
    cautions = []
    tide = tide or tide_context(now)
    if tide['state'] == 'unknown':
        cautions.append('TIDE UNKNOWN')
    if location == 'south_milton':
        launch = ('Low-tide reef shelter confirmed locally; verify launch remains safe' if reef_confirmed
                  else 'Launch unverified; low-tide reef can shelter launch but exposure must be checked')
        if tide.get('near_low'):
            launch += '; predicted near low tide is favourable, not proof of safe exposure'
        cautions.append('Check exposed reef, water depth and launch before entering')
    else:
        launch = 'Any tide can work; launch conditions unverified' if not launch_confirmed else 'Launch checked locally'
    if not launch_confirmed:
        cautions.append('LAUNCH UNVERIFIED')
    wave = 'Unknown breaking-wave conditions'
    wave_hazard = False
    wave_caution = False
    if breaking is None:
        cautions.append('WAVE HEIGHT UNVERIFIED')
        if marine and marine.get('swell_wave_height', 0) > 0:
            wave = 'Offshore swell energy present; rideable breaking waves unverified'
    else:
        # This argument must come from a permitted breaking-wave provider, never swell.
        low, high = breaking['min_ft'], breaking['max_ft']
        if (not breaking.get('source') or any(isinstance(v, bool) or not isinstance(v, (int, float))
                or not math.isfinite(v) for v in (low, high)) or not 0 <= low <= high):
            raise ValueError('Invalid attributed breaking-wave range')
        if high >= 10:
            wave_hazard = True
            wave = 'Hazardous breaking-wave range'
            reasons.append(f'Breaking waves {low:g}–{high:g} ft: definite NO GO')
        elif high > 6:
            wave_caution = True
            wave = 'CAUTION: large breaking waves; assess carefully'
            cautions.append(f'CAUTION: breaking waves {low:g}–{high:g} ft')
        elif high > 4:
            wave = 'Potentially excellent wave riding (4–6 ft band), subject to launch/safety checks'
        else:
            wave = 'Generally manageable breaking-wave band; local checks still needed'
    review = False
    if wind and rules:
        speed, gust = wind['wind_speed_10m'], wind['wind_gusts_10m']
        flags = rules['review_flags']
        if (speed >= flags['sustained_knots'] or gust >= flags['gust_knots']
                or gust - speed >= flags['gust_spread_knots']):
            review = True
            cautions.append('VERY STRONG / GUSTY: review control, equipment and launch; no fixed wind veto')
    overall = suitability if suitability != 'UNKNOWN' else 'HEADS-UP'
    if wave_hazard or hazards:
        overall = 'NO GO'
        reasons.extend(hazards or [])
    elif wave_caution and overall in ('GO CANDIDATE', 'STRONG GO CANDIDATE'):
        overall = 'WATCH'
    elif (overall in ('GO CANDIDATE', 'STRONG GO CANDIDATE') and breaking is not None
          and launch_confirmed and not review and (location != 'south_milton' or reef_confirmed)):
        overall = 'GO'
    return {'status': overall, 'overall_recommendation': overall,
            'wind_suitability': suitability, 'launch_suitability': launch,
            'wave_riding_potential': wave, 'breaking_wave_range': breaking,
            'tide': tide, 'confidence': 'low' if cautions or overall == 'HEADS-UP' else 'moderate',
            'cautions': cautions, 'reasons': reasons}


def validate_rules(config):
    for location in ('south_milton', 'bigbury'):
        rules = config[location]
        if rules is None:
            continue
        keys = ['minimum_knots', 'candidate_knots']
        if location == 'south_milton':
            keys += ['strong_candidate_knots', 'nw_extra_knots', 'nw_direction_degrees', 'nw_sector_end_degrees']
        values = [rules[k] for k in keys] + list(rules['review_flags'].values())
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 for v in values):
            raise ValueError('Calibration values must be finite nonnegative numbers')
        if rules['minimum_knots'] > rules['candidate_knots']:
            raise ValueError('Minimum exceeds candidate wind')
        sectors = [rules[k] for k in ('direction_degrees', 'preferred_direction_degrees', 'southerly_direction_degrees') if k in rules]
        if any(len(s) != 2 or not all(isinstance(v, (int, float)) and not isinstance(v, bool)
                    and math.isfinite(v) and 0 <= v <= 360 for v in s) or s[0] > s[1] for s in sectors):
            raise ValueError('Invalid direction sectors')
        if location == 'south_milton' and not (rules['candidate_knots'] <= rules['strong_candidate_knots']
                and rules['southerly_direction_degrees'][1] == rules['preferred_direction_degrees'][0]
                and rules['preferred_direction_degrees'][1] < rules['nw_direction_degrees'] <= rules['nw_sector_end_degrees'] <= 360):
            raise ValueError('Invalid South Milton transition')
    return config


def solar_elevation(stamp, latitude, longitude):
    """NOAA fractional-year approximation, degrees; adequate for hourly planning."""
    stamp = stamp.astimezone(timezone.utc)
    hour = stamp.hour + stamp.minute / 60 + stamp.second / 3600
    gamma = 2 * math.pi / 365 * (stamp.timetuple().tm_yday - 1 + (hour - 12) / 24)
    eq = 229.18 * (0.000075 + 0.001868 * math.cos(gamma) - 0.032077 * math.sin(gamma)
                   - 0.014615 * math.cos(2 * gamma) - 0.040849 * math.sin(2 * gamma))
    decl = (0.006918 - 0.399912 * math.cos(gamma) + 0.070257 * math.sin(gamma)
            - 0.006758 * math.cos(2 * gamma) + 0.000907 * math.sin(2 * gamma)
            - 0.002697 * math.cos(3 * gamma) + 0.00148 * math.sin(3 * gamma))
    angle = math.radians((hour * 60 + eq + 4 * longitude) / 4 - 180)
    lat = math.radians(latitude)
    return math.degrees(math.asin(math.sin(lat) * math.sin(decl) + math.cos(lat) * math.cos(decl) * math.cos(angle)))


def session_windows(hours, location):
    """Choose up to two non-overlapping 1–3 hour daylight windows, best first."""
    candidates = []
    for i, hour in enumerate(hours):
        for duration in (1, 2, 3):
            group = hours[i:i + duration]
            if len(group) != duration or any(
                    not h['daylight_session_hour']
                    or h['wind_suitability'] not in ('WATCH', 'GO CANDIDATE', 'STRONG GO CANDIDATE')
                    or h.get('provisional_recommendation', h['overall_recommendation']) == 'NO GO'
                    for h in group):
                continue
            if any(utc(b['valid_time']) - utc(a['valid_time']) != timedelta(hours=1) for a, b in zip(group, group[1:])):
                continue
            start = utc(group[0]['valid_time'])
            end = utc(group[-1]['valid_time']) + timedelta(hours=1)
            rank = min(WIND_RANK[h['wind_suitability']] for h in group)
            if any(h.get('provisional_recommendation', h['overall_recommendation']) == 'WATCH' for h in group):
                rank = min(rank, 1)
            morning = start.astimezone(UK).hour < 12
            near_low = any(h['tide'].get('near_low') is True for h in group)
            score = rank * 100 + duration * 10 + (25 if location == 'south_milton' and near_low else 0) + (3 if morning else 0)
            status = ('HEADS-UP' if group[0]['forecast_day'] >= 4 else
                      ('WATCH' if rank == 1 else 'GO CANDIDATE'))
            candidates.append({'start_local': start.astimezone(UK).isoformat(),
                'end_local': end.astimezone(UK).isoformat(), 'duration_hours': duration,
                'status': status, 'wind_suitability': min(group, key=lambda h: WIND_RANK[h['wind_suitability']])['wind_suitability'],
                'sustained_knots': [min(h['sustained_knots'] for h in group), max(h['sustained_knots'] for h in group)],
                'gust_knots_max': max(h['gust_knots'] for h in group),
                'direction_degrees': [h['direction_degrees'] for h in group],
                'confidence': 'low', 'near_low': near_low if near_low else None,
                'reasons': sorted({r for h in group for r in h['reasons']} | ({'Preferred morning session'} if morning else set())
                           | ({'Near predicted low tide; check reef exposure locally'} if location == 'south_milton' and near_low else set())),
                'cautions': sorted({c for h in group for c in h['cautions']}), '_score': score})
    selected = []
    for window in sorted(candidates, key=lambda w: (-w['_score'], w['start_local'])):
        if any(utc(window['start_local']) < utc(w['end_local']) and utc(w['start_local']) < utc(window['end_local']) for w in selected):
            continue
        selected.append(window)
        if len(selected) == 2:
            break
    for w in selected:
        w.pop('_score')
    return sorted(selected, key=lambda w: w['start_local'])


def assessments(snapshots, config, now, tides=None):
    output = {}
    today = now.astimezone(UK).date()
    for location in ('south_milton', 'bigbury'):
        indexed = {}
        for s in snapshots:
            if s['location'] == location and fresh(s, now):
                indexed[s['kind']] = {r['valid_time']: r for r in s['rows']}
        # UTC iteration keeps both repeated UK clock-change hours distinct.
        start = datetime.combine(today, datetime.min.time(), UK).astimezone(timezone.utc)
        end = datetime.combine(today + timedelta(days=7), datetime.min.time(), UK).astimezone(timezone.utc)
        valid = start
        hours = []
        while valid < end:
            if valid < now:
                valid += timedelta(hours=1)
                continue
            t = valid.isoformat()
            local = valid.astimezone(UK)
            wind, marine = indexed.get('wind', {}).get(t), indexed.get('marine', {}).get(t)
            prediction = (tides or {}).get(location)
            if prediction:
                try:
                    age = (now - utc(prediction['retrieved_at'])).total_seconds()
                    if not 0 <= age <= 86400:
                        prediction = None
                except (KeyError, TypeError, ValueError):
                    prediction = None
            tide = tide_context(valid, prediction)
            rating = assess(wind, marine, config[location], now, location, tide=tide)
            rating['provisional_recommendation'] = rating['overall_recommendation']
            day = (local.date() - today).days + 1
            if day >= 4 and rating['status'] in ('WATCH', 'GO CANDIDATE', 'STRONG GO CANDIDATE', 'GO'):
                rating.update(status='HEADS-UP', overall_recommendation='HEADS-UP', confidence='low')
                rating['cautions'].append('Days 4–7: timing confidence lower; recheck nearer the day')
            daylight = (solar_elevation(valid, *LOCATIONS[location]) >= 0
                        and solar_elevation(valid + timedelta(hours=1), *LOCATIONS[location]) >= 0)
            hours.append({'location': location, 'valid_time': t, 'local_time': local.isoformat(),
                'local_date': local.date().isoformat(), 'timezone_abbreviation': local.tzname(), 'forecast_day': day,
                'sustained_knots': wind['wind_speed_10m'] if wind else None,
                'gust_knots': wind['wind_gusts_10m'] if wind else None,
                'direction_degrees': wind['wind_direction_10m'] if wind else None,
                'offshore_swell': {'height_m': marine['swell_wave_height'], 'period_seconds': marine['swell_wave_period'],
                                   'direction_degrees': marine['swell_wave_direction']} if marine else None,
                'daylight_session_hour': daylight, **rating})
            if marine is None:
                hours[-1]['cautions'].append('Offshore marine forecast unavailable')
            valid += timedelta(hours=1)
        daily = []
        for n in range(7):
            date = (today + timedelta(days=n)).isoformat()
            group = [h for h in hours if h['local_date'] == date]
            windows = session_windows(group, location)
            status = ('HEADS-UP' if n >= 3 else ('GO CANDIDATE' if any(w['status'] == 'GO CANDIDATE' for w in windows) else 'WATCH')) if windows else (
                'NO GO' if group and all(h['wind_suitability'] != 'UNKNOWN' for h in group) else 'HEADS-UP')
            daily.append({'date': date, 'status': status, 'windows': windows,
                'reasons': ['Best viable daylight sessions; wind suitability remains provisional'] if windows else
                           ['No viable remaining full daylight hour in this forecast' if status == 'NO GO' else 'Forecast data missing; no reliable daylight session identified'],
                'summary_basis': 'best remaining daylight sessions, not worst hour'})
        output[location] = {'daily': daily, 'hourly': hours}
    return {'schema_version': 2, 'rules_version': 'owner-2026-10-19',
            'generated_at': now.isoformat(), 'stale_after_seconds': MAX_AGE,
            'timezone': 'Europe/London', 'daylight_basis': 'NOAA solar elevation approximation; complete hours with sun above horizon',
            'locations': output}

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
