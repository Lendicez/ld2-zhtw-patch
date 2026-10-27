"""Pinned candidate profiles, never runtime paths or permission to install a game."""
from copy import deepcopy
import hashlib
from pathlib import Path
from .disposable import CopyRecipe, SOURCE_HASH, REVIEWED
from .patch_engine import strict_json, build_versions

DEFAULT_TRIAL_PROFILE = 'm042'
PINS = {'m020': {'recipe': {'catalog': 'ui-m020.zh-TW.json', 'catalog_sha256': '86619a3d3dd3db00660100daf899c9278f1af02777e6aa14df8e709fdd89764f', 'engine': 'resource_append_v1', 'font_locations': 15, 'id': 'm020-ui-resource-v1', 'schema_version': 1, 'text_locations': 239, 'version_id': 'ld95-1.0.3.16'}, 'output_hash': 'a15bf7313636a7c19a065b388345f93b46bbce8eb6bf3c9b910a7dc192c3da81', 'output_size': 7102464}, 'm037': {'recipe': {'schema_version': 2, 'id': 'm037-combat-ui-v1', 'engine': 'resource_append_v1', 'version_id': 'ld95-1.0.3.16-m037', 'catalog': 'catalog.json', 'catalog_sha256': '92c116027de8795866ffb91bc39ce3e73d9d3ba7bb1e5bcbf16f1a521b8b47f3', 'text_locations': 271, 'font_locations': 20}, 'output_hash': '1fada3e7081de0797101bd61388cee20f2f2b38d796d9ef3fd892dac82e179d4', 'output_size': 7102464}, 'm038': {'recipe': {'schema_version': 2, 'id': 'm038-travel-party-quest-v1', 'engine': 'resource_append_v1', 'version_id': 'ld95-1.0.3.16-m038', 'catalog': 'catalog.json', 'catalog_sha256': 'a0f4476129c0bbd6b4366ef57b42682a28a88b80293c89b885310a14c0d63e64', 'text_locations': 295, 'font_locations': 24}, 'output_hash': '8730f5731730afcf8a20e245958744d2b227dde4fa260d861eae296001ef65b2', 'output_size': 7106560}, 'm041': {'recipe': {'schema_version': 2, 'id': 'm041-facility-pages-v1', 'engine': 'resource_append_v1', 'version_id': 'ld95-1.0.3.16-m041', 'catalog': 'catalog.json', 'catalog_sha256': '362d7d54879773f39e24b50c7d189388b8c00e58eb2dee0bc705ffe4e8a2dec6', 'text_locations': 418, 'font_locations': 51}, 'output_hash': 'bedee9b18527f1f3a3a264ac175fa968ce24bf41beb6070a82988eeaf6cd5177', 'output_size': 7114752}, 'm042': {'recipe': {'schema_version': 2, 'id': 'm042-static-ui-v1', 'engine': 'resource_append_v1', 'version_id': 'ld95-1.0.3.16-m042', 'catalog': 'catalog.json', 'catalog_sha256': 'b9b4d7d5bcc334d0588fd75db180cedf3eab8266fa54bf951e9eb21fed0d234b', 'text_locations': 552, 'font_locations': 71}, 'output_hash': '9fea1172e92167d435a8ec26baf085ab45a2a56468690bf7bfec1f8ba29dc367', 'output_size': 7118848}}
PROFILE_IDS = tuple(PINS)


def profile_info(profile):
    if not isinstance(profile, str) or profile not in PINS:
        raise ValueError('Unknown candidate profile')
    p = PINS[profile]
    r = p['recipe']
    return {'id': profile, 'recipe_id': r['id'], 'version_id': r['version_id'],
            'text_locations': r['text_locations'], 'font_locations': r['font_locations'],
            'expected_output_sha256': p['output_hash'], 'expected_output_bytes': p['output_size'],
            'production_can_apply': False, 'runtime_tested': False,
            'dynamic_formatter_enabled': False, 'deadline_layout_enabled': False}


def copy_recipe(profile):
    i = profile_info(profile)
    return CopyRecipe(i['version_id'], SOURCE_HASH, REVIEWED.source_size,
                      i['expected_output_sha256'], i['expected_output_bytes'])


def profile_for_version(version):
    if not isinstance(version, str):
        raise ValueError('Unknown recovery profile version')
    matches = [p for p in PROFILE_IDS if PINS[p]['recipe']['version_id'] == version]
    if len(matches) != 1:
        raise ValueError('Unknown recovery profile version')
    return matches[0]


def load_bundle(profile, root):
    info = profile_info(profile)
    folder = Path(root) if profile == 'm020' else Path(root) / profile
    expected = PINS[profile]['recipe']
    recipe = strict_json((folder / ('m020-recipe.json' if profile == 'm020' else 'recipe.json')).read_bytes())
    if recipe != expected:
        raise ValueError('Pinned profile recipe differs')
    versions = strict_json((folder / 'versions.json').read_bytes())
    entries = build_versions(versions, expected['schema_version'])
    if len(entries) != 1:
        raise ValueError('One pinned profile source required')
    v = entries[0]
    output_key = 'historical_m020_sha256' if profile == 'm020' else 'expected_output_sha256'
    size_key = 'historical_m020_size' if profile == 'm020' else 'expected_output_size'
    expected_entry = {'id': expected['version_id'], 'filename': 'Ld95.exe',
        'file_version': '1.0.3.16', 'product_version': '1.0.3.0',
        'source_sha256': SOURCE_HASH, 'source_size': REVIEWED.source_size,
        output_key: info['expected_output_sha256'], size_key: info['expected_output_bytes'],
        'catalog': expected['catalog'], 'release_approved': False}
    if v != expected_entry:
        raise ValueError('Pinned profile version/output differs')
    catalog = (folder / expected['catalog']).read_bytes()
    if len(catalog) > 1024 * 1024 or hashlib.sha256(catalog).hexdigest() != expected['catalog_sha256']:
        raise ValueError('Pinned profile catalog differs')
    return catalog, versions, recipe


def preview_versions(profile, versions):
    # Read-only Controller uses the historical schema-1 field names. This is
    # solely a preview projection, never passed as a production apply plan.
    profile_info(profile)
    result = deepcopy(versions)
    if result['schema_version'] == 2:
        result['schema_version'] = 1
        for v in result['versions']:
            v['historical_m020_sha256'] = v.pop('expected_output_sha256')
            v['historical_m020_size'] = v.pop('expected_output_size')
    return result
