"""Recalculate publication freshness at read time (exit 1 if unhealthy)."""
from datetime import datetime, timezone
import json
import sys
from forecast import ROOT, LOCATIONS, fresh, utc, MAX_AGE


def check(bundle, ratings, now):
    expected = {(loc, kind) for loc in LOCATIONS for kind in ('wind', 'marine')
                if loc != 'prawle' or kind == 'wind'}
    sources = bundle.get('snapshots', [])
    seen = {(s.get('location'), s.get('kind')) for s in sources}
    if seen != expected or len(sources) != len(expected):
        return False
    try:
        age = (now - utc(ratings['generated_at'])).total_seconds()
        return (all(fresh(s, now) for s in sources) and 0 <= age <= MAX_AGE
                and set(ratings['locations']) == {'south_milton', 'bigbury'})
    except (KeyError, ValueError, TypeError):
        return False


if __name__ == '__main__':
    try:
        ok = check(json.loads((ROOT / 'docs/forecast.json').read_text()),
                   json.loads((ROOT / 'docs/assessments.json').read_text()),
                   datetime.now(timezone.utc))
    except (OSError, ValueError):
        ok = False
    print('Forecast publication fresh' if ok else 'Forecast publication missing, stale or unhealthy')
    sys.exit(0 if ok else 1)
