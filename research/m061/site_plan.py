"""m061: pure-Python verifier/planner for per-site list-insert retargeting (no capstone).

Each pinned site is a 5-byte `call rel32` to the MFC CWnd::SendDlgItemMessage
wrapper. A future patch would retarget only that rel32 to a reviewed helper with
the identical thiscall/ret 0x10 contract. This module verifies the pinned window
hashes on an accepted source profile and returns (offset, old, new) tuples in
memory. It never writes or applies them.
"""
import hashlib, json, struct

BASE = 0x400000
WRAPPER_VA = 0x4ea671
WRAPPER_SHA256 = 'ccb96bfb9c7d0adec5af3d4d8bc8009a8d5d5021243dc16c2766a243d4c4cf01'
TEXT_RVA, TEXT_END = 0x1000, 0x124c39


class Refuse(ValueError):
    pass


def need(ok, msg):
    if not ok:
        raise Refuse(msg)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def load_sites(manifest_bytes, priority_only=True):
    m = json.loads(manifest_bytes)
    need(m.get('wrapper_va') == hex(WRAPPER_VA) and m.get('production_can_apply') is False, 'Manifest identity')
    need(m.get('window_bytes_before_call') == 16, 'Window contract')
    rows = [s for s in m['sites'] if (s['priority'] if priority_only else s['phase1_candidate'])]
    need(rows and len({s['va'] for s in rows}) == len(rows), 'Site list')
    return rows


def verify_sites(image, sites):
    """`image` must already be accepted by source_profile.derive (identical .text)."""
    need(type(image) is bytes and len(image) > TEXT_END, 'Image')
    w = WRAPPER_VA - BASE
    need(sha(image[w:w + 0x2e]) == WRAPPER_SHA256, 'Wrapper bytes')
    out = []
    for s in sites:
        va = int(s['va'], 16)
        o = va - BASE  # .text raw pointer == RVA for this image family
        need(TEXT_RVA + 16 <= o and o + 5 <= TEXT_END, 'Site outside .text')
        need(s['kind'] == 'CWnd::SendDlgItemMessage' and s['message'] in ('LB_INSERTSTRING', 'LB_ADDSTRING', 'CB_INSERTSTRING'), 'Site kind')
        need(sha(image[o - 16:o + 5]) == s['window_sha256'], 'Site window hash ' + s['va'])
        need(image[o] == 0xE8 and va + 5 + struct.unpack_from('<i', image, o + 1)[0] == WRAPPER_VA, 'Site target')
        out.append(o)
    return out


def plan_retarget(image, sites, helper_va):
    need(type(helper_va) is int and BASE <= helper_va <= 0xffffffff, 'Helper VA')
    plan = []
    for o in verify_sites(image, sites):
        rel = helper_va - (BASE + o + 5)
        need(-(1 << 31) <= rel < (1 << 31), 'REL32 range')
        plan.append((o, image[o:o + 5], b'\xe8' + struct.pack('<i', rel)))
    return plan
