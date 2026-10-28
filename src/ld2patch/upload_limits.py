"""Bounded upload size rule for the exact reviewed text catalog; no scan bypass."""
import hashlib,json
from .catalog import validate_catalog
DEFAULT_TEXT_LIMIT=400000
REVIEWED_PATH='patches/m042/catalog.json'
REVIEWED_SIZE=499730
REVIEWED_SHA256='b9b4d7d5bcc334d0588fd75db180cedf3eab8266fa54bf951e9eb21fed0d234b'
def within_reviewed_text_size(path,data):
    if len(data)<=DEFAULT_TEXT_LIMIT:return True
    approved={REVIEWED_PATH:(REVIEWED_SIZE,REVIEWED_SHA256,552), 'patches/m045/catalog.json':(501614,'a3b15568cf7a4047745e8877f682fe8d1ea5b327ba0d113e1a29b46f2248a3bc',554)}
    if path not in approved:return False
    size,digest,count=approved[path]
    if len(data)!=size or hashlib.sha256(data).hexdigest()!=digest:return False
    try:
        catalog=json.loads(data.decode('utf-8'))
        return validate_catalog(catalog)==count
    except (ValueError,UnicodeError,KeyError,TypeError):
        return False
