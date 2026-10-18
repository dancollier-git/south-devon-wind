"""Compare archived Prawle forecasts with subsequent usable Prawle readings."""
from datetime import timedelta
import json
import math
from forecast import utc


def report(root, now):
    observations = {}
    path = root / 'docs/history.json'
    for obs in json.loads(path.read_text()) if path.exists() else []:
        try:
            stamp = utc(obs['observation_time'])
            value = obs['wind_speed_knots']
            if (obs.get('status') != 'ok' or obs.get('warnings') or obs.get('error')
                    or obs.get('stale') is not False or stamp > now
                    or isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or value < 0):
                continue
            observations.setdefault(stamp, value)
        except (KeyError, TypeError, ValueError):
            continue
    snapshots = []
    for path in sorted((root / 'archive/forecasts').glob('*.jsonl')):
        for line in path.read_text().splitlines():
            bundle = json.loads(line)
            for s in bundle['snapshots']:
                if s['location'] == 'prawle' and s['kind'] == 'wind' and s['status'] == 'ok':
                    snapshots.append((utc(s['retrieved_at']), {utc(r['valid_time']): r for r in s['rows']}))
    snapshots.sort(key=lambda s: s[0], reverse=True)
    metrics = []
    for lead in (0, 24, 48, 72, 96, 120, 144):
        errors = []
        actual_leads = []
        for stamp, observed in observations.items():
            valid = stamp.replace(minute=0, second=0, microsecond=0)
            if stamp - valid > timedelta(minutes=30):
                valid += timedelta(hours=1)
            for retrieved, rows in snapshots:
                # Require retrieval before both valid time and observation; no hindsight.
                hours = (valid - retrieved).total_seconds() / 3600
                if retrieved > stamp or not lead <= hours < lead + 24 or valid not in rows:
                    continue
                errors.append(rows[valid]['wind_speed_10m'] - observed)
                actual_leads.append(hours)
                break
        count = len(errors)
        metrics.append({'lead_hours': [lead, lead + 24], 'samples': count,
                        'bias_knots': sum(errors) / count if count else None,
                        'mae_knots': sum(map(abs, errors)) / count if count else None,
                        'rmse_knots': math.sqrt(sum(e * e for e in errors) / count) if count else None,
                        'mean_retrieval_lead_hours': sum(actual_leads) / count if count else None})
    return {'generated_at': now.isoformat(), 'location': 'prawle', 'source': 'open-meteo',
            'lead_basis': 'retrieval, not model issue time', 'error_sign': 'forecast minus observed',
            'matching': 'nearest forecast hour within 30 minutes; one latest eligible snapshot per observation per band',
            'limitations': 'Elevated station; sparse hourly samples; not beach calibration. No automatic threshold changes.',
            'metrics': metrics}
