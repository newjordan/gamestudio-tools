"""Seeded fast fuzz subset: every catalogued reader tool gets empty / truncated /
bit-flipped / random-byte / fully-random inputs derived from tiny generated seeds
(no samples/ dependency). Tools must exit 0, 1 or 2 with no Python traceback.
A fully-random input (no leftover structure from the seed) must exit 1 or 2.
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fuzz.harness import fuzz, format_summary

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def test_fuzz_fast_subset_is_clean():
    report = fuzz(root=ROOT, seed=1, fast=True, timeout=2.0, samples=False)
    # persist so a failure is easy to inspect
    dest = os.path.join(ROOT, "tests", "fuzz", "reports", "fast-latest.json")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    json.dump(report, open(dest, "w"), indent=2)
    assert report["cases"] > 100, "fast subset should cover the catalog"
    assert report["crashes"] == 0, format_summary(report)


def test_fuzz_fully_random_input_is_rejected():
    """Every reader tool must exit 1 or 2 on a fully random-byte input (not 0)."""
    report = fuzz(root=ROOT, seed=1, fast=True, timeout=2.0, samples=False,
                  mutations=("fully-random",))
    dest = os.path.join(ROOT, "tests", "fuzz", "reports", "fast-fully-random-latest.json")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    json.dump(report, open(dest, "w"), indent=2)
    assert report["cases"] > 100, "fully-random subset should cover the catalog"
    garbage = report["by_class"].get("accepted-garbage", 0)
    assert garbage == 0, "reader tools accepted fully-random input:\n%s" % format_summary(report)
    assert report["crashes"] == 0, format_summary(report)


# Failures that still reach cli_error as a raw Exception (not GstInputError).
# Validated input errors and SystemExit usage messages do not count. Keep this
# tight: a regression that re-opens a decoder without going through lib/gst_read
# should trip the suite.
GENERIC_HIT_THRESHOLD = 5


def test_fuzz_generic_wrapper_hits_under_threshold():
    report = fuzz(root=ROOT, seed=1, fast=True, timeout=2.0, samples=False, debug=False)
    dest = os.path.join(ROOT, "tests", "fuzz", "reports", "fast-generic-latest.json")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    json.dump(report, open(dest, "w"), indent=2)
    hits = report.get("generic_hits", 0)
    assert hits <= GENERIC_HIT_THRESHOLD, (
        "generic-wrapper hits %d exceed threshold %d\n%s"
        % (hits, GENERIC_HIT_THRESHOLD, format_summary(report))
    )
