#!/usr/bin/env python3
"""Fill the paper's named LaTeX slots from adhd_study.py analyse JSON.

Formatting only: no model imports, inference, significance decisions or replay
certification. The summary JSON cannot certify the separate d-0025 audit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "manuscript.tex"
BINDINGS = HERE / "result-bindings.json"
TOKEN = re.compile(r"\\result\{([A-Z][A-Z0-9_]*)\}")
STATUS = r"\newcommand{\paperstatus}{PREPRINT DRAFT --- HUMAN AUTHOR APPROVAL PENDING}"


def load_json(path: Path):
    def reject(value):
        raise ValueError(f"non-finite JSON constant: {value}")
    return json.loads(path.read_text(), parse_constant=reject)


def resolve(record, pointer: str):
    """Read a JSON Pointer; no default values for absent results."""
    if not pointer.startswith("/"):
        raise ValueError(f"not a JSON Pointer: {pointer}")
    value = record
    for part in pointer[1:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def number(value) -> str:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"expected finite number, got {value!r}")
    # Keep small nonzero results visible rather than rounding them to zero.
    return format(value, ".6g")


def integer(value) -> str:
    if type(value) is not int or value < 0:
        raise ValueError(f"expected nonnegative integer, got {value!r}")
    return str(value)


def escape_tex(value: str) -> str:
    escapes = {"\\": r"\textbackslash{}", "{": r"\{", "}": r"\}",
               "$": r"\$", "&": r"\&", "#": r"\#", "%": r"\%",
               "_": r"\_", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
    return "".join(escapes.get(c, c) for c in value)


def formatted(value, kind: str) -> str:
    if kind.startswith("condition_"):
        mode, index = kind.split(":")
        index = int(index)
        if mode not in ("condition_mean", "condition_range") or index not in range(4):
            raise ValueError("unknown condition binding")
        if not isinstance(value, list) or len(value) != 10:
            raise ValueError("expected ten condition rows")
        data = [row[index] for row in value]
        for item in data:
            number(item)
        if mode == "condition_mean":
            return number(sum(data) / len(data))
        return "[" + ", ".join(number(v) for v in (min(data), max(data))) + "]"
    if kind == "sign_count":
        number(value)
        n = value * 1024
        if not 0 <= value <= 1 or not n.is_integer():
            raise ValueError("not an exact 1024-assignment sign p value")
        return f"{int(n)}/1024"
    if kind in ("decision", "decision_abstract", "decision_discussion"):
        if type(value) is not bool:
            raise ValueError("expected confirmed boolean")
        return {
            "decision": ("confirmed" if value else "not confirmed"),
            "decision_abstract": ("the independent follow-up met the frozen negative-contrast criterion." if value else
                                  "the earlier nominal hint did not replicate under the frozen negative-contrast criterion."),
            "decision_discussion": ("The independent follow-up met the frozen confirmation rule; this supports a candidate neural signature, not a clinical or behavioural claim." if value else
                                    "The nominal hint from the first study did not replicate in the independent follow-up under the frozen rule. The pilot contrast cannot be treated as a confirmed finding."),
        }[kind]
    if kind == "number":
        return number(value)
    if kind == "integer":
        return integer(value)
    if kind == "interval":
        if not isinstance(value, list) or len(value) != 2:
            raise ValueError("expected two interval endpoints")
        ends = [number(x) for x in value]
        if value[0] > value[1]:
            raise ValueError("reversed interval")
        return "[" + ", ".join(ends) + "]"
    if kind == "counts":
        if not isinstance(value, list) or len(value) != 10:
            raise ValueError("expected one unresolved-cell count per held seed")
        counts = [integer(x) for x in value]
        if any(x > 245 for x in value):
            raise ValueError("unresolved-cell count exceeds the 245-cell readout")
        return ", ".join(counts)
    if kind == "sha256":
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
            raise ValueError("expected SHA-256 hex")
        return r"\nolinkurl{" + value + "}"
    if kind == "text":
        if not isinstance(value, str) or not value.strip():
            raise ValueError("expected nonempty text")
        return escape_tex(value)
    raise ValueError(f"unknown format: {kind}")


def finite_list(value, length: int, label: str) -> None:
    if not isinstance(value, list) or len(value) != length:
        raise ValueError(f"{label} must contain {length} values")
    for item in value:
        try:
            number(item)
        except ValueError as exc:
            raise ValueError(f"{label}: {exc}") from exc


def hash_map(value, label: str, *, allow_empty: bool) -> None:
    if not isinstance(value, dict) or (not allow_empty and not value):
        raise ValueError(f"{label} must be a nonempty hash map")
    for name, digest in value.items():
        if not isinstance(name, str) or not name:
            raise ValueError(f"{label} has an invalid file name")
        formatted(digest, "sha256")


def validate_record(record: dict) -> bool:
    """Validate the frozen summary shape without recomputing any result."""
    if not isinstance(record, dict) or record.get("version") != "male-history-v1":
        raise ValueError("expected frozen result version male-history-v1")
    fixture = record.get("_paper_fixture")
    if fixture not in (None, "synthetic"):
        raise ValueError("unknown _paper_fixture label")
    synthetic = fixture == "synthetic"

    primary = record.get("primary")
    expected = ["genotype", "difference_in_differences"]
    if (not isinstance(primary, list) or len(primary) != 2 or
            any(not isinstance(item, dict) for item in primary) or
            [item.get("name") for item in primary] != expected):
        raise ValueError("primary names/order differ from the frozen schema")
    readings = {"detected difference", "no detected difference",
                "nominal only; not Holm significant"}
    for index, item in enumerate(primary):
        finite_list(item.get("per_seed"), 10, f"primary/{index}/per_seed")
        if item.get("reading") not in readings:
            raise ValueError(f"primary/{index}/reading is not a frozen reading")
        for field in ("p_exact", "p_holm"):
            value = item.get(field)
            number(value)
            if not 0 <= value <= 1:
                raise ValueError(f"primary/{index}/{field} must be in [0, 1]")

    history = record.get("H_per_seed_condition")
    if not isinstance(history, list) or len(history) != 10:
        raise ValueError("H_per_seed_condition must contain ten seeds")
    for index, row in enumerate(history):
        finite_list(row, 4, f"H_per_seed_condition/{index}")
    finite_list(record.get("genotype_gaps"), 2, "genotype_gaps")

    affine = record.get("affine_secondary")
    if not isinstance(affine, dict):
        raise ValueError("affine_secondary must be an object")
    finite_list(affine.get("residual"), 10, "affine_secondary/residual")

    bootstrap = record.get("bootstrap")
    if not isinstance(bootstrap, dict):
        raise ValueError("bootstrap must be an object")
    if bootstrap.get("pair_selection_uncertainty_included") is not False:
        raise ValueError("pair-selection uncertainty flag differs from frozen analysis")
    if bootstrap.get("template_uncertainty_included") is not True:
        raise ValueError("template-uncertainty flag differs from frozen analysis")
    if bootstrap.get("replicates") != 10_000:
        raise ValueError("frozen analysis requires 10000 bootstrap resamples")

    hash_map(record.get("raw_sha256"), "raw_sha256", allow_empty=synthetic)
    hash_map(record.get("calibration_sha256"), "calibration_sha256", allow_empty=synthetic)
    if not synthetic and not isinstance(record.get("mixture"), dict):
        raise ValueError("real analysis record is missing mixture outputs")
    return synthetic


def validate_confirmation(record: dict) -> bool:
    if not isinstance(record, dict) or record.get("version") != "male-history-confirm-v1":
        raise ValueError("expected frozen confirmation version")
    fixture = record.get("_paper_fixture")
    if fixture not in (None, "synthetic"):
        raise ValueError("unknown confirmation fixture label")
    primary = record["primary"]
    if primary["name"] != "genotype" or type(primary["confirmed"]) is not bool:
        raise ValueError("confirmation primary identity or decision missing")
    finite_list(primary["per_seed"], 40, "confirmation per_seed")
    mean = primary["mean"]
    number(mean)
    if abs(mean - sum(primary["per_seed"]) / 40) > 1e-10:
        raise ValueError("confirmation estimate disagrees with per-seed values")
    ci = primary["ci95"]
    formatted(ci, "interval")
    sign = primary["sign_randomisation"]
    integer(sign["extreme"])
    number(sign["p"])
    if (integer(sign["draws"]) != "1000000" or integer(sign["seed"]) != "14620260926" or
            sign["extreme"] > sign["draws"] or
            abs(sign["p"] - (sign["extreme"] + 1) / (sign["draws"] + 1)) > 1e-12):
        raise ValueError("sign randomisation differs from frozen procedure")
    if primary["confirmed"] != (sign["p"] < .05 and mean < 0):
        raise ValueError("confirmation decision disagrees with frozen rule")
    if primary["interval_reading"] != ("no detected difference" if ci[0] <= 0 <= ci[1] else "interval excludes zero"):
        raise ValueError("confirmation interval reading disagrees with bounds")
    bootstrap = record["bootstrap"]
    invalid = bootstrap["invalid"]
    integer(invalid)
    if (bootstrap["replicates"] != 10000 or bootstrap["seed"] != 14620260925 or
            bootstrap["template_uncertainty_included"] is not True or
            bootstrap["pair_selection_uncertainty_included"] is not False or invalid > 10000):
        raise ValueError("confirmation bootstrap differs from frozen procedure")
    secondary = record["secondaries"]
    for value in (secondary["paired_t"]["statistic"], secondary["paired_t"]["p_two_sided"],
                  secondary["cohen_d_paired"], secondary["pooled_pilot_plus_confirmation"]["mean"]):
        number(value)
    pooled = secondary["pooled_pilot_plus_confirmation"]
    finite_list(pooled["per_seed"], 50, "pooled seeds")
    if pooled["n"] != 50 or pooled["decision"] is not False:
        raise ValueError("pooled result is descriptive only")
    if fixture is None:
        if len(record["audit"]["seeds"]) != 40 or record["audit"]["seeds"] != list(range(301, 341)):
            raise ValueError("confirmation audit must cover seeds 301--340")
        hash_map(record["calibration_sha256"], "calibration_sha256", allow_empty=False)
        hash_map(record["pilot_sha256"], "pilot_sha256", allow_empty=False)
        if record["primary_window_s"] != [8, 10]:
            raise ValueError("confirmation primary window differs")
    return fixture == "synthetic"


def render(record: dict, confirmation: dict, template: str, bindings: dict) -> str:
    pilot_synthetic = validate_record(record)
    confirm_synthetic = validate_confirmation(confirmation)
    synthetic = pilot_synthetic or confirm_synthetic
    slots = set(TOKEN.findall(template))
    if slots != set(bindings):
        raise ValueError(f"template/bindings differ: {sorted(slots ^ set(bindings))}")
    if template.count(STATUS) != 1:
        raise ValueError("template must retain the draft status marker")
    values = {}
    for name, binding in bindings.items():
        try:
            source = confirmation if binding.get("record") == "confirmation" else record
            values[name] = formatted(resolve(source, binding["pointer"]), binding["format"])
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ValueError(f"{name} ({binding['pointer']}): {exc}") from exc
    if record["bootstrap"]["invalid"] > record["bootstrap"]["replicates"]:
        raise ValueError("invalid bootstrap count exceeds requested resamples")
    label = ("SYNTHETIC FIXTURE --- MADE-UP NUMBERS; NOT EXPERIMENTAL RESULTS"
             if synthetic else
             "RESULTS INSERTED --- HUMAN AUTHOR APPROVAL PENDING; NOT FOR SUBMISSION")
    output = TOKEN.sub(lambda m: values[m[1]], template)
    return output.replace(STATUS, r"\newcommand{\paperstatus}{" + label + "}")


def fill(record_path: Path, confirmation_path: Path, output_path: Path) -> None:
    protected = (record_path.resolve(), confirmation_path.resolve(), TEMPLATE.resolve(), BINDINGS.resolve())
    if output_path.resolve() in protected:
        raise ValueError("output must not overwrite the record or paper sources")
    record_bytes = record_path.read_bytes()
    output = render(load_json(record_path), load_json(confirmation_path), TEMPLATE.read_text(), load_json(BINDINGS))
    provenance = ("% Pilot JSON SHA-256: " + hashlib.sha256(record_bytes).hexdigest() +
                  "\n% Confirmation JSON SHA-256: " + hashlib.sha256(confirmation_path.read_bytes()).hexdigest() + "\n")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(provenance + output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path)
    parser.add_argument("confirmation", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        fill(args.record, args.confirmation, args.out)
    except (OSError, KeyError, TypeError, ValueError) as exc:
        parser.exit(2, f"Cannot fill results: {exc}\n")
    print(args.out)


if __name__ == "__main__":
    main()
