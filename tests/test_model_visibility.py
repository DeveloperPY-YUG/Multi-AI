"""One-click hide/restore model behavior and persistence across sessions."""

import tempfile
import unittest
from pathlib import Path

from backend.config import Config, model_entry
from backend.model_manager import Models


class VisibilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "settings.json"
        self.config = Config(self.path)
        self.models = Models(self.config)

    def test_discovered_model_remains_hidden_after_refresh(self):
        self.models.discovered["groq"] = [
            model_entry("groq", "sample-model", "Sample Model")
        ]
        self.models.remove("groq", "sample-model")
        self.assertNotIn("sample-model", [m["id"] for m in self.models.all()])
        self.models.discovered["groq"] = [
            model_entry("groq", "sample-model", "Sample Model")
        ]
        self.assertNotIn("sample-model", [m["id"] for m in self.models.all()])
        # Even after restart the discovered name is retained for restoration.
        new = Models(Config(self.path))
        new.restore("groq", "sample-model")
        restored = next(m for m in new.all() if m["id"] == "sample-model")
        self.assertEqual(restored["name"], "Sample Model")

    def test_manual_model_and_rename_survive_hide_restart_and_restore(self):
        self.models.save("groq", "my-custom-model", "My Favorite AI")
        self.models.remove("groq", "my-custom-model")
        self.assertNotIn("my-custom-model", [m["id"] for m in self.models.all()])
        new = Models(Config(self.path))
        self.assertNotIn("my-custom-model", [m["id"] for m in new.all()])
        new.restore("groq", "my-custom-model")
        restored = next(m for m in new.all() if m["id"] == "my-custom-model")
        self.assertEqual(restored["name"], "My Favorite AI")
        self.assertTrue(restored["saved"])

    def test_removing_active_default_resets_default_id(self):
        self.models.save("groq", "current-model", "Current")
        self.config.update(defaultProvider="groq", defaultModel="current-model")
        self.models.remove("groq", "current-model")
        self.assertEqual(self.config.data["defaultModel"], "")

    def test_unknown_models_cannot_fill_hidden_model_list(self):
        with self.assertRaises(ValueError):
            self.models.remove("groq", "does-not-exist")
        self.assertEqual(self.config.data["hiddenModels"], [])


if __name__ == "__main__":
    unittest.main()
