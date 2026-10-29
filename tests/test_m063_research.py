"""Runs research/m063 unit tests from tools/check.py. Lab tests skip without licensed inputs; rehearsal/mock tests skip without ziglang (+capstone); m063c C cross-check skips without a host C compiler."""
import sys
import unittest
from pathlib import Path

M063 = Path(__file__).resolve().parents[1] / 'research' / 'm063'


def load_tests(loader, standard_tests, pattern):
    sys.path.insert(0, str(M063))
    suite = unittest.TestSuite()
    for pattern in ('test_m063.py', 'test_catalog_v4.py', 'test_native_v4.py'):
        suite.addTests(loader.discover(str(M063), pattern=pattern, top_level_dir=str(M063)))
    return suite
