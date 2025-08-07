#!/usr/bin/env python3
"""
Zentraler Test-Runner für Python Utils Repository
====================================================

Automatische Erkennung und Ausführung aller Tests im Repository.
Unterstützt sowohl einzelne Test-Dateien als auch Module mit Test-Verzeichnissen.

Verwendung:
  python run_tests.py              # Alle Tests
  python run_tests.py analyzer     # Nur analyzer Tests
  python run_tests.py -v           # Verbose Ausgabe
  python run_tests.py --help       # Hilfe anzeigen
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, NamedTuple


class TestSuite(NamedTuple):
    """Represents a discoverable test suite."""

    name: str
    path: Path
    test_type: str  # 'single_file', 'module_with_tests', 'inline_tests'
    python_path: Path | None = None
    requires_uv: bool = True


class TestRunner:
    """Discovers and runs all tests in the repository."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.test_suites: List[TestSuite] = []

    def discover_test_suites(self) -> List[TestSuite]:
        """Automatically discover all test suites in the repository."""
        test_suites = []

        # 1. Find standalone test files (test_*.py in root)
        for test_file in self.repo_root.glob("test_*.py"):
            test_suites.append(
                TestSuite(
                    name=test_file.stem.replace("test_", ""), path=test_file, test_type="single_file", requires_uv=True
                )
            )

        # 2. Find modules with tests/ directories
        for item in self.repo_root.iterdir():
            if item.is_dir() and item.name not in {".git", "__pycache__", ".pytest_cache", "templates"}:
                tests_dir = item / "tests"
                if tests_dir.exists() and tests_dir.is_dir():
                    # Check if there are actual test files
                    test_files = list(tests_dir.glob("test_*.py"))
                    if test_files:
                        test_suites.append(
                            TestSuite(
                                name=item.name,
                                path=tests_dir,
                                test_type="module_with_tests",
                                python_path=item,
                                requires_uv=True,
                            )
                        )

        self.test_suites = test_suites
        return test_suites

    def run_single_test_suite(self, suite: TestSuite, verbose: bool = False, extra_args: List[str] = None) -> bool:
        """Run a single test suite."""
        extra_args = extra_args or []

        print(f"\n🧪 Running tests for: {suite.name}")
        print(f"   Type: {suite.test_type}")
        print(f"   Path: {suite.path}")

        # Build command
        if suite.requires_uv:
            cmd = ["uv", "run", "pytest"]
        else:
            cmd = ["pytest"]

        # Add path
        cmd.append(str(suite.path))

        # Add verbosity
        if verbose:
            cmd.append("-v")

        # Add extra arguments
        cmd.extend(extra_args)

        # Set environment
        env = os.environ.copy()
        if suite.python_path:
            if "PYTHONPATH" in env:
                env["PYTHONPATH"] = f"{suite.python_path}:{env['PYTHONPATH']}"
            else:
                env["PYTHONPATH"] = str(suite.python_path)

        print(f"   Command: {' '.join(cmd)}")
        if suite.python_path:
            print(f"   PYTHONPATH: {suite.python_path}")

        # Run the tests
        try:
            result = subprocess.run(cmd, cwd=self.repo_root, env=env, capture_output=False)
            success = result.returncode == 0

            if success:
                print(f"✅ {suite.name}: Tests passed")
            else:
                print(f"❌ {suite.name}: Tests failed")

            return success

        except FileNotFoundError as e:
            print(f"❌ {suite.name}: Command not found - {e}")
            return False
        except Exception as e:
            print(f"❌ {suite.name}: Error running tests - {e}")
            return False

    def run_all_tests(self, verbose: bool = False, extra_args: List[str] = None) -> Dict[str, bool]:
        """Run all discovered test suites."""
        if not self.test_suites:
            print("🔍 No test suites discovered!")
            return {}

        print(f"🚀 Running {len(self.test_suites)} test suite(s):")
        for suite in self.test_suites:
            print(f"   - {suite.name} ({suite.test_type})")

        results = {}
        for suite in self.test_suites:
            results[suite.name] = self.run_single_test_suite(suite, verbose, extra_args)

        return results

    def run_specific_test(self, test_name: str, verbose: bool = False, extra_args: List[str] = None) -> bool:
        """Run a specific test suite by name."""
        suite = next((s for s in self.test_suites if s.name == test_name), None)

        if not suite:
            print(f"❌ Test suite '{test_name}' not found!")
            print(f"Available test suites: {', '.join(s.name for s in self.test_suites)}")
            return False

        return self.run_single_test_suite(suite, verbose, extra_args)

    def print_summary(self, results: Dict[str, bool]):
        """Print a summary of test results."""
        if not results:
            return

        total = len(results)
        passed = sum(results.values())
        failed = total - passed

        print(f"\n{'=' * 60}")
        print("📊 TEST SUMMARY")
        print(f"{'=' * 60}")
        print(f"Total test suites: {total}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")

        if failed > 0:
            print("\nFailed test suites:")
            for name, success in results.items():
                if not success:
                    print(f"   - {name}")

        print(f"{'=' * 60}")

        if failed == 0:
            print("🎉 All tests passed!")
        else:
            print(f"⚠️  {failed} test suite(s) failed")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run tests for Python utilities repository",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_tests.py                    # Run all tests
  python run_tests.py analyzer           # Run only analyzer tests
  python run_tests.py -v                 # Run all tests with verbose output
  python run_tests.py analyzer --tb=short # Run analyzer tests with short traceback
        """,
    )

    parser.add_argument(
        "test_suite", nargs="?", help="Specific test suite to run (e.g., 'analyzer', 'git_lineendings')"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--list", action="store_true", help="List all available test suites")

    # Capture any additional pytest arguments
    args, pytest_args = parser.parse_known_args()

    # Setup
    repo_root = Path(__file__).parent
    runner = TestRunner(repo_root)

    # Discover test suites
    print("🔍 Discovering test suites...")
    test_suites = runner.discover_test_suites()

    if not test_suites:
        print("❌ No test suites found!")
        return 1

    # List mode
    if args.list:
        print(f"\n📋 Available test suites ({len(test_suites)}):")
        for suite in test_suites:
            print(f"   {suite.name:<20} ({suite.test_type})")
            print(f"      Path: {suite.path}")
        return 0

    # Run tests
    if args.test_suite:
        # Run specific test suite
        success = runner.run_specific_test(args.test_suite, args.verbose, pytest_args)
        return 0 if success else 1
    else:
        # Run all test suites
        results = runner.run_all_tests(args.verbose, pytest_args)
        runner.print_summary(results)

        # Return appropriate exit code
        failed_count = len([r for r in results.values() if not r])
        return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
