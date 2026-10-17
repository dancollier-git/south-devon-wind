#!/usr/bin/env python3
"""One public-feed GET per invocation; Python standard library only."""
import argparse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import math
from pathlib import Path
import sys
from urllib.request import Request, urlopen

FEED = 'https://nci-prawlepoint.org.uk/scripts/wx-data.php'


def normalize(data, now=None, stale_after=600):
    now = now or datetime.now(timezone.utc)
    warnings = []
    units = str(data.get('windunit', '')).strip().lower()
    factors = {'kts': 1, 'knots': 1, 'kt': 1, 'mph': 1 / 1.150779448,
               'km/h': 1 / 1.852, 'm/s': 1 / 0.514444444}
    if units not in factors:
        raise ValueError(f'Unsupported windunit: {units!r}')

    def number(key, low=0, high=None, wind=False):
        try:
            value = float(data[key])
            if not math.isfinite(value) or value < low or (high is not None and value > high):
                raise ValueError()
            return round(value * (factors[units] if wind else 1), 3)
        except (KeyError, TypeError, ValueError):
            warnings.append(f'Missing or invalid {key}')
            return None

    raw_time = data.get('obstime')
    observation = None
    age = None
    try:
        observation = parsedate_to_datetime(raw_time)
        if observation.tzinfo is None:
            raise ValueError('Observation timestamp has no timezone')
        observation = observation.astimezone(timezone.utc)
        age = round((now - observation).total_seconds(), 1)
    except (TypeError, ValueError, OverflowError):
        warnings.append('Observation timestamp unavailable or invalid; freshness unknown')
    stale = None if age is None else age > stale_after
    if stale:
        warnings.append(f'Observation is {age:g} seconds old (limit {stale_after:g})')
    if age is not None and age < -60:
        warnings.append('Observation timestamp is in the future; check clocks')
    if str(data.get('SensorContactLost', '0')) != '0':
        warnings.append('Feed reports lost sensor contact')
    result = {
        'source': FEED,
        'retrieved_at': now.isoformat(),
        'observation_time': observation.isoformat() if observation else None,
        'observation_time_raw': raw_time,
        'age_seconds': age,
        'wind_speed_knots': number('wspeed', wind=True),
        'latest_wind_speed_knots': number('wlatest', wind=True),
        'gust_knots': number('wgust', wind=True),
        'direction_degrees': number('bearing', high=360),
        'average_direction_degrees': number('avgbearing', high=360),
        'dominant_direction': data.get('domwinddir'),
        'averaging_period_minutes': 10,
        'stale': stale,
        'stale_after_seconds': stale_after,
        'warnings': warnings,
    }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, help='Parse saved JSON without a network request')
    parser.add_argument('--save-raw', type=Path)
    parser.add_argument('--stale-after', type=float, default=600)
    args = parser.parse_args()
    try:
        if args.stale_after < 0 or not math.isfinite(args.stale_after):
            raise ValueError('stale-after must be finite and nonnegative')
        if args.input:
            raw = args.input.read_bytes()
        else:
            request = Request(FEED, headers={'User-Agent': 'PrawleWeatherPrototype/0.1',
                                             'Accept': 'application/json'})
            with urlopen(request, timeout=20) as response:
                raw = response.read(262145)
            if len(raw) > 262144:
                raise ValueError('Unexpectedly large response')
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError('Expected a JSON object')
        result = normalize(data, stale_after=args.stale_after)
        if args.save_raw:
            args.save_raw.write_bytes(raw)
        print(json.dumps(result, indent=2, allow_nan=False))
    except Exception as exc:
        print(json.dumps({'source': FEED, 'error': str(exc), 'stale': None,
                          'warnings': ['No usable reading; freshness unknown']}))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
