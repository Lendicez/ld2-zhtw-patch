/* m016 research source: compiled previously; NOT integrated into LD95.
   Historical execution was security-blocked; do not execute/repackage to bypass that block.
   Only own modal UI and own resource. No injection, game memory access, or locale changes.
   Build as native x86. The caller must keep resourceModule loaded until return. */
#define UNICODE
#define _UNICODE
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#if !defined(_M_IX86)
#error This prototype requires the x86 target
#endif


#include <wchar.h>
typedef struct Audit {
 DWORD size,initCount,unicodeWindows,ownerDisabled,destroyCount,ncDestroyCount;
 DWORD textUnits,missingGlyphs,bodyWidth,bodyHeight,neededWidth,neededHeight;
 DWORD cp932Loss,cp950Loss,commandId,focusId,active;
 WCHAR font[64];
} Audit;
static Audit audit;
static UINT testCase;
static BOOL active;
static const WCHAR *testBodies[]={L"要儲存目前的冒險進度嗎？",L"冒険の記録：はい／いいえ",L"記錄檔：はい／いいえ／123",L"較長譯文：冒險記錄檔的儲存測試\n第二行：錄、檔、はい、12345"};
__declspec(dllexport) BOOL WINAPI LD2M016SetCase(UINT n) {
 if(active||n>=4)return FALSE;testCase=n;ZeroMemory(&audit,sizeof(audit));audit.size=sizeof(audit);return TRUE;
}
__declspec(dllexport) BOOL WINAPI LD2M016GetAudit(Audit *out,DWORD bytes) {
 if(!out||bytes!=sizeof(audit))return FALSE;*out=audit;out->active=active;return TRUE;
}
static void AuditInit(HWND h,const WCHAR *text) {
 HWND child=GetDlgItem(h,65535),owner=GetWindow(h,GW_OWNER);HDC dc;HFONT font;HGDIOBJ old=NULL;RECT r,needed;WORD glyphs[128];int i,n=(int)wcslen(text);BOOL used;char buf[1024];
 if(!child)child=GetDlgItem(h,-1);
 audit.initCount++;audit.unicodeWindows=(DWORD)IsWindowUnicode(h)+(DWORD)IsWindowUnicode(child)+(DWORD)IsWindowUnicode(GetDlgItem(h,IDOK))+(DWORD)IsWindowUnicode(GetDlgItem(h,IDNO))+(DWORD)IsWindowUnicode(GetDlgItem(h,IDCANCEL));
 audit.ownerDisabled=owner&&!IsWindowEnabled(owner);audit.textUnits=(DWORD)n;
 GetClientRect(child,&r);audit.bodyWidth=(DWORD)(r.right-r.left);audit.bodyHeight=(DWORD)(r.bottom-r.top);
 dc=GetDC(child);if(!dc)return;font=(HFONT)SendMessageW(child,WM_GETFONT,0,0);if(font)old=SelectObject(dc,font);
 GetTextFaceW(dc,64,audit.font);needed=r;DrawTextW(dc,text,n,&needed,DT_CALCRECT|DT_WORDBREAK|DT_NOPREFIX);
 audit.neededWidth=(DWORD)(needed.right-needed.left);audit.neededHeight=(DWORD)(needed.bottom-needed.top);
 if(n<128 && GetGlyphIndicesW(dc,text,n,glyphs,GGI_MARK_NONEXISTING_GLYPHS)!=GDI_ERROR){for(i=0;i<n;i++)if(text[i]>=32&&glyphs[i]==0xffff)audit.missingGlyphs++;}else audit.missingGlyphs=0xffffffff;
 if(old)SelectObject(dc,old);ReleaseDC(child,dc);
 used=FALSE;if(WideCharToMultiByte(932,WC_NO_BEST_FIT_CHARS,text,-1,buf,sizeof(buf),NULL,&used)>0)audit.cp932Loss=used;
 used=FALSE;if(WideCharToMultiByte(950,WC_NO_BEST_FIT_CHARS,text,-1,buf,sizeof(buf),NULL,&used)>0)audit.cp950Loss=used;
}

typedef struct DialogState {
    int choice; /* game semantics: 1=yes, 0=no, -1=cancel */
    BOOL initialized;
    BOOL completed;
    DWORD error;
} DialogState;

static const WCHAR title[] = L"冒險記錄檔儲存確認";
static const WCHAR *body;
static const WCHAR yesText[] = L"是(&Y)";
static const WCHAR noText[] = L"否(&N)";
static const WCHAR cancelText[] = L"取消(&C)";

static BOOL SetAndCheck(HWND h, const WCHAR *text) {
    WCHAR readback[128];
    if (!h || !IsWindowUnicode(h) || !SetWindowTextW(h,text)) return FALSE;
    if (GetWindowTextLengthW(h) >= (int)(sizeof(readback)/sizeof(readback[0]))) return FALSE;
    if (!GetWindowTextW(h,readback,(int)(sizeof(readback)/sizeof(readback[0])))) return FALSE;
    return lstrcmpW(readback,text)==0;
}
static INT_PTR CALLBACK ConfirmProc(HWND h,UINT msg,WPARAM w,LPARAM l) {
    DialogState *s=(DialogState*)GetWindowLongPtrW(h,DWLP_USER);
    if (msg==WM_DESTROY) audit.destroyCount++;
    if (msg==WM_NCDESTROY) audit.ncDestroyCount++;
    if (msg==WM_INITDIALOG) {
        HWND bodyWindow;
        s=(DialogState*)l;
        if (!s) {EndDialog(h,0);return TRUE;}
        SetLastError(0);
        if (!SetWindowLongPtrW(h,DWLP_USER,(LONG_PTR)s) && GetLastError()) {
            s->error=GetLastError();EndDialog(h,0);return TRUE;
        }
        bodyWindow=GetDlgItem(h,65535);
        if (!bodyWindow) bodyWindow=GetDlgItem(h,-1);
        if (!SetAndCheck(h,title) || !SetAndCheck(GetDlgItem(h,IDOK),yesText) ||
            !SetAndCheck(GetDlgItem(h,IDNO),noText) || !SetAndCheck(GetDlgItem(h,IDCANCEL),cancelText) ||
            !SetAndCheck(bodyWindow,body)) {
            s->error=ERROR_INVALID_DATA;EndDialog(h,0);return TRUE;
        }
        AuditInit(h,body);
        s->initialized=TRUE;
        return TRUE; /* dialog manager retains resource default focus */
    }
    if (!s) return FALSE;
    if (msg==WM_COMMAND && HIWORD(w)==BN_CLICKED) {
        int id=LOWORD(w);
        audit.commandId=(DWORD)id;audit.focusId=(DWORD)GetDlgCtrlID(GetFocus());
        if (id==IDOK || id==IDNO || id==IDCANCEL) {
            s->choice=id==IDOK?1:(id==IDNO?0:-1);
            s->completed=TRUE;
            EndDialog(h,id==IDOK?IDOK:IDCANCEL);
            return TRUE;
        }
    }
    if (msg==WM_CLOSE) {
        audit.commandId=0xf060;audit.focusId=(DWORD)GetDlgCtrlID(GetFocus());
        s->choice=-1;s->completed=TRUE;EndDialog(h,IDCANCEL);return TRUE;
    }
    return FALSE;
}

/* Boolean success is separate from choice, so API failure cannot become Yes/No.
   This is stdcall, not a replacement for the game's ECX/thiscall DoModal. */
__declspec(dllexport) BOOL WINAPI LD2Confirm116W(HINSTANCE resourceModule,HWND owner,int *choice,DWORD *error) {
    DialogState state={-1,FALSE,FALSE,0};
    HRSRC resource; HGLOBAL loaded; const DLGTEMPLATE *tpl; DWORD bytes; INT_PTR modal;
    if (!choice || !error) {SetLastError(ERROR_INVALID_PARAMETER);return FALSE;}
    *choice=-1;*error=0;
    if(active){*error=ERROR_BUSY;return FALSE;}
    body=testBodies[testCase];
    if (!resourceModule || (owner && !IsWindow(owner))) {*error=ERROR_INVALID_PARAMETER;return FALSE;}
    resource=FindResourceW(resourceModule,MAKEINTRESOURCEW(116),RT_RCDATA);
    if (!resource) {*error=GetLastError();return FALSE;}
    bytes=SizeofResource(resourceModule,resource);
    loaded=LoadResource(resourceModule,resource);
    tpl=loaded?(const DLGTEMPLATE*)LockResource(loaded):NULL;
    if (!tpl || bytes<sizeof(DLGTEMPLATE) || ((ULONG_PTR)tpl & 3)) {*error=ERROR_INVALID_DATA;return FALSE;}
    SetLastError(0);
    active=TRUE;
    modal=DialogBoxIndirectParamW(resourceModule,tpl,owner,ConfirmProc,(LPARAM)&state);
    active=FALSE;
    if (!state.initialized || !state.completed || (modal!=IDOK && modal!=IDCANCEL)) {
        *error=state.error?state.error:GetLastError();
        if (!*error) *error=ERROR_INVALID_DATA;
        return FALSE;
    }
    *choice=state.choice;
    return TRUE;
}
#ifdef LD2_STANDALONE
int WINAPI wWinMain(HINSTANCE module,HINSTANCE previous,LPWSTR commandLine,int show) {
    int choice=-1;DWORD error=0;
    (void)previous;(void)commandLine;(void)show;
    if (!LD2Confirm116W(module,NULL,&choice,&error)) return 100;
    return choice==1?11:(choice==0?10:12);
}
#endif