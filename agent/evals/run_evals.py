#!/usr/bin/env python3
"""Run evaluation suite against the agent /chat endpoint."""

import json
import sys
from typing import Any

import httpx


def load_cases(filename: str = "cases.json") -> list[dict[str, Any]]:
    """Load eval cases from JSON file."""
    with open(filename, "r") as f:
        return json.load(f)


def run_eval_case(case: dict[str, Any], agent_url: str) -> dict[str, Any]:
    """Run a single eval case and return results."""
    case_id = case["id"]
    description = case["description"]

    print(f"\n[{case_id}] {description}")

    # Handle invalid patient_id cases (type validation)
    if not isinstance(case["patient_id"], int):
        # This should fail at the API level (422 validation error)
        try:
            response = httpx.post(
                f"{agent_url}/chat",
                json={"patient_id": case["patient_id"], "message": case["message"]},
                timeout=30.0,
            )
            if response.status_code == 422:
                print(f"  ✅ Expected validation error (422) received")
                return {
                    "case_id": case_id,
                    "passed": True,
                    "reason": "Validation error as expected",
                }
            else:
                print(f"  ❌ Expected 422, got {response.status_code}")
                return {
                    "case_id": case_id,
                    "passed": False,
                    "reason": f"Wrong status code: {response.status_code}",
                }
        except Exception as e:
            print(f"  ❌ Request failed: {str(e)}")
            return {"case_id": case_id, "passed": False, "reason": str(e)}

    # Normal cases
    try:
        response = httpx.post(
            f"{agent_url}/chat",
            json={"patient_id": case["patient_id"], "message": case["message"]},
            timeout=30.0,
        )

        # Check for expected errors
        if case.get("expected_error", False):
            if response.status_code >= 400:
                print(f"  ✅ Expected error received ({response.status_code})")
                return {
                    "case_id": case_id,
                    "passed": True,
                    "reason": f"Expected error: {response.status_code}",
                }
            else:
                print(f"  ❌ Expected error but got 200")
                return {
                    "case_id": case_id,
                    "passed": False,
                    "reason": "Expected error but request succeeded",
                }

        # Check for successful response
        if response.status_code != 200:
            print(f"  ❌ HTTP {response.status_code}: {response.text[:200]}")
            return {
                "case_id": case_id,
                "passed": False,
                "reason": f"HTTP {response.status_code}",
            }

        data = response.json()
        response_text = data.get("response", "")
        citations = data.get("citations", [])

        # Check assertions
        failures = []

        # Check minimum citations
        expected_citations_min = case.get("expected_citations_min", 0)
        if len(citations) < expected_citations_min:
            failures.append(
                f"Expected >= {expected_citations_min} citations, got {len(citations)}"
            )

        # Check expected substrings
        for substring in case.get("expected_substrings", []):
            if substring.lower() not in response_text.lower():
                failures.append(f"Missing expected substring: '{substring}'")

        # Check should_not_contain
        for substring in case.get("should_not_contain", []):
            if substring.lower() in response_text.lower():
                failures.append(f"Contains forbidden substring: '{substring}'")

        if failures:
            print(f"  ❌ FAILED")
            for failure in failures:
                print(f"     - {failure}")
            return {
                "case_id": case_id,
                "passed": False,
                "reason": "; ".join(failures),
            }
        else:
            print(f"  ✅ PASSED ({len(citations)} citations)")
            return {"case_id": case_id, "passed": True, "reason": "All checks passed"}

    except httpx.TimeoutException:
        print(f"  ❌ Request timeout")
        return {"case_id": case_id, "passed": False, "reason": "Timeout"}
    except Exception as e:
        print(f"  ❌ Error: {str(e)}")
        return {"case_id": case_id, "passed": False, "reason": str(e)}


def main():
    """Run all eval cases and print summary."""
    if len(sys.argv) < 2:
        print("Usage: python run_evals.py <agent_url>")
        print("Example: python run_evals.py http://localhost:8000")
        sys.exit(1)

    agent_url = sys.argv[1].rstrip("/")

    print(f"Running evals against: {agent_url}")
    print("=" * 60)

    cases = load_cases()
    results = []

    for case in cases:
        result = run_eval_case(case, agent_url)
        results.append(result)

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    pass_rate = (passed / total * 100) if total > 0 else 0

    print(f"\nTotal: {total} cases")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    print(f"Pass rate: {pass_rate:.1f}%")

    # Print failures
    failures = [r for r in results if not r["passed"]]
    if failures:
        print("\nFailed cases:")
        for failure in failures:
            print(f"  - {failure['case_id']}: {failure['reason']}")

    # Exit with non-zero if any failures
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
