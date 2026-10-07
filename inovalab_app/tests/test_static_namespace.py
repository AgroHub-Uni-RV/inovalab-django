import re
from pathlib import Path
from unittest.mock import patch
from django.contrib.staticfiles import finders
from django.test import TestCase
from inovalab_app.conteudo.institutional_content import EQUIPMENT, SERVICES


class StaticNamespaceTests(TestCase):
    def test_institutional_templates_and_content_reference_bundled_namespaced_assets(self):
        directory = Path(__file__).resolve().parents[1] / 'templates'
        assets = []
        for template in directory.rglob('*.html'):
            assets.extend(re.findall(r"{%\s*static\s+['\"]([^'\"]+)['\"]", template.read_text(encoding='utf-8')))
        assets += [entry[key] for entries in (EQUIPMENT, SERVICES) for entry in entries for key in ('icon', 'image') if entry.get(key)]
        for asset in assets:
            with self.subTest(asset=asset):
                self.assertTrue(asset.startswith('inovalab_app/'))
                self.assertIsNotNone(finders.find(asset))
