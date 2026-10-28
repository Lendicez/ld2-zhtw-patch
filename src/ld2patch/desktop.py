"""Dispatch GUI only on an explicit --gui or a no-argument interactive launch."""
import sys
from .generator import main as generate_main


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == '--trial':
        from .trial_entry import main as trial_main
        return trial_main(args[1:])
    if args == [] or args == ['--gui']:
        from .generator import resource_root
        if (resource_root() / 'trial-policy.json').exists():
            from .trial_ui import launch as trial_launch
            trial_launch()
            return 0
        from .ui import launch
        launch()
        return 0
    if args == ['--help']:
        print('--trial preview/install/inspect/restore: disposable candidate only; --confirm required for writes; --profile m045 (default), m020/m037/m038/m041/m042 available.')
        print('LD2 繁中離線產生器：--gui 開啟操作畫面；無參數亦開啟畫面。')
        print('正式安裝尚未開放。下列指令只讀取來源並產生新檔案。')
    return generate_main(args)
