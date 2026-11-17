"""Run from any directory: python run_tests.py [test_module ...]."""
from pathlib import Path
import os
import sys
import unittest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tests'))
os.chdir(ROOT)

if __name__ == '__main__':
    loader = unittest.defaultTestLoader
    suite = (loader.loadTestsFromNames(sys.argv[1:]) if len(sys.argv) > 1
             else loader.discover(str(ROOT / 'tests'), pattern='test_*.py'))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
