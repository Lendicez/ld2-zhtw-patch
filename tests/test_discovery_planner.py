import copy
from dataclasses import replace
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from ld2patch.discovery import Candidate, Discovery, EvidenceError, child, discover, discover_from_registry_values, manual_candidate, path_key, windows_path
from ld2patch.planner import ProcessEvidence, plan_install
from fake_steam import APP_ID, ORIGINAL, PATCHED, MemoryFS, add_library, example, vdf_string


class Paths(unittest.TestCase):
    def test_unicode_space_absolute_path(self):
        self.assertEqual(windows_path('d:/合成 程式庫/遊戲/'), 'D:\\合成 程式庫\\遊戲')

    def test_unsafe_paths(self):
        for path in ['', 'C:relative', 'relative', r'\\server\share', r'\\?\C:\x', r'C:\x\..\y',
                     r'C:\x\.\y', r'C:\x:stream', 'C:\\x ', 'C:\\x.', r'C:\NUL.txt', r'C:\x\COM1',
                     'C:\\x\x00y', r'C:\x\a?b', r'C:\x\a|b', r'C:\x\\y', 'C:\\COM\u00b9', r'C:\CONIN$', r'C:\CONOUT$']:
            with self.subTest(path=path), self.assertRaises(EvidenceError):
                windows_path(path)

    def test_child_rejects_escape(self):
        for part in ['..', r'D:\Other', r'..\Other']:
            with self.subTest(part=part), self.assertRaises(EvidenceError):
                child(r'C:\Synthetic', part)


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.fs, self.root, self.install, self.config = example()

    def test_multilibrary_and_missing_manifest(self):
        before = self.fs.snapshot(); report = discover([self.root], APP_ID, self.fs)
        self.assertEqual([c.install_dir for c in report.candidates], [self.install])
        self.assertEqual(len(report.examined_libraries), 2)
        self.assertTrue(any(x.code == 'file_missing' for x in report.issues))
        self.assertEqual(before, self.fs.snapshot())
        self.assertTrue(all('USR' not in p for p in self.fs.reads))

    def test_unset_appid_does_not_call_provider_or_fs(self):
        calls=[]
        report=discover_from_registry_values(lambda: calls.append(1), None, self.fs)
        self.assertEqual(report.issues[0].code, 'appid_required');self.assertEqual(calls, []);self.assertEqual(self.fs.probes, [])

    def test_invalid_appids(self):
        for app_id in ['0','01','１２３','../1','4294967296',123]:
            with self.subTest(app_id=app_id):
                report=discover([self.root],app_id,self.fs);self.assertEqual(report.issues[0].code,'invalid_appid')
        self.assertEqual(self.fs.probes, [])

    def test_registry_denial_no_fallback(self):
        def denied():raise PermissionError('synthetic')
        report=discover_from_registry_values(denied,APP_ID,self.fs)
        self.assertEqual(report.issues[0].code,'registry_access_denied');self.assertEqual(self.fs.probes,[])

    def test_registry_generator_denial(self):
        def denied():
            yield self.root
            raise PermissionError('synthetic')
        report=discover_from_registry_values(denied,APP_ID,self.fs)
        self.assertEqual(report.issues[0].code,'registry_access_denied');self.assertEqual(self.fs.probes,[])

    def test_root_dedup_and_legacy_library(self):
        doc='"LibraryFolders" { "1" '+vdf_string(r'D:\合成 程式庫')+' }'
        self.fs.add(child(self.root,'steamapps','libraryfolders.vdf'),doc.encode('utf-8'))
        report=discover([self.root,self.root.lower()],APP_ID,self.fs)
        self.assertEqual(len(report.examined_libraries),2);self.assertEqual(len(report.candidates),1)

    def test_manifest_appid_mismatch(self):
        add_library(self.fs,r'D:\合成 程式庫',app_id='1234567891')
        report=discover([self.root],APP_ID,self.fs)
        self.assertEqual(report.candidates,[]);self.assertIn('manifest_appid_mismatch',[x.code for x in report.issues])

    def test_traversal_manifest(self):
        path=child(r'D:\合成 程式庫','steamapps',f'appmanifest_{APP_ID}.acf')
        self.fs.add(path,f'"AppState" {{"appid" "{APP_ID}" "installdir" "../escape"}}'.encode())
        report=discover([self.root],APP_ID,self.fs)
        self.assertEqual(report.candidates,[]);self.assertIn('invalid_manifest',[x.code for x in report.issues])

    def test_malicious_library_and_budget(self):
        path=child(self.root,'steamapps','libraryfolders.vdf')
        self.fs.add(path,b'"libraryfolders" {"1" "../escape"}')
        report=discover([self.root],APP_ID,self.fs);self.assertIn('unsafe_path',[x.code for x in report.issues])
        report=discover([f'C:\\Synthetic{i}' for i in range(9)],APP_ID,self.fs)
        self.assertEqual(report.issues[0].code,'root_budget')

    def test_permission_denial_stops_branch(self):
        path=child(self.root,'steamapps','libraryfolders.vdf');self.fs.denied.add(path_key(path))
        report=discover([self.root],APP_ID,self.fs)
        self.assertEqual(report.issues[0].code,'access_denied');self.assertEqual(report.examined_libraries,[]);self.assertEqual(self.fs.reads,[])

    def test_expanded_path_budget_returns_issue(self):
        report=discover(['C:\\'+'x'*230],APP_ID,self.fs)
        self.assertFalse(report.complete);self.assertEqual(report.issues[0].code,'unsafe_path')

    def test_missing_library_list_cannot_be_complete(self):
        report=discover([r'C:\Missing Steam'],APP_ID,self.fs)
        self.assertFalse(report.complete);self.assertEqual(report.issues[0].code,'file_missing')

    def test_reparse_and_unknown_ancestor(self):
        for overrides in [{'reparse':True},{'ancestors_verified':False}]:
            with self.subTest(overrides=overrides):
                fs,root,install,_=example();fs.add(install,**overrides)
                report=discover([root],APP_ID,fs)
                self.assertEqual(report.candidates,[]);self.assertIn('reparse_or_unverified_ancestors',[x.code for x in report.issues])

    def test_manual_selection_uses_same_guards(self):
        c=manual_candidate(self.install,APP_ID,self.fs);self.assertEqual(c.origin,'manual')
        with self.assertRaises(EvidenceError):manual_candidate(self.install,None,self.fs)

    def test_changed_vdf_is_not_trusted(self):
        path=child(self.root,'steamapps','libraryfolders.vdf');self.fs.change_after_read.add(path_key(path))
        report=discover([self.root],APP_ID,self.fs);self.assertIn('file_changed',[x.code for x in report.issues])

    def test_oversized_or_nonutf8_vdf(self):
        for content in [b'\xff',b'x'*(2*1024*1024+1)]:
            with self.subTest(length=len(content)):
                fs,root,_,_=example();fs.add(child(root,'steamapps','libraryfolders.vdf'),content)
                report=discover([root],APP_ID,fs)
                self.assertTrue(any(x.code in ('invalid_vdf','file_size_or_change_token_unknown') for x in report.issues))


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.fs,self.root,self.install,self.config=example()
        self.discovery=discover([self.root],APP_ID,self.fs)
        self.clear=ProcessEvidence(True)

    def plan(self,**kwargs):
        return plan_install(self.discovery,self.config,self.fs,kwargs.pop('processes',self.clear),**kwargs)

    def test_ready_preview_has_no_writes_and_only_exe_change(self):
        before=self.fs.snapshot();p=self.plan()
        self.assertEqual(p.status,'ready_for_review');self.assertFalse(p.can_apply);self.assertTrue(p.confirmation_required)
        self.assertEqual([x['path'] for x in p.proposed_changes],[child(self.install,'Ld95.exe')]);self.assertEqual(before,self.fs.snapshot())
        self.assertEqual(p.backup_action,'create_and_verify_before_any_replacement');json.dumps(p.to_dict(),ensure_ascii=False)

    def test_multicandidate_needs_explicit_selection(self):
        fs,root,install,config=example(two=True);c=discover([root],APP_ID,fs)
        p=plan_install(c,config,fs,self.clear);self.assertEqual(p.issues[0].code,'selection_required')
        p=plan_install(c,config,fs,self.clear,selected_install_dir=install);self.assertEqual(p.status,'ready_for_review')
        p=plan_install(c,config,fs,self.clear,selected_install_dir=r'C:\Other');self.assertEqual(p.issues[0].code,'selection_not_a_candidate')

    def test_hash_mismatch_even_matching_version(self):
        self.fs.add(child(self.install,'Ld95.exe'),b'OTHER MOD',file_version='1.2.3.4')
        self.assertEqual(self.plan().issues[0].code,'unsupported_hash')

    def test_file_version_missing(self):
        self.fs.add(child(self.install,'Ld95.exe'),ORIGINAL,file_version=None)
        self.assertEqual(self.plan().issues[0].code,'file_version_unknown_or_mismatch')

    def test_no_installed_candidates(self):
        p=plan_install(Discovery(APP_ID,complete=True),self.config,self.fs,self.clear)
        self.assertEqual(p.issues[0].code,'no_candidates');self.assertFalse(p.can_apply)

    def test_size_allowlist_mismatch(self):
        self.config['versions'][0]['source_size'] += 1
        self.assertEqual(self.plan().issues[0].code,'version_size_mismatch')

    def test_any_running_game_blocks(self):
        for path in [child(self.install,'Ld95.exe'),r'E:\OtherCopy\Ld95.exe']:
            with self.subTest(path=path):self.assertEqual(self.plan(processes=ProcessEvidence(True,(path,))).issues[0].code,'game_running')

    def test_unknown_process_state_blocks(self):
        for evidence in [ProcessEvidence(False),ProcessEvidence(True,unresolved_game_processes=True),ProcessEvidence(True,unresolved_game_processes=None),ProcessEvidence(True,running_game_paths=None)]:
            with self.subTest(evidence=evidence):self.assertEqual(self.plan(processes=evidence).issues[0].code,'process_state_unknown')

    def test_existing_verified_backup_reused(self):
        p=self.plan();self.fs.add(p.backup,ORIGINAL)
        p=self.plan();self.assertEqual(p.status,'ready_for_review');self.assertEqual(p.backup_action,'reuse_verified_backup_without_overwrite')

    def test_backup_conflict(self):
        p=self.plan();self.fs.add(p.backup,b'OTHER BACKUP')
        self.assertEqual(self.plan().issues[0].code,'backup_content_conflict')

    def test_backup_directory_conflict(self):
        self.fs.add(child(self.install,'.ld2-zhtw-backups'),b'OTHER MOD FILE')
        self.assertEqual(self.plan().issues[0].code,'backup_directory_conflict')

    def test_backup_reparse(self):
        p=self.plan();self.fs.add(p.backup,ORIGINAL,reparse=True)
        self.assertEqual(self.plan().issues[0].code,'reparse_or_unverified_ancestors')

    def test_permission_failure_no_fallback_read(self):
        target=child(self.install,'Ld95.exe');self.fs.denied.add(path_key(target));n=len(self.fs.reads)
        self.assertEqual(self.plan().issues[0].code,'access_denied');self.assertEqual(len(self.fs.reads),n)

    def test_file_changes_during_read(self):
        self.fs.change_after_read.add(path_key(child(self.install,'Ld95.exe')))
        self.assertEqual(self.plan().issues[0].code,'file_changed')

    def test_already_patched_is_idempotent_preview(self):
        self.fs.add(child(self.install,'Ld95.exe'),PATCHED)
        p=self.plan();self.assertEqual(p.status,'already_patched');self.assertEqual(p.proposed_changes,[]);self.assertFalse(p.can_apply)

    def test_release_not_approved(self):
        self.config['versions'][0]['release_approved']=False
        p=self.plan();self.assertEqual(p.issues[0].code,'release_not_approved');self.assertEqual(len(p.proposed_changes),1)

    def test_real_configuration_remains_unset_appid(self):
        config=json.loads((ROOT/'patches/versions.json').read_text(encoding='utf-8'))
        p=plan_install(self.discovery,config,self.fs,self.clear);self.assertEqual(p.issues[0].code,'appid_required');self.assertFalse(p.can_apply)

    def test_bad_version_and_ambiguous_hash(self):
        for mutation in [{'id':'../escape'},{'filename':'other.exe'},{'source_size':True},{'historical_m020_sha256':self.config['versions'][0]['source_sha256']}]:
            with self.subTest(mutation=mutation):
                config=copy.deepcopy(self.config);config['versions'][0].update(mutation)
                self.assertEqual(plan_install(self.discovery,config,self.fs,self.clear).status,'blocked')

    def test_candidate_appid_and_canonical_mismatch(self):
        wrong=Discovery(APP_ID,[replace(self.discovery.candidates[0],app_id='2')],complete=True)
        self.assertEqual(plan_install(wrong,self.config,self.fs,self.clear).issues[0].code,'candidate_appid_mismatch')
        self.fs.add(self.install,canonical_path=r'C:\Different')
        self.assertEqual(self.plan().issues[0].code,'canonical_path_mismatch')

    def test_partial_discovery_cannot_auto_select(self):
        fs,root,install,config=example(two=True)
        fs.denied.add(path_key(child(r'D:\合成 程式庫','steamapps',f'appmanifest_{APP_ID}.acf')))
        discovery=discover([root],APP_ID,fs)
        self.assertEqual(len(discovery.candidates),1);self.assertFalse(discovery.complete)
        p=plan_install(discovery,config,fs,self.clear)
        self.assertEqual(p.issues[0].code,'discovery_incomplete')


if __name__=='__main__':unittest.main()
