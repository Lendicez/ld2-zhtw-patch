"""Runs research/m062 unit tests from tools/check.py. Licensed-input tests skip unless LD2_TEST_EXE / LD2_M051_CATALOG are set."""
import sys
import unittest
from pathlib import Path

M062 = Path(__file__).resolve().parents[1] / 'research' / 'm062'


def load_tests(loader, standard_tests, pattern):
    sys.path.insert(0, str(M062))
    suite = unittest.TestSuite()
    suite.addTests(loader.discover(str(M062), pattern='test_m062.py', top_level_dir=str(M062)))
    suite.addTests(loader.discover(str(M062), pattern='test_merge_v3.py', top_level_dir=str(M062)))
    suite.addTests(loader.discover(str(M062), pattern='test_name_draw_sites.py', top_level_dir=str(M062)))
    return suite
