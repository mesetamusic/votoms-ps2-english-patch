"""Test English patch for Soukou Kihei Votoms (PS2, SLPS-25827).

Copies the ISO and overwrites a handful of strings in place inside _DATA.DIP.
Each English string must fit in the space of the Japanese string it replaces
(no pointers are moved), and is null-padded to that length.

Usage: python patch_test.py <original.iso> <patched.iso>
"""
import os, shutil, struct, sys

SECTOR = 2048

# (path inside _DATA.DIP, offset in that file, expected Japanese, English)
PATCHES = [
    # Main menu help line, one per menu item
    ('root/menu/text.mtt', 0x6c8, 'プレイするミッションを選択し、出撃します。', 'Select a mission and sortie.'),
    ('root/menu/text.mtt', 0x6f4, '搭乗するＡＴのセッティングを行います。', 'Set up the AT you will pilot.'),
    ('root/menu/text.mtt', 0x71c, 'ＣＯＭや他のプレイヤーと自由に対戦します。', 'Battle the COM or other players.'),
    ('root/menu/text.mtt', 0x748, '獲得したＡＴやＢＧＭなど、さまざまな特典を鑑賞します。', 'View unlocked ATs, BGM and other extras.'),
    ('root/menu/text.mtt', 0x780, 'オプション設定を変更します。', 'Change game settings.'),
    ('root/menu/text.mtt', 0x7a0, 'プレイするミッションを選択してください。', 'Choose a mission to play.'),
    # Mission 000 (tutorial) opening lines
    ('root/mission/000.pac', 0x148d0, 'よし、俺がお前さんに\nＡＴ操作の基本ってえやつを\n教えてやろう。',
     "Alright, I'll teach you\nthe basics of piloting\nan AT."),
    ('root/mission/000.pac', 0x14948, 'まずは、手前にある\nＡＴに乗ってみろ。',
     'First, hop into\nthat AT up ahead.'),
    ('root/mission/000.pac', 0x149c0, 'ＡＴだけじゃねえ、お前さん\n自身をうまく扱えなくちゃあ\nいけねえな。',
     "It ain't just the AT.\nYou gotta be able to\nhandle yourself, too."),
    ('root/mission/000.pac', 0x14a38, 'おおっと、みだりに銃なんぞ\n撃つもんじゃあねぇ。',
     "Whoa there! Don't go\nfiring that gun wildly."),
]


def iso_find(f, name):
    """Return (byte offset, size) of a root-directory file in an ISO9660 image."""
    f.seek(16 * SECTOR)
    pvd = f.read(SECTOR)
    assert pvd[1:6] == b'CD001', 'not an ISO9660 image'
    root = pvd[156:190]
    lba, size = struct.unpack_from('<I', root, 2)[0], struct.unpack_from('<I', root, 10)[0]
    f.seek(lba * SECTOR)
    d = f.read(size)
    i = 0
    while i < len(d):
        ln = d[i]
        if ln == 0:  # records don't cross sector boundaries
            i = (i // SECTOR + 1) * SECTOR
            continue
        ext, sz = struct.unpack_from('<I', d, i + 2)[0], struct.unpack_from('<I', d, i + 10)[0]
        nm = d[i + 33:i + 33 + d[i + 32]].split(b';')[0].decode('ascii')
        if nm.upper() == name.upper():
            return ext * SECTOR, sz
        i += ln
    raise FileNotFoundError(name)


def dip_index(f, base):
    """Map 'root/dir/file' -> (offset relative to DIP start, size)."""
    f.seek(base)
    ent_len, name_len, _total, ent_start, name_off, data_off = struct.unpack('<6I', f.read(24))
    f.seek(base + name_off)
    raw = f.read(name_len)
    names = [raw[i:i + 32].split(b'\0')[0].decode('ascii') for i in range(0, name_len, 32)]
    f.seek(base + ent_start)
    raw = f.read(ent_len)
    ents = [struct.unpack_from('<HHII', raw, i) for i in range(0, len(raw) - 11, 12)]
    out = {}

    def walk(idx, prefix):
        flag, ni, a, b = ents[idx]
        if flag == 0:
            for c in range(b, b + a):
                walk(c, prefix + names[ni] + '/')
        else:
            out[prefix + names[ni]] = (data_off + b, a * 32)
    walk(0, '')
    return out


def main(src, dst):
    if os.path.abspath(src) == os.path.abspath(dst):
        sys.exit('refusing to patch the original in place')
    print('copying ISO...')
    shutil.copyfile(src, dst)
    with open(dst, 'r+b') as f:
        dip_off, _ = iso_find(f, '_DATA.DIP')
        idx = dip_index(f, dip_off)
        for path, off, jp, en in PATCHES:
            fo, fsz = idx[path]
            pos = dip_off + fo + off
            jpb = jp.encode('cp932')
            enb = en.encode('ascii')
            f.seek(pos)
            cur = f.read(len(jpb) + 1)
            if cur != jpb + b'\0':
                sys.exit(f'{path}@{off:#x}: original text not found, aborting')
            if len(enb) > len(jpb):
                sys.exit(f'{path}@{off:#x}: English is {len(enb)} bytes, slot is {len(jpb)}')
            f.seek(pos)
            f.write(enb.ljust(len(jpb) + 1, b'\0'))
            print(f'patched {path}@{off:#x}: {en!r}')
    print('done:', dst)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
