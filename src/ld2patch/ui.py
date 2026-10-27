"""Optional Tk view. No window or host detection is created at import time."""
import json
from pathlib import Path


def make_controller(profile='m020'):
    from .controller import Controller
    from .generator import elevated, resource_root
    from .patch_engine import build_to_paths, strict_json
    from .windows_readonly import WindowsReadOnlyFS, process_state, query_registry
    if elevated():
        raise ValueError('請以一般權限啟動，勿使用系統管理員身分。')
    root = resource_root()
    from .profiles import load_bundle, preview_versions
    catalog, versions, recipe = load_bundle(profile, root)
    def generate(source, output, metadata):
        return build_to_paths(source, output, metadata, catalog, versions, recipe)
    return Controller(preview_versions(profile, versions), WindowsReadOnlyFS(), query_registry, process_state, generate)


def launch():
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    messages = {
        'registry_access_denied': 'Windows 拒絕讀取 Steam 位置，本次操作已停止。',
        'registry_read_unavailable': '無法讀取完整 Steam 位置。',
        'steam_roots_missing': '未找到 Steam 位置，可明確選擇遊戲資料夾。',
        'process_access_denied': 'Windows 拒絕查詢遊戲程序，本次操作已停止。',
        'process_state_unknown': '無法確認遊戲是否正在執行，暫不能產生檔案。',
        'game_running': '偵測到遊戲正在執行，請先正常結束遊戲。',
        'unsupported_hash_or_version': '來源檔案不是目前支援的版本，將保留原檔。',
        'already_patched': '這個檔案已是已知繁中版本，無需再次產生。',
        'discovery_incomplete': '位置偵測尚未完整，請先確認來源。',
        'file_missing': '候選程式庫沒有這款遊戲的安裝紀錄。',
        'selection_required': '請選擇並檢查一個候選位置。',
    }
    controller = make_controller()  # Still no registry/process queries here.
    window = tk.Tk()
    window.title('LD2 繁中離線產生器')
    window.geometry('860x650')
    frame = ttk.Frame(window, padding=16); frame.pack(fill='both', expand=True)
    ttk.Label(frame, text='選擇遊戲位置，先檢查，再產生新檔案', font=('', 16)).pack(anchor='w')
    ttk.Label(frame, text='Steam AppID 335420；公開產品識別已核實，本機安裝尚待檢查。').pack(anchor='w', pady=6)
    row = ttk.Frame(frame); row.pack(fill='x', pady=8)
    candidates = ttk.Combobox(frame, state='readonly'); candidates.pack(fill='x')
    details = tk.Text(frame, height=19, wrap='word', state='disabled'); details.pack(fill='both', expand=True, pady=10)
    actions = ttk.Frame(frame); actions.pack(fill='x')

    def render():
        view = controller.view()
        paths = [x['install_dir'] for x in view['candidates']]
        old = candidates.get(); candidates['values'] = paths
        if old not in paths:
            candidates.set(paths[0] if len(paths) == 1 else '')
        preview = view['preview']
        lines = [view['notice'], view['risk'], '', '候選位置：' + str(len(paths)),
                 '偵測完整：' + ('是' if view['discovery_complete'] else '否')]
        if preview:
            lines += ['來源：' + ('Steam manifest' if preview['origin'] == 'steam_manifest' else '手動指定（不代表 Steam 安裝）'),
                      '位置：' + preview['install_dir'], '檔案版本：' + str(preview['file_version'] or '無法確認'),
                      '來源 SHA256：' + preview['source_sha256'], '大小：' + str(preview['source_bytes']) + ' bytes',
                      '可產生新檔案：' + ('是' if preview['can_generate'] else '否')]
        if view['issue']:
            lines += ['', messages.get(view['issue'], '檢查未完成；原因：' + view['issue'])]
        if view['stopped']:
            lines += ['存取遭拒，本次操作已停止；不會改用其他路徑或權限重試。']
        lines += ['', '安裝到遊戲目錄：尚未開放', '請先檢查來源，再選擇新輸出位置。']
        details.configure(state='normal'); details.delete('1.0', 'end'); details.insert('end', '\n'.join(lines)); details.configure(state='disabled')
        generate_button.configure(state='normal' if view['generate_enabled'] else 'disabled')
        for button in (detect_button, manual_button, inspect_button):
            button.configure(state='disabled' if view['stopped'] else 'normal')

    def guarded(action):
        try:
            action()
        except (OSError, ValueError) as exc:
            messagebox.showerror('未完成', str(exc), parent=window)
        finally:
            render()

    def manual():
        folder = filedialog.askdirectory(title='選擇包含 Ld95.exe 的資料夾', parent=window)
        if folder:
            controller.manual(folder)

    def inspect():
        if not candidates.get():
            raise ValueError('請先選擇一個候選位置。')
        controller.inspect(candidates.get())

    def generate():
        output = filedialog.asksaveasfilename(title='選擇全新的輸出位置', defaultextension='.exe',
                    initialfile='Ld95-zhtw.exe', confirmoverwrite=False, parent=window)
        if not output:
            return
        metadata = output + '.json'
        if not messagebox.askyesno('確認產生新檔案', '只建立以下兩個新檔案，保留原遊戲：\n\n' + output + '\n' + metadata, parent=window):
            return
        result = controller.generate(Path(output), Path(metadata), confirmed=True)
        messagebox.showinfo('已產生', '新檔案已建立，尚未安裝或啟動遊戲。\nSHA256：' + result['output_sha256'], parent=window)

    detect_button = ttk.Button(row, text='唯讀偵測 Steam', command=lambda: guarded(controller.discover)); detect_button.pack(side='left')
    manual_button = ttk.Button(row, text='手動指定資料夾', command=lambda: guarded(manual)); manual_button.pack(side='left', padx=8)
    inspect_button = ttk.Button(row, text='檢查選取項目', command=lambda: guarded(inspect)); inspect_button.pack(side='left')
    generate_button = ttk.Button(actions, text='產生到新位置…', state='disabled', command=lambda: guarded(generate)); generate_button.pack(side='left')
    ttk.Button(actions, text='安裝（尚未開放）', state='disabled').pack(side='left', padx=8)
    ttk.Button(actions, text='結束', command=window.destroy).pack(side='right')
    def selection_changed(event):
        controller.preview = None
        render()
    candidates.bind('<<ComboboxSelected>>', selection_changed)
    render()
    window.mainloop()
