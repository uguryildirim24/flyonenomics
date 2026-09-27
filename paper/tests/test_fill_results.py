"""Only the requested paper-filling contract; no engine or full-suite imports."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PAPER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PAPER))
import fill_results as filler


class FillResultsTest(unittest.TestCase):
    def setUp(self):
        self.record = filler.load_json(PAPER / "tests/synthetic-result.json")
        self.confirmation = filler.load_json(PAPER / 'tests/synthetic-confirmation.json')
        self.template = filler.TEMPLATE.read_text()
        self.bindings = filler.load_json(filler.BINDINGS)

    def render(self, record=None, template=None):
        return filler.render(self.record if record is None else record,
                             self.confirmation, self.template if template is None else template, self.bindings)

    def test_all_slots_use_exact_frozen_fields_and_synthetic_banner(self):
        output = self.render()
        self.assertFalse(filler.TOKEN.search(output))
        self.assertIn("SYNTHETIC FIXTURE --- MADE-UP NUMBERS", output)
        self.assertIn("gap of 0.1 template units (95\\%", output)
        self.assertIn("difference in gaps was -0.09 (95\\%", output)
        self.assertIn("no detected difference", output)
        self.assertIn("affine residual was 0.025 (nominal 95\\%", output)
        self.assertIn("WT vehicle 0.045 [0, 0.09]", output)
        self.assertIn("10/1024", output)
        self.assertEqual(self.template.count(r"\result{GEN_MEAN}"), 2)

    def test_missing_wrong_or_nonfinite_fields_fail_without_fake_numbers(self):
        for mutation in ("missing", "nan", "null", "bool", "interval", "order", "version",
                         "history", "p-range", "residual", "bootstrap-flags"):
            record = copy.deepcopy(self.record)
            if mutation == "missing":
                del record["primary"][0]["mean"]
            elif mutation in ("nan", "null", "bool"):
                record["primary"][0]["mean"] = {"nan": float("nan"), "null": None, "bool": True}[mutation]
            elif mutation == "interval":
                record["primary"][0]["ci95"] = [1, -1]
            elif mutation == "order":
                record["primary"].reverse()
            elif mutation == "version":
                record["version"] = "not-the-frozen-schema"
            elif mutation == "history":
                record["H_per_seed_condition"] = record["H_per_seed_condition"][:-1]
            elif mutation == "p-range":
                record["primary"][0]["p_holm"] = 1.1
            elif mutation == "residual":
                record["affine_secondary"]["residual"] = [0.0] * 9
            else:
                record["bootstrap"]["template_uncertainty_included"] = False
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.render(record)
        with self.assertRaises(ValueError):
            self.render(template=self.template + r"\result{UNBOUND}")

    def test_text_is_escaped_and_nonzero_small_results_are_not_zeroed(self):
        self.assertEqual(filler.escape_tex(r"50% & a_b \input{evil}"),
                         r"50\% \& a\_b \textbackslash{}input\{evil\}")
        self.record["primary"][0]["mean"] = 1e-9
        self.assertIn("gap of 1e-09 template units", self.render())

    def test_filling_cannot_certify_human_review(self):
        del self.record["_paper_fixture"]
        self.record["raw_sha256"] = {"raw": "b" * 64}
        self.record["calibration_sha256"] = {"calibration": "c" * 64}
        self.record["mixture"] = {}
        self.assertIn("SYNTHETIC FIXTURE", self.render())
        for field in ("raw_sha256", "calibration_sha256", "mixture"):
            malformed = copy.deepcopy(self.record)
            del malformed[field]
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.render(malformed)

    def test_cli_writes_labelled_synthetic_output_and_preserves_sources_on_error(self):
        source = PAPER / "tests/synthetic-result.json"
        before = source.read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "synthetic.tex"
            subprocess.run([sys.executable, str(PAPER / "fill_results.py"), str(source),
                            str(PAPER / 'tests/synthetic-confirmation.json'), "--out", str(out)], check=True, capture_output=True)
            self.assertIn("% Confirmation JSON SHA-256:", out.read_text())
            self.assertIn("SYNTHETIC FIXTURE", out.read_text())
            with self.assertRaises(ValueError):
                filler.fill(source, PAPER / 'tests/synthetic-confirmation.json', source)
            invalid = Path(tmp) / "invalid.json"
            invalid.write_text(json.dumps({**self.record, "version": "wrong"}))
            saved = out.read_bytes()
            with self.assertRaises(ValueError):
                filler.fill(invalid, PAPER / 'tests/synthetic-confirmation.json', out)
            self.assertEqual(saved, out.read_bytes())
        self.assertEqual(before, source.read_bytes())


if __name__ == "__main__":
    unittest.main()
