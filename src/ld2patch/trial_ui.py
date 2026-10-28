"""Optional candidate Tk view; importing does not create a window or query host."""
import threading
from .trial_entry import make_trial_controller,policy
from .profiles import PROFILE_IDS,DEFAULT_TRIAL_PROFILE


def launch():
    import tkinter as tk
    from tkinter import ttk,filedialog,messagebox
    c=make_trial_controller()
    w=tk.Tk();w.title('LD2 繁中副本驗收候選版');w.geometry('920x720')
    frame=ttk.Frame(w,padding=16);frame.pack(fill='both',expand=True)
    ttk.Label(frame,text='檢查來源 → 確認新副本 → 安裝與還原',font=('',16)).pack(anchor='w')
    ttk.Label(frame,text='只操作本次指定測試範圍；不修改正式遊戲，不啟動遊戲。').pack(anchor='w',pady=5)
    row=ttk.Frame(frame);row.pack(fill='x',pady=8)
    profile_box=ttk.Combobox(frame,state='readonly',values=PROFILE_IDS)
    profile_box.set(DEFAULT_TRIAL_PROFILE);profile_box.pack(fill='x')
    candidates=ttk.Combobox(frame,state='readonly');candidates.pack(fill='x')
    details=tk.Text(frame,wrap='word',state='disabled',height=23)
    details.pack(fill='both',expand=True,pady=10)
    actions=ttk.Frame(frame);actions.pack(fill='x')
    status={'choose':'請選擇來源','ready':'來源已檢查','confirm_install':'請確認新副本安裝',
        'confirm_restore':'請確認還原','busy':'處理中，請勿關閉','installed':'副本安裝完成',
        'restored':'副本已還原','failed':'操作未完成，已保留檔案'}
    running={'value':False}
    issues={'unsupported_hash_or_version':'來源版本或雜湊不支援，不能安裝。',
            'game_running':'偵測到遊戲執行中，請先正常結束。',
            'process_state_unknown':'無法確認程序狀態，操作已拒絕。',
            'selection_required':'請明確選擇一個來源。',
            'already_patched':'來源已是已知修改版，請選原版。'}

    def render():
        v=c.view();paths=[p['install_dir'] for p in v['candidates']]
        old=candidates.get();candidates['values']=paths
        if old not in paths:candidates.set(paths[0] if len(paths)==1 else '')
        lines=[status[v['stage']],v['notice'],v['recovery_notice'],'',
               '允許建立副本的根目錄：'+policy()['parent']]
        active=v['result'].get('profile',v['profile']) if v['result'] else v['profile']
        lines+=['候選 profile：'+active['id']+' / '+active['recipe_id'],
                '翻譯位置：'+str(active['text_locations'])+'；字型位置：'+str(active['font_locations']),
                '預期輸出 SHA-256：'+active['expected_output_sha256'],
                'm039 動態文字與 m040 版面候選均未啟用。']
        if active['id']=='m045':
            lines+=['m045 僅初始 F1 提示經畫面確認、手動檔案選單依使用者回報通過；完整遊戲及存讀檔尚未驗收。']
        if v['preview']:
            p=v['preview'];lines+=['來源：'+p['install_dir'],'版本：'+str(p['file_version']),
                                  '來源 SHA-256：'+p['source_sha256']]
        if v['trial_plan']:
            p=v['trial_plan'];lines+=['','將建立的新副本：'+p['target'],
                '獨立復原資料：'+p['recovery_store'],
                '按「確認執行」後才建立檔案。原版與正式存檔保留。']
        if v['workspace']:lines+=['','驗收工作區：'+v['workspace']]
        if v['stage']=='confirm_restore':
            lines+=['將還原此工作區內的副本；若檔案已被其他程式修改，會拒絕覆寫。']
        if v['issue']:lines+=['',issues.get(v['issue'],'檢查結果：'+v['issue'])]
        if v['stopped']:lines+=['存取遭拒，本次操作已停止，不會改路徑或權限重試。']
        lines+=['','限制：兩次改名不是單一步驟的原子替換，未驗證斷電安全。',
                '安裝工具 GUI 尚未目視驗收；遊戲僅具上述有限證據，工具不會自動啟動遊戲。']
        details.configure(state='normal');details.delete('1.0','end')
        details.insert('end','\n'.join(lines));details.configure(state='disabled')
        usable=not v['busy'] and not v['stopped'] and not running['value']
        for b in (manual_button,inspect_button,recovery_button,back_button):
            b.configure(state='normal' if usable else 'disabled')
        trial_button.configure(state='normal' if v['trial_enabled'] else 'disabled')
        confirm_button.configure(state='normal' if v['confirm_enabled'] and not running['value'] else 'disabled')
        candidates.configure(state='readonly' if usable else 'disabled')
        profile_box.configure(state='readonly' if usable and not v['confirm_enabled'] else 'disabled')

    def guarded(action):
        if running['value']:return
        try:action()
        except Exception as e:messagebox.showerror('操作未完成',str(e),parent=w)
        render()
    def select_profile():
        nonlocal c
        if c.view()['busy'] or c.view()['confirm_enabled']:return
        c=make_trial_controller(profile_box.get())
    profile_box.bind('<<ComboboxSelected>>',lambda e:guarded(select_profile))
    def manual():
        folder=filedialog.askdirectory(title='選取原版 Ld95.exe 所在資料夾',parent=w)
        if folder:c.manual(folder)
    def recover():
        folder=filedialog.askdirectory(title='選取本候選版建立的 ld2-trial 工作區',parent=w,
                                        initialdir=policy()['parent'])
        if folder:c.request_restore(folder)
    def complete(error):
        running['value']=False
        if error:messagebox.showerror('操作未完成',error,parent=w)
        render()
    def confirm():
        if running['value']:return
        running['value']=True
        # Tk is touched only by the UI thread. State machine rejects double submit.
        def work():
            error=None
            try:c.confirm()
            except Exception as e:error=str(e)
            w.after(0,lambda:complete(error))
        render()
        threading.Thread(target=work,daemon=False).start()
        w.after(25,render)
    def close():
        if running['value'] or c.view()['busy']:
            messagebox.showinfo('處理中','請等待本次操作結束後再關閉。',parent=w)
        else:w.destroy()

    ttk.Button(row,text='Steam 偵測（本機尚未開放驗證）',state='disabled').pack(side='left')
    manual_button=ttk.Button(row,text='選擇原版資料夾',command=lambda:guarded(manual))
    manual_button.pack(side='left',padx=8)
    inspect_button=ttk.Button(row,text='檢查選取項目',command=lambda:guarded(lambda:c.inspect(candidates.get())))
    inspect_button.pack(side='left')
    trial_button=ttk.Button(actions,text='準備新副本安裝',command=lambda:guarded(c.request_install))
    trial_button.pack(side='left')
    confirm_button=ttk.Button(actions,text='確認執行',state='disabled',command=confirm)
    confirm_button.pack(side='left',padx=8)
    back_button=ttk.Button(actions,text='取消／返回',command=lambda:guarded(c.cancel));back_button.pack(side='left')
    recovery_button=ttk.Button(actions,text='開啟工作區並還原',command=lambda:guarded(recover))
    recovery_button.pack(side='left',padx=8)
    ttk.Button(actions,text='正式目錄安裝（停用）',state='disabled').pack(side='left')
    ttk.Button(actions,text='結束',command=close).pack(side='right')
    candidates.bind('<<ComboboxSelected>>',lambda e:guarded(lambda:c.inspect(candidates.get())))
    w.protocol('WM_DELETE_WINDOW',close);render();w.mainloop()

