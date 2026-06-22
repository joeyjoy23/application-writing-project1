"""Inject WPS-compatible on-click fade animations into python-pptx output."""

from __future__ import annotations

import argparse
import logging
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

log = logging.getLogger(__name__)

_P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
_A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

_ANIM_NAME_RE = re.compile(r"^anim_(\d+)$")


def _q(tag: str) -> str:
    return f"{{{_P_NS}}}{tag}"


def _a(tag: str) -> str:
    return f"{{{_A_NS}}}{tag}"


def _iter_anim_hosts(slide_root: ET.Element):
    for tag in ("sp", "graphicFrame"):
        yield from slide_root.iter(_q(tag))


def _cNvPr_from_host(host: ET.Element) -> ET.Element | None:
    for child in host:
        if not child.tag.endswith("Pr") or child.tag == _q("spPr"):
            continue
        cnv = child.find(_q("cNvPr"))
        if cnv is not None:
            return cnv
    return None


def _collect_anim_shapes(slide_root: ET.Element) -> list[tuple[int, int]]:
    """Return sorted (order, spid) from shapes named anim_NNN."""
    found: list[tuple[int, int]] = []
    for host in _iter_anim_hosts(slide_root):
        cnv = _cNvPr_from_host(host)
        if cnv is None:
            continue
        name = cnv.get("name", "")
        m = _ANIM_NAME_RE.match(name)
        if not m:
            continue
        spid = int(cnv.get("id", "0"))
        found.append((int(m.group(1)), spid))
    found.sort(key=lambda x: x[0])
    return found


def _build_timing_xml(spids: list[int], start_id: int = 10) -> ET.Element:
    """Minimal main-sequence click fade/appear for WPS + MSO."""
    timing = ET.Element(_q("timing"))
    tn_lst = ET.SubElement(timing, _q("tnLst"))
    par_root = ET.SubElement(tn_lst, _q("par"))
    ctn_root = ET.SubElement(par_root, _q("cTn"))
    ctn_root.set("id", "1")
    ctn_root.set("dur", "indefinite")
    ctn_root.set("restart", "never")
    ctn_root.set("nodeType", "tmRoot")
    child_root = ET.SubElement(ctn_root, _q("childTnLst"))

    seq = ET.SubElement(child_root, _q("seq"))
    seq.set("concurrent", "1")
    seq.set("nextAc", "seek")
    ctn_seq = ET.SubElement(seq, _q("cTn"))
    ctn_seq.set("id", "2")
    ctn_seq.set("dur", "indefinite")
    ctn_seq.set("nodeType", "mainSeq")
    child_seq = ET.SubElement(ctn_seq, _q("childTnLst"))

    nid = start_id
    for spid in spids:
        par = ET.SubElement(child_seq, _q("par"))
        ctn_par = ET.SubElement(par, _q("cTn"))
        ctn_par.set("id", str(nid))
        ctn_par.set("fill", "hold")
        nid += 1
        st_cond = ET.SubElement(ctn_par, _q("stCondLst"))
        cond = ET.SubElement(st_cond, _q("cond"))
        cond.set("delay", "0")
        child_par = ET.SubElement(ctn_par, _q("childTnLst"))

        par2 = ET.SubElement(child_par, _q("par"))
        ctn_eff = ET.SubElement(par2, _q("cTn"))
        ctn_eff.set("id", str(nid))
        ctn_eff.set("presetID", "10")
        ctn_eff.set("presetClass", "entr")
        ctn_eff.set("presetSubtype", "0")
        ctn_eff.set("fill", "hold")
        ctn_eff.set("nodeType", "clickEffect")
        ctn_eff.set("grpId", "0")
        nid += 1
        st2 = ET.SubElement(ctn_eff, _q("stCondLst"))
        c2 = ET.SubElement(st2, _q("cond"))
        c2.set("delay", "0")
        child_eff = ET.SubElement(ctn_eff, _q("childTnLst"))

        set_el = ET.SubElement(child_eff, _q("set"))
        bhvr = ET.SubElement(set_el, _q("cBhvr"))
        ctn_b = ET.SubElement(bhvr, _q("cTn"))
        ctn_b.set("id", str(nid))
        ctn_b.set("dur", "500")
        ctn_b.set("fill", "hold")
        nid += 1
        stb = ET.SubElement(ctn_b, _q("stCondLst"))
        cb = ET.SubElement(stb, _q("cond"))
        cb.set("delay", "0")
        tgt = ET.SubElement(bhvr, _q("tgtEl"))
        sp_tgt = ET.SubElement(tgt, _q("spTgt"))
        sp_tgt.set("spid", str(spid))
        attr = ET.SubElement(bhvr, _q("attributeName"))
        attr.text = "style.visibility"
        to_el = ET.SubElement(set_el, _q("to"))
        str_val = ET.SubElement(to_el, _q("strVal"))
        str_val.set("val", "visible")

    prev = ET.SubElement(seq, _q("prevCondLst"))
    pcond = ET.SubElement(prev, _q("cond"))
    pcond.set("evt", "onPrev")
    pcond.set("delay", "0")
    tgt = ET.SubElement(pcond, _q("tgtEl"))
    ET.SubElement(tgt, _q("sldTgt"))

    return timing


def apply_click_reveal(pptx_path: Path, *, effect: str = "fade") -> bool:
    """Inject on-click appear sequence for shapes named anim_NNN. Returns False on failure."""
    del effect  # only fade/appear for now
    try:
        buf = pptx_path.read_bytes()
        out_files: dict[str, bytes] = {}
        with zipfile.ZipFile(pptx_path, "r") as zin:
            for name in zin.namelist():
                out_files[name] = zin.read(name)

        slide_names = sorted(
            n for n in out_files if n.startswith("ppt/slides/slide") and n.endswith(".xml")
        )
        changed = 0
        for name in slide_names:
            root = ET.fromstring(out_files[name])
            pairs = _collect_anim_shapes(root)
            if not pairs:
                continue
            spids = [p[1] for p in pairs]
            for old in root.findall(_q("timing")):
                root.remove(old)
            root.append(_build_timing_xml(spids))
            out_files[name] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            changed += 1

        if changed == 0:
            log.warning("no anim_* shapes found in %s", pptx_path)
            return True

        tmp = pptx_path.with_suffix(".anim.pptx")
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
            for name, data in out_files.items():
                zout.writestr(name, data)
        tmp.replace(pptx_path)
        return True
    except Exception as exc:
        log.warning("animation inject failed: %s", exc)
        return False


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Add WPS on-click fade to classroom pptx")
    parser.add_argument("pptx", type=Path)
    args = parser.parse_args(argv)
    ok = apply_click_reveal(args.pptx)
    print("OK" if ok else "FAILED (file unchanged if partial)")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
