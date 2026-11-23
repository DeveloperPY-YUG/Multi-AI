import tempfile
import unittest
from pathlib import Path

from backend.migration import preferred_settings_path
from backend.key_manager import Vault, SERVICE, LEGACY_SERVICE
from tests.test_providers import MemoryCredentials


class ReleaseMigrationTests(unittest.TestCase):
    def test_pref_copy_on_first_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp, 'MULTIAI', 'settings.json')
            target = Path(tmp, 'MULTI-AI', 'settings.json')
            source.parent.mkdir()
            source.write_text('{"scale":100}', encoding='utf-8')
            self.assertEqual(preferred_settings_path(target, source), target)
            self.assertEqual(target.read_text(), source.read_text())
            target.write_text('{"scale":120}')
            self.assertEqual(preferred_settings_path(target, source), target)
            self.assertEqual(target.read_text(), '{"scale":120}')

    def test_old_cloud_credentials_migrate_to_new_service(self):
        mock = MemoryCredentials()
        mock.set_password(LEGACY_SERVICE, 'groq', 'test-credential')
        vault = Vault(mock)
        self.assertEqual(vault.get('groq', 'https://example.com'), 'test-credential')
        self.assertEqual(mock.get_password(SERVICE, 'groq'), 'test-credential')
        self.assertIsNone(mock.get_password(LEGACY_SERVICE, 'groq'))
        vault.delete('groq', 'https://example.com')
        self.assertIsNone(vault.get('groq', 'https://example.com'))


if __name__ == '__main__':
    unittest.main()
