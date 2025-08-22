# Copyright (c) 2025 takotime808

from __future__ import annotations

import os
from typing import Dict

def sniff_basic_metadata(path:str, mode:str="basic") -> Dict:
    """
    Very light metadata sniffing that always works without heavy deps.
    For mode="full", we add file times and size; a real implementation would try EXIF/XMP/etc.
    """
    st = os.stat(path)
    md = {
        "size_bytes": st.st_size,
        "modified_time": int(st.st_mtime),
        "created_time": int(getattr(st, "st_ctime", st.st_mtime)),
    }
    if mode == "full":
        md["access_time"] = int(st.st_atime)
        md["owner_uid"] = getattr(st, "st_uid", None)
        md["owner_gid"] = getattr(st, "st_gid", None)
    return md
