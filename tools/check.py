"""One command, no installs/network/output binaries. Missing real input is SKIPPED."""
import argparse,os,sys,unittest
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--game-exe',type=Path);args=p.parse_args()
if args.game_exe:os.environ['LD2_TEST_EXE']=str(args.game_exe.resolve(strict=True))
root=Path(__file__).resolve().parents[1]
result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover(str(root/'tests')))
sys.exit(not result.wasSuccessful())
