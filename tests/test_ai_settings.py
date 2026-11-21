import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rooplan.agent import Agent, QwenClient
from rooplan.settings import AISettings, DEFAULT_BASE
from rooplan.store import Store


class AISettingsTests(unittest.TestCase):
    def test_encrypted_restart_edit_and_clear(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = AISettings(folder)
            settings.save("qwen", DEFAULT_BASE, "qwen3.8-flash", "test-secret-credential")
            self.assertNotIn("test-secret-credential", settings.path.read_text(encoding="utf-8"))
            self.assertNotIn("credential", settings.public())
            loaded = AISettings(folder)
            self.assertEqual(loaded.key, "test-secret-credential")
            loaded.save("qwen", DEFAULT_BASE, "another-model", "")
            self.assertEqual(AISettings(folder).model, "another-model")
            self.assertEqual(AISettings(folder).key, "test-secret-credential")
            with self.assertRaises(ValueError):
                loaded.save("compatible", "https://example.com/v1", "model", "")
            loaded.save("compatible", "https://example.com/v1", "model", "other-secret")
            self.assertEqual(AISettings(folder).provider, "compatible")
            loaded.save("compatible", "https://example.com/v1", "model", "", clear=True)
            self.assertEqual(AISettings(folder).key, "")

    def test_corrupt_credentials_can_be_replaced(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = AISettings(folder)
            settings.path.write_text(json.dumps(dict(base=DEFAULT_BASE, model="qwen3.8-flash", credential="broken")))
            loaded = AISettings(folder)
            self.assertFalse(loaded.key)
            self.assertTrue(loaded.error)
            loaded.save("qwen", DEFAULT_BASE, "qwen3.8-flash", "replacement")
            self.assertEqual(AISettings(folder).key, "replacement")

    def test_client_limits_output_and_only_sends_qwen_options_to_qwen(self):
        response = json.dumps(dict(choices=[dict(message=dict(content="", tool_calls=[]))])).encode()
        for provider in ("qwen", "compatible"):
            with patch("rooplan.agent.urllib.request.urlopen") as request:
                request.return_value.__enter__.return_value.read.return_value = response
                QwenClient(key="test", provider=provider).complete([])
                body = json.loads(request.call_args.args[0].data)
                self.assertEqual(body["max_tokens"], 2800)
                self.assertEqual(body["temperature"], 0.1)
                self.assertEqual("enable_thinking" in body, provider == "qwen")

    def test_simple_notice_finishes_in_one_call_and_keeps_one_activity(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder)/"test.db")
            key = store.new_draft("Saturday gathering and visit")
            row = dict(fields=dict(title="Museum visit", start="2026-11-21T09:15",
                                   end="2026-11-21T11:30", location="History hall"))
            class Model:
                count = 0

                def complete(self, messages):
                    self.count += 1
                    return dict(tool_calls=[dict(id="1", function=dict(name="propose_changes",
                        arguments=json.dumps(dict(changes=[row, row], note=""))))])

            model = Model()
            draft = Agent(store, model).run(key)
            self.assertEqual(model.count, 1)
            self.assertEqual(len(draft["rows"]), 1)
            self.assertFalse(store.all())
