"""Runs research/m061 unit tests from tools/check.py. Licensed-input tests skip unless LD2_TEST_EXE / LD2_M045_EXE are set."""
import sys
import unittest
from pathlib import Path

M061 = Path(__file__).resolve().parents[1] / 'research' / 'm061'


def load_tests(loader, standard_tests, pattern):
    sys.path.insert(0, str(M061))
    suite = unittest.TestSuite()
    suite.addTests(loader.discover(str(M061), pattern='test_m061.py', top_level_dir=str(M061)))
    return suite
