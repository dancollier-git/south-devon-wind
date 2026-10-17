"""Exercise the exact workflow authorization code with untrusted event payloads."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

WORKFLOW = Path(__file__).resolve().parents[1] / '.github/workflows/wind.yml'
CODE = textwrap.dedent(WORKFLOW.read_text().split("python3 - <<'PYAUTH'\n", 1)[1].split('          PYAUTH', 1)[0])


class CommandTests(unittest.TestCase):
    def event(self):
        return {'action': 'created', 'issue': {'number': 1},
                'comment': {'body': '/wind', 'user': {'login': 'dancollier-git'}},
                'repository': {'owner': {'login': 'dancollier-git'}}}

    def allowed(self, event, name='issue_comment'):
        with tempfile.TemporaryDirectory() as directory:
            payload, output = Path(directory)/'event.json', Path(directory)/'output'
            payload.write_text(json.dumps(event))
            subprocess.run([sys.executable, '-c', CODE], check=True,
                           env={**os.environ, 'GITHUB_EVENT_PATH': str(payload),
                                'GITHUB_EVENT_NAME': name, 'GITHUB_OUTPUT': str(output)})
            return output.read_text() == 'allowed=true\n'

    def test_authorized_command(self):
        self.assertTrue(self.allowed(self.event()))

    def test_reject_wrong_command_and_missing_fields(self):
        for body in ['/WIND', '/wind ', ' /wind', '/wind\n', '/wind now', '', '$(id)']:
            event = self.event()
            event['comment']['body'] = body
            with self.subTest(body=body):
                self.assertFalse(self.allowed(event))
        self.assertFalse(self.allowed({}))

    def test_reject_other_senders_issues_and_events(self):
        mutations = [lambda e: e['comment']['user'].update(login='someone-else'),
                     lambda e: e['issue'].update(number=2),
                     lambda e: e['issue'].update(pull_request={}),
                     lambda e: e.update(action='edited'),
                     lambda e: e['repository']['owner'].update(login='someone-else')]
        for mutate in mutations:
            event = copy.deepcopy(self.event())
            mutate(event)
            self.assertFalse(self.allowed(event))
        self.assertFalse(self.allowed(self.event(), 'issues'))

    def test_existing_triggers(self):
        for name in ['schedule', 'workflow_dispatch', 'push']:
            self.assertTrue(self.allowed({}, name))
