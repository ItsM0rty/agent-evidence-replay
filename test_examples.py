import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from run_example import load_fixture

ROOT = Path(__file__).resolve().parent
EXAMPLES = ROOT / "examples"


class ExampleContract(unittest.TestCase):
    def test_checked_in_outputs_match_every_fixture(self):
        inputs = sorted(EXAMPLES.glob("*.json"))
        inputs = [path for path in inputs if not path.name.endswith(".expected.json")]
        self.assertEqual(len(inputs), 6)
        for path in inputs:
            with self.subTest(fixture=path.name):
                expected = path.with_suffix(".expected.json")
                self.assertEqual(load_fixture(path), json.loads(expected.read_text()))

    def test_readme_command_runs_from_another_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([
                sys.executable, str(ROOT / "run_example.py"),
                str(EXAMPLES / "shared-key.json"),
            ], cwd=directory, text=True, capture_output=True, check=True)
        agents = [row["agent"] for row in json.loads(result.stdout)["observations"]]
        self.assertEqual(agents, ["calendar-agent", "mail-agent"])

    def test_cli_reports_invalid_json_without_a_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text("{", encoding="utf-8")
            result = subprocess.run([
                sys.executable, str(ROOT / "run_example.py"), str(path)
            ], text=True, capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("Invalid fixture:", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_duplicate_session_bindings_are_rejected(self):
        fixture = json.loads((EXAMPLES / "shared-key.json").read_text())
        fixture["bindings"].append(fixture["bindings"][0])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text(json.dumps(fixture), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate binding"):
                load_fixture(path)

    def test_duplicate_json_fields_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text('{"now": 100, "now": 200}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate JSON field: now"):
                load_fixture(path)

    def test_heartbeat_container_has_a_clear_validation_error(self):
        fixture = json.loads((EXAMPLES / "shared-key.json").read_text())
        fixture["heartbeats"] = []
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text(json.dumps(fixture), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "heartbeats must be an object"):
                load_fixture(path)


if __name__ == "__main__":
    unittest.main()
