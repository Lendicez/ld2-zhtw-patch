"""Bounded upload size rule for the exact reviewed text catalog; no scan bypass."""
import hashlib,json
from .catalog import validate_catalog
DEFAULT_TEXT_LIMIT=400000
REVIEWED_PATH='patches/m042/catalog.json'
REVIEWED_SIZE=499730
REVIEWED_SHA256='b9b4d7d5bcc334d0588fd75db180cedf3eab8266fa54bf951e9eb21fed0d234b'
def within_reviewed_text_size(path,data):
    if len(data)<=DEFAULT_TEXT_LIMIT:return True
    if path!=REVIEWED_PATH or len(data)!=REVIEWED_SIZE:return False
    if hashlib.sha256(data).hexdigest()!=REVIEWED_SHA256:return False
    try:
        catalog=json.loads(data.decode('utf-8'))
        return validate_catalog(catalog)==552
    except (ValueError,UnicodeError,KeyError,TypeError):
        return False
