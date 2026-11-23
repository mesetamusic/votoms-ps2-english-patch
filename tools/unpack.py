"""Unpack the files the patch tools work on from the original Japanese ISO.

usage: python unpack.py <original.iso> <out_dir>
Writes out_dir/disc/SLPS_258.27, out_dir/disc/_DATA.DIP and the extracted
archive under out_dir/dip/root/...
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dip
from patch_test import iso_find

iso, out = sys.argv[1], sys.argv[2]
os.makedirs(os.path.join(out, 'disc'), exist_ok=True)
with open(iso, 'rb') as f:
    for name in ('SLPS_258.27', '_DATA.DIP'):
        off, size = iso_find(f, name)
        f.seek(off)
        with open(os.path.join(out, 'disc', name), 'wb') as o:
            left = size
            while left:
                b = f.read(min(left, 1 << 22)); o.write(b); left -= len(b)
        print('wrote', name)
fh, files, _ = dip.parse(os.path.join(out, 'disc', '_DATA.DIP'))
for p, o, s in files:
    dst = os.path.join(out, 'dip', p); os.makedirs(os.path.dirname(dst), exist_ok=True)
    fh.seek(o); open(dst, 'wb').write(fh.read(s))
print('extracted', len(files), 'files to', os.path.join(out, 'dip'))
