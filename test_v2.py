"""Test suite for EAP v2 parser."""

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from eap.parser import EthiopianAddressParser


def load_test_addresses(filepath: str) -> list[tuple[str, str, str]]:
    """Load test addresses from file. Format: address | expected_subcity | expected_landmark"""
    tests = []
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 3:
                tests.append((parts[0], parts[1], parts[2]))
    return tests


def run_test_category(parser, filepath: str, category: str) -> dict:
    """Run tests for a category and return stats."""
    tests = load_test_addresses(filepath)
    if not tests:
        print(f"  No tests found in {filepath}")
        return {}

    subcity_correct = 0
    landmark_correct = 0
    total_confidence = 0.0
    results = []

    for address, expected_subcity, expected_landmark in tests:
        result = parser.parse(address)

        # Check subcity
        sc_match = False
        if result.subcity and expected_subcity.lower() != "unknown":
            sc_match = expected_subcity.lower() in result.subcity.lower()
        elif expected_subcity.lower() == "unknown" and not result.subcity:
            sc_match = True

        # Check landmark
        lm_match = False
        if expected_landmark.lower() == "unknown":
            lm_match = True  # No expectation
        elif result.landmark_name:
            lm_match = expected_landmark.lower() in result.landmark_name.lower()

        if sc_match:
            subcity_correct += 1
        if lm_match:
            landmark_correct += 1
        total_confidence += result.confidence

        results.append({
            "address": address,
            "expected_subcity": expected_subcity,
            "got_subcity": result.subcity or "(none)",
            "subcity_ok": sc_match,
            "expected_landmark": expected_landmark,
            "got_landmark": result.landmark_name or "(none)",
            "landmark_ok": lm_match,
            "confidence": result.confidence,
            "method": result.landmark_match_method,
        })

    total = len(tests)
    stats = {
        "category": category,
        "total": total,
        "subcity_pct": round(100 * subcity_correct / total, 1),
        "landmark_pct": round(100 * landmark_correct / total, 1),
        "avg_confidence": round(total_confidence / total, 1),
    }

    # Print results
    print(f"\n{'='*60}")
    print(f"  {category}: {total} addresses")
    print(f"{'='*60}")

    for r in results:
        sc_icon = "✓" if r["subcity_ok"] else "✗"
        lm_icon = "✓" if r["landmark_ok"] else "✗"
        print(f"  {r['address'][:50]:<50}")
        print(f"    Subcity: {sc_icon} expected={r['expected_subcity']:<15} got={r['got_subcity']}")
        print(f"    Landmark: {lm_icon} expected={r['expected_landmark']:<15} got={r['got_landmark']} ({r['method']}, {r['confidence']:.0f}%)")

    print(f"\n  RESULTS: Subcity={stats['subcity_pct']}% | Landmark={stats['landmark_pct']}% | Confidence={stats['avg_confidence']}%")
    return stats


def main():
    print("EAP v2 — Ethiopian Address Parser Test Suite")
    print("=" * 60)

    # Initialize parser (rule-based only for now)
    parser = EthiopianAddressParser(
        data_dir=".",
        use_transformer_ner=False,  # Start with rules, enable ML later
        use_semantic_search=False,
    )
    parser.load()

    # Run tests per category
    test_files = {
        "English Only": "tests/addresses_english_only.txt",
        "Transliterated Amharic": "tests/addresses_transliterated.txt",
        "Mixed (Amharic + English)": "tests/addresses_mixed.txt",
        "Pure Amharic": "tests/addresses_amharic_only.txt",
    }

    all_stats = []
    for category, filepath in test_files.items():
        if Path(filepath).exists():
            stats = run_test_category(parser, filepath, category)
            if stats:
                all_stats.append(stats)

    # Summary
    if all_stats:
        print(f"\n{'='*60}")
        print("  SUMMARY")
        print(f"{'='*60}")
        print(f"  {'Category':<30} {'Subcity':>8} {'Landmark':>9} {'Confidence':>11}")
        print(f"  {'-'*30} {'-'*8} {'-'*9} {'-'*11}")
        for s in all_stats:
            print(f"  {s['category']:<30} {s['subcity_pct']:>7.1f}% {s['landmark_pct']:>8.1f}% {s['avg_confidence']:>10.1f}%")

        # Overall
        total_tests = sum(s["total"] for s in all_stats)
        avg_sc = sum(s["subcity_pct"] * s["total"] for s in all_stats) / total_tests
        avg_lm = sum(s["landmark_pct"] * s["total"] for s in all_stats) / total_tests
        avg_conf = sum(s["avg_confidence"] * s["total"] for s in all_stats) / total_tests
        print(f"  {'OVERALL':<30} {avg_sc:>7.1f}% {avg_lm:>8.1f}% {avg_conf:>10.1f}%")


if __name__ == "__main__":
    main()
