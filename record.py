"""Run the existing checker once; preserve readings and failures for Pages."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
ROOT = Path(__file__).resolve().parent


def classify(reading):
    valid = (not reading.get('error') and reading.get('stale') is False
             and not reading.get('warnings')
             and isinstance(reading.get('wind_speed_knots'), (int, float)))
    reading['status'] = 'ok' if valid else 'warning'
    reading['wind_alert'] = bool(valid and reading['wind_speed_knots'] >= 20)
    return reading


def main():
    try:
        result = subprocess.run([sys.executable, str(ROOT / 'weather.py')],
                                capture_output=True, text=True, timeout=45)
        reading = json.loads(result.stdout)
        if not isinstance(reading, dict):
            raise ValueError('Checker output is not an object')
        if result.returncode:
            reading.setdefault('error', 'Checker failed')
    except (ValueError, TypeError, subprocess.TimeoutExpired) as exc:
        reading = {'error': str(exc), 'stale': None,
                   'warnings': ['No usable reading; freshness unknown']}
    reading.setdefault('retrieved_at', datetime.now(timezone.utc).isoformat())
    classify(reading)
    docs = ROOT / 'docs'
    docs.mkdir(exist_ok=True)
    history_path = docs / 'history.json'
    history = json.loads(history_path.read_text()) if history_path.exists() else []
    history.append(reading)
    for name, value in [('latest.json', reading), ('history.json', history)]:
        path = docs / name
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
        temp.replace(path)
    print(json.dumps(reading, indent=2))
    return 0 if reading['status'] == 'ok' else 1


if __name__ == '__main__':
    sys.exit(main())
