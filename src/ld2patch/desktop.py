"""Dispatch GUI only on an explicit --gui or a no-argument interactive launch."""
import sys
from .generator import main as generate_main


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args == [] or args == ['--gui']:
        from .ui import launch
        launch()
        return 0
    if args == ['--help']:
        print('LD2 繁中離線產生器：--gui 開啟操作畫面；無參數亦開啟畫面。')
        print('正式安裝尚未開放。下列指令只讀取來源並產生新檔案。')
    return generate_main(args)
