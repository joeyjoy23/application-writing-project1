"""Inject WPS-compatible on-click appear animations into python-pptx output."""

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

_ANIM_NAME_RE = re.compile(r"^anim_(\d+)$")


def _q(tag: str) -> str:
    return f"{{{_P_NS}}}{tag}"


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


def count_click_reveal_stats(pptx_path: Path) -> tuple[int, int]:
    """Return (slides_with_timing, total_anim_shape_count)."""
    timing_slides = 0
    anim_count = 0
    with zipfile.ZipFile(pptx_path, "r") as zin:
        for name in sorted(zin.namelist()):
            if not name.startswith("ppt/slides/slide") or not name.endswith(".xml"):
                continue
            root = ET.fromstring(zin.read(name))
            pairs = _collect_anim_shapes(root)
            anim_count += len(pairs)
            if root.find(_q("timing")) is not None:
                timing_slides += 1
    return timing_slides, anim_count


def _append_visibility_set(parent: ET.Element, *, spid: int, ctn_id: int) -> None:
    set_el = ET.SubElement(parent, _q("set"))
    bhvr = ET.SubElement(set_el, _q("cBhvr"))
    ctn_b = ET.SubElement(bhvr, _q("cTn"))
    ctn_b.set("id", str(ctn_id))
    ctn_b.set("dur", "1")
    ctn_b.set("fill", "hold")
    stb = ET.SubElement(ctn_b, _q("stCondLst"))
    cb = ET.SubElement(stb, _q("cond"))
    cb.set("delay", "0")
    tgt = ET.SubElement(bhvr, _q("tgtEl"))
    sp_tgt = ET.SubElement(tgt, _q("spTgt"))
    sp_tgt.set("spid", str(spid))
    attr_lst = ET.SubElement(bhvr, _q("attrNameLst"))
    attr = ET.SubElement(attr_lst, _q("attrName"))
    attr.text = "style.visibility"
    to_el = ET.SubElement(set_el, _q("to"))
    str_val = ET.SubElement(to_el, _q("strVal"))
    str_val.set("val", "visible")


def _append_fade_in_effect(parent: ET.Element, *, spid: int, ctn_id: int) -> None:
    """Fade-in entrance companion — MSO/WPS hide-until-click without cNvPr hidden."""
    anim_eff = ET.SubElement(parent, _q("animEffect"))
    anim_eff.set("transition", "in")
    anim_eff.set("filter", "fade")
    bhvr = ET.SubElement(anim_eff, _q("cBhvr"))
    ctn_b = ET.SubElement(bhvr, _q("cTn"))
    ctn_b.set("id", str(ctn_id))
    ctn_b.set("dur", "500")
    ctn_b.set("fill", "hold")
    stb = ET.SubElement(ctn_b, _q("stCondLst"))
    cb = ET.SubElement(stb, _q("cond"))
    cb.set("delay", "0")
    tgt = ET.SubElement(bhvr, _q("tgtEl"))
    sp_tgt = ET.SubElement(tgt, _q("spTgt"))
    sp_tgt.set("spid", str(spid))


def _build_timing_xml(spids: list[int]) -> ET.Element:
    """Main-sequence on-click appear (preset 1) — structure aligned with MSO/WPS."""
    timing = ET.Element(_q("timing"))
    tn_lst = ET.SubElement(timing, _q("tnLst"))
    par_root = ET.SubElement(tn_lst, _q("par"))
    ctn_root = ET.SubElement(par_root, _q("cTn"))
    ctn_root.set("id", "1")
    ctn_root.set("dur", "indefinite")
    ctn_root.set("restart", "whenNotActive")
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

    nid = 3
    for grp_idx, spid in enumerate(spids):
        par_outer = ET.SubElement(child_seq, _q("par"))
        ctn_outer = ET.SubElement(par_outer, _q("cTn"))
        ctn_outer.set("id", str(nid))
        ctn_outer.set("fill", "hold")
        nid += 1
        st_outer = ET.SubElement(ctn_outer, _q("stCondLst"))
        cond_outer = ET.SubElement(st_outer, _q("cond"))
        cond_outer.set("evt", "onBegin")
        cond_outer.set("delay", "indefinite")
        child_outer = ET.SubElement(ctn_outer, _q("childTnLst"))

        par_mid = ET.SubElement(child_outer, _q("par"))
        ctn_mid = ET.SubElement(par_mid, _q("cTn"))
        ctn_mid.set("id", str(nid))
        ctn_mid.set("fill", "hold")
        nid += 1
        st_mid = ET.SubElement(ctn_mid, _q("stCondLst"))
        cond_mid = ET.SubElement(st_mid, _q("cond"))
        cond_mid.set("delay", "0")
        child_mid = ET.SubElement(ctn_mid, _q("childTnLst"))

        par_eff = ET.SubElement(child_mid, _q("par"))
        ctn_eff = ET.SubElement(par_eff, _q("cTn"))
        ctn_eff.set("id", str(nid))
        ctn_eff.set("presetID", "10")
        ctn_eff.set("presetClass", "entr")
        ctn_eff.set("presetSubtype", "0")
        ctn_eff.set("fill", "hold")
        ctn_eff.set("grpId", str(grp_idx))
        ctn_eff.set("nodeType", "clickEffect")
        ctn_eff.set("dur", "500")
        nid += 1
        st_eff = ET.SubElement(ctn_eff, _q("stCondLst"))
        cond_eff = ET.SubElement(st_eff, _q("cond"))
        cond_eff.set("evt", "begin")
        cond_eff.set("delay", "0")
        child_eff = ET.SubElement(ctn_eff, _q("childTnLst"))
        _append_visibility_set(child_eff, spid=spid, ctn_id=nid)
        nid += 1
        _append_fade_in_effect(child_eff, spid=spid, ctn_id=nid)
        nid += 1

    prev = ET.SubElement(seq, _q("prevCondLst"))
    pcond = ET.SubElement(prev, _q("cond"))
    pcond.set("evt", "onBegin")
    pcond.set("delay", "0")
    tn = ET.SubElement(pcond, _q("tn"))
    tgt = ET.SubElement(tn, _q("tgtEl"))
    ET.SubElement(tgt, _q("sldTgt"))

    bld_lst = ET.SubElement(timing, _q("bldLst"))
    for spid in spids:
        bld = ET.SubElement(bld_lst, _q("bldP"))
        bld.set("spid", str(spid))
        bld.set("grpId", "0")
        bld.set("uiExpand", "1")
        bld.set("build", "p")

    return timing


def apply_click_reveal(pptx_path: Path, *, effect: str = "appear") -> bool:
    """Inject on-click appear sequence for shapes named anim_NNN. Returns False on failure.

    Shapes stay visible in edit view (no cNvPr hidden="1") — WPS hides hidden shapes
    in both edit and slideshow, causing blank cards. Timing uses fade entrance +
    visibility set + bldLst (MSO pattern) so slideshow may hide-until-click without
    blanking edit view.
    """
    del effect  # appear only for WPS compatibility
    try:
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
    parser = argparse.ArgumentParser(description="Add WPS on-click appear to classroom pptx")
    parser.add_argument("pptx", type=Path)
    args = parser.parse_args(argv)
    ok = apply_click_reveal(args.pptx)
    print("OK" if ok else "FAILED (file unchanged if partial)")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
