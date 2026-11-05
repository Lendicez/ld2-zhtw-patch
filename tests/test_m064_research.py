"""Runs research/m064 unit tests (rdata_ansi lab tool; synthetic bytes only) from tools/check.py."""
import sys
import unittest
from pathlib import Path

M064 = Path(__file__).resolve().parents[1] / 'research' / 'm064'


def load_tests(loader, standard_tests, pattern):
    sys.path.insert(0, str(M064))
    suite = unittest.TestSuite()
    suite.addTests(loader.discover(str(M064), pattern='test_rdata_ansi.py', top_level_dir=str(M064)))
    suite.addTests(loader.discover(str(M064), pattern='test_bmh.py', top_level_dir=str(M064)))
    suite.addTests(loader.discover(str(M064), pattern='test_catalog_patch.py', top_level_dir=str(M064)))
    suite.addTests(loader.discover(str(M064), pattern='test_charset_patch.py', top_level_dir=str(M064)))
    suite.addTests(loader.discover(str(M064), pattern='test_list_reroute.py', top_level_dir=str(M064)))
    suite.addTests(loader.discover(str(M064), pattern='test_tab_title_patch.py', top_level_dir=str(M064)))
    return suite
