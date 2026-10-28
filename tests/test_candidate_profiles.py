"""Profile pinning and headless selection/recovery contracts; no GUI."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from ld2patch.profiles import (PROFILE_IDS, DEFAULT_TRIAL_PROFILE, PINS, profile_info,
    copy_recipe, profile_for_version, load_bundle, preview_versions)
from ld2patch.disposable import REVIEWED, build_reviewed, validate_receipt
from ld2patch.trial_backend import TrialBackend
from ld2patch.trial_store import PURPOSE
from ld2patch.windows_fixture import FixtureRefusal
from ld2patch.windows_capture import encode,digest
from ld2patch.planner import _versions


class CandidateProfiles(unittest.TestCase):
    def test_six_profiles_exact_counts_and_unique_versions(self):
        self.assertEqual(DEFAULT_TRIAL_PROFILE,'m045')
        self.assertEqual([profile_info(p)['text_locations'] for p in PROFILE_IDS],
                         [239,271,295,418,552,554])
        self.assertEqual(copy_recipe('m020'),REVIEWED)
        self.assertEqual(len({copy_recipe(p).version for p in PROFILE_IDS}),6)
        for p in PROFILE_IDS:
            info=profile_info(p)
            self.assertFalse(info['production_can_apply'])
            self.assertFalse(info['dynamic_formatter_enabled'])
            self.assertFalse(info['deadline_layout_enabled'])
            self.assertEqual(profile_for_version(info['version_id']),p)
            copy_recipe(p).validate()

    def test_m045_limited_observation_does_not_enable_full_runtime_or_install(self):
        info=profile_info('m045')
        self.assertFalse(info['runtime_tested'])
        self.assertFalse(info['production_can_apply'])
        self.assertEqual(info['runtime_evidence'],{'scope':'partial',
            'idle_f1_prompt':'direct_visual_pass','manual_file_menu':'user_reported_pass',
            'full_game':False,'save_load':False})
        self.assertEqual(copy_recipe('m042').output_size,copy_recipe('m045').output_size)
        self.assertNotEqual(copy_recipe('m042').output_hash,copy_recipe('m045').output_hash)

    def test_unknown_profile_and_version_shapes_are_refused(self):
        for p in (None,[],{},True,'../m042','m039','m040','M042'):
            with self.subTest(value=p),self.assertRaises(ValueError):profile_info(p)
        for v in (None,[],{},True,'unknown','ld95-1.0.3.16-m040'):
            with self.assertRaises(ValueError):profile_for_version(v)

    def test_all_real_bundle_pins_and_preview_projection(self):
        for p in PROFILE_IDS:
            cat,vs,r=load_bundle(p,ROOT/'patches')
            self.assertEqual(hashlib.sha256(cat).hexdigest(),r['catalog_sha256'])
            before=copy.deepcopy(vs)
            view=preview_versions(p,vs)
            checked=_versions(view)
            self.assertEqual(checked[0]['historical_m020_sha256'],copy_recipe(p).output_hash)
            self.assertEqual(vs,before)
            self.assertFalse(checked[0]['release_approved'])

    def fake_bundle(self,mutate):
        temp=tempfile.TemporaryDirectory(prefix='ld2-profile-synthetic-')
        self.addCleanup(temp.cleanup)
        root=Path(temp.name);folder=root/'m042';folder.mkdir()
        cat,vs,r=load_bundle('m042',ROOT/'patches')
        cat,vs,r=mutate(cat,copy.deepcopy(vs),copy.deepcopy(r))
        for name,data in [('catalog.json',cat),('versions.json',json.dumps(vs).encode()),
                          ('recipe.json',json.dumps(r).encode())]:
            (folder/name).write_bytes(data)
        return root

    def test_catalog_tamper_is_not_accepted_by_matching_filename(self):
        root=self.fake_bundle(lambda c,v,r:(c+b' ',v,r))
        with self.assertRaisesRegex(ValueError,'catalog differs'):load_bundle('m042',root)

    def test_recipe_and_output_pins_cannot_be_rebound(self):
        def recipe(c,v,r):r['text_locations']=553;return c,v,r
        def version(c,v,r):v['versions'][0]['expected_output_sha256']='0'*64;return c,v,r
        def source(c,v,r):v['versions'][0]['source_sha256']='1'*64;return c,v,r
        for mutate in (recipe,version,source):
            root=self.fake_bundle(mutate)
            with self.assertRaises(ValueError):load_bundle('m042',root)

    def test_receipt_cannot_cross_profiles_even_when_source_and_size_match(self):
        # All identifiers are synthetic; no original bytes or resources are used.
        for p in PROFILE_IDS:
            recipe=copy_recipe(p)
            ids=[{'volume':1,'file_id':str(i)*32} for i in range(4)]
            r={'schema':1,'version':recipe.version,'leaf':'case-01',
               'source_size':recipe.source_size,'output_size':recipe.output_size,
               'prepared':{'schema':1,'root':ids[0],'original':ids[1],'backup':ids[2],
                   'stage':ids[3],'source_sha256':recipe.source_hash,'output_sha256':recipe.output_hash},
               'metadata':{'attributes':32,'created':1,'written':2,'security_sha256':'a'*64}}
            raw=encode(r)
            self.assertEqual(validate_receipt(raw,digest(raw),recipe),r)
            for other in PROFILE_IDS:
                if other!=p:
                    with self.assertRaises(FixtureRefusal):
                        validate_receipt(raw,digest(raw),copy_recipe(other))

    @unittest.skipUnless(os.name=='nt','Windows local path semantics')
    def test_plan_pins_profile_before_any_source_or_target_access(self):
        policy={'schema':1,'purpose':PURPOSE,'parent':r'C:\OwnedTrialProfiles',
                'identity':{'volume':1,'file_id':'1'*32}}
        b=TrialBackend(policy,profile='m042')
        plan=b.plan(r'C:\OwnedSource\Ld95.exe')
        self.assertEqual(plan['profile']['text_locations'],552)
        for key,value in [('profile',profile_info('m020')),('production_can_apply',True),
                          ('target',r'C:\OwnedSource\Ld95.exe')]:
            bad=copy.deepcopy(plan);bad[key]=value
            with patch('ld2patch.trial_backend.read_source_only',side_effect=AssertionError('no access')):
                with self.assertRaises(FixtureRefusal):b.install(bad)

    def test_factory_default_and_explicit_profile_do_not_query_registry(self):
        from ld2patch.trial_entry import make_trial_controller
        with patch('ld2patch.ui.make_controller') as base,patch('ld2patch.trial_entry.policy',return_value={}),\
             patch('ld2patch.trial_entry.TrialBackend') as backend:
            make_trial_controller()
            base.assert_called_once_with('m045')
            backend.assert_called_once_with({},profile='m045')
            for p in PROFILE_IDS:
                make_trial_controller(p)
                self.assertEqual(base.call_args.args,(p,))

    def test_cli_cancel_and_explicit_profile_are_headless(self):
        import contextlib,io
        from ld2patch.trial_entry import main
        c=Mock();c.cancel.return_value={'stage':'ready','production_can_apply':False}
        with patch('ld2patch.trial_entry.elevated',return_value=False),\
             patch('ld2patch.trial_entry.make_trial_controller',return_value=c) as factory,\
             contextlib.redirect_stdout(io.StringIO()):
            result=main(['preview','--source',str(ROOT/'Ld95.exe'),'--profile','m041','--cancel'])
        self.assertEqual(result,0);factory.assert_called_once_with('m041')
        c.cancel.assert_called_once();c.confirm.assert_not_called()

    @unittest.skipUnless(os.environ.get('LD2_TEST_EXE'),'Licensed source unavailable; pinned builder integration skipped')
    def test_licensed_m042_build_uses_exact_copy_recipe(self):
        path=Path(os.environ['LD2_TEST_EXE']);source=path.read_bytes()
        for profile,count in [('m042',552),('m045',554)]:
            args=load_bundle(profile,ROOT/'patches')
            result=build_reviewed(source,*args,copy_recipe(profile))
            copy_recipe(profile).check(result.output,True)
            self.assertEqual(result.metadata['text_locations'],count)
            # m042 and m045 have the same byte length but different pinned content.
            other='m045' if profile=='m042' else 'm042'
            with self.assertRaises(FixtureRefusal):build_reviewed(source,*args,copy_recipe(other))
        self.assertEqual(path.read_bytes(),source)


if __name__=='__main__':unittest.main()
