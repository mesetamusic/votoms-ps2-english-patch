# Building the patch

Requirements: **Windows** (the menu graphics are rendered with Windows fonts through PowerShell), **Python 3.10+** (standard library only), and the original Japanese ISO (MD5 `5487eb7a234301dd3932174446ef9bcd`).

Game files and ISOs are never committed (`.gitignore` covers `*.iso`, `build/` and `work/texout/`).

## Rebuild from scratch

```powershell
# 1. unpack the ELF and the _DATA.DIP archive from the original ISO
python tools/unpack.py "Soukou Kihei Votoms (Japan).iso" build

# 2. redraw the Japanese menu graphics in English (writes work/texout/)
python tools/texpatch.py build/dip/root work/texout

# 3. check the translation fits (report in work/report.txt), then build the ISO
python tools/insert.py check build/dip/root build/disc/SLPS_258.27
python tools/insert.py build build/dip/root build/disc/SLPS_258.27 "Soukou Kihei Votoms (Japan).iso" "Votoms (English).iso"

# 4. make the release patch
python tools/make_xdelta.py make "Soukou Kihei Votoms (Japan).iso" "Votoms (English).iso" patch/Votoms-English-v1.0.xdelta
```

`python tools/make_xdelta.py hash <iso>` prints CRC32 / MD5 / SHA-1, and `python tools/make_xdelta.py apply <original> <patch> <out>` applies a patch without any other tool.

## Editing the translation

`work/en/*.tsv`: one line per string, `id <TAB> jp-check <TAB> english`.

| Syntax | Meaning |
|---|---|
| `\|` | line break |
| `{keepN}` prefix | keep the first N original characters (control bytes in front of the real text) |
| `long~~short` | fallbacks: the first one that fits its slot is used |
| `=` | leave the Japanese string untouched |
| `@c02 … @c07`, `%s`, `%d`, `#E` … | game colour codes, printf arguments and button glyphs: keep them |

`jp-check` is the first characters of the Japanese string (from `work/sheet_frozen.tsv`) and guards against editing the wrong line.

Most strings are rewritten in place and must fit the original byte length (`insert.py check` lists any that don't). Strings in `menu/text.mtt` are repacked, and every pointer to them is updated, so only the total size of that pool matters.

## Files

| Path | Purpose |
|---|---|
| `work/sheet_frozen.tsv` | every unique Japanese string with its id, line count and width |
| `work/strings_frozen.json` | every occurrence: file, offset, available room, mode (in place / pointer pool) |
| `work/en/*.tsv` | the English translation |
| `tools/insert.py` | applies the translation and writes the patched ISO (same size as the original) |
| `tools/texpatch.py`, `tex.py`, `render_text.ps1` | menu texture decoding and English redraws (labels, mission titles, scenario banners) |
| `tools/dip.py`, `pof0.py`, `patch_test.py`, `unpack.py` | `_DATA.DIP` archive, DUMY/POF0 pointer tables, ISO9660 lookup |
| `tools/make_xdelta.py` | VCDIFF (xdelta3-compatible) patch creator / applier |
| `tools/extract.py`, `extract2.py`, `add_*.py`, `sjis_scan.py` | one-off scripts used to build the string sheet; not needed to rebuild |
