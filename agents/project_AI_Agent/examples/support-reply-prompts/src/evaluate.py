"""Score every prompt version's recorded responses against the test cases.

    python src/evaluate.py                         compare all versions
    python src/evaluate.py --failures v2_role_and_rules   list what one version got wrong

Writes results/scores.csv with one row per version.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

from checks import CHECK_NAMES, check_response

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = ["v1_baseline", "v2_role_and_rules", "v3_few_shot_json"]


def load_cases():
    return {case["id"]: case for case in json.loads((ROOT / "data/test_cases.json").read_text(encoding="utf-8"))}


def score_version(version, cases):
    """Return ({check: passed_count}, [(case_id, failed_checks)])."""
    responses = json.loads((ROOT / f"outputs/{version}.json").read_text(encoding="utf-8"))["responses"]
    totals = {name: 0 for name in CHECK_NAMES}
    failures = []
    for response in responses:
        result = check_response(response["raw"], cases[response["id"]])
        for name, passed in result.items():
            totals[name] += passed
        failed = [name for name, passed in result.items() if not passed]
        if failed:
            failures.append((response["id"], failed))
    return totals, failures


def compare(cases):
    n = len(cases)
    rows = []
    print(f"Prompt comparison - {n} test emails, {len(CHECK_NAMES)} checks each")
    print(f"{'version':<19}" + "".join(f"{name:>12}" for name in CHECK_NAMES) + f"{'overall':>10}")
    for version in VERSIONS:
        totals, _ = score_version(version, cases)
        overall = sum(totals.values()) / (n * len(CHECK_NAMES))
        print(f"{version:<19}" + "".join(f"{f'{totals[c]}/{n}':>12}" for c in CHECK_NAMES) + f"{overall:>10.1%}")
        rows.append({"version": version, **totals, "overall_pct": round(overall * 100, 1)})
    out = ROOT / "results/scores.csv"
    out.parent.mkdir(exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["version", *CHECK_NAMES, "overall_pct"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {out.relative_to(ROOT).as_posix()}")


def show_failures(version, cases):
    _, failures = score_version(version, cases)
    print(f"Failures for {version}: {len(failures)} of {len(cases)} emails")
    for case_id, failed in failures:
        print(f"  {case_id} ({cases[case_id]['expected_category']}): {', '.join(failed)}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--failures", choices=VERSIONS, help="list the failed checks for one version")
    args = parser.parse_args(argv)
    cases = load_cases()
    if args.failures:
        show_failures(args.failures, cases)
    else:
        compare(cases)
    return 0


if __name__ == "__main__":
    sys.exit(main())
