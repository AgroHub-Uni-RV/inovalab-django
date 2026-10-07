import os
from pathlib import Path
import subprocess
import sys
from django.test import SimpleTestCase


class PortabilityProcessTests(SimpleTestCase):
    def test_separate_native_host_with_url_prefix(self):
        env = {key: value for key, value in os.environ.items() if not key.startswith(('DJANGO_', 'DATABASE_', 'VERCEL'))}
        result = subprocess.run([sys.executable, 'manage.py', 'test', 'inovalab_app.tests.portability',
                                 '--settings=inovalab_app.tests.host_settings', '--noinput', '--verbosity=0'],
                                cwd=Path(__file__).resolve().parents[2], env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
