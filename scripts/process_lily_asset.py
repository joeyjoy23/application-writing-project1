"""处理百合装饰图：裁切、弱化水印、导出 Hero / 透明 / 角落用图。

用法（项目根目录）:
    python scripts/process_lily_asset.py [输入图路径]

默认读取 Cursor 工作区 assets 下的原图；输出到 assets/ui/。
"""

from __future__ import annotations

import sys
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SRC = ROOT / "assets" / "ui" / "lily-source.png"
OUT_DIR = ROOT / "assets" / "ui"
BG_SAMPLE = np.array([247.0, 240.0, 232.0])


def _content_bbox(arr: np.ndarray, *, threshold: float = 28.0, pad: int = 12) -> tuple[int, int, int, int]:
    dist = np.sqrt(((arr.astype(np.float32) - BG_SAMPLE) ** 2).sum(axis=2))
    ys, xs = np.where(dist > threshold)
    y0, y1 = int(ys.min()), int(ys.max())
    x0, x1 = int(xs.min()), int(xs.max())
    h, w = arr.shape[:2]
    return (
        max(0, x0 - pad),
        max(0, y0 - pad),
        min(w - 1, x1 + pad),
        min(h - 1, y1 + pad),
    )


def _flood_bg_mask(crop: np.ndarray, *, tol: float = 14.0) -> np.ndarray:
    ch, cw, _ = crop.shape
    bg_mask = np.zeros((ch, cw), dtype=bool)
    q: deque[tuple[int, int]] = deque()

    def near_bg(px: np.ndarray) -> bool:
        return float(np.linalg.norm(px.astype(np.float32) - BG_SAMPLE)) <= tol

    for x in range(cw):
        for y in (0, ch - 1):
            if near_bg(crop[y, x]) and not bg_mask[y, x]:
                bg_mask[y, x] = True
                q.append((y, x))
    for y in range(ch):
        for x in (0, cw - 1):
            if near_bg(crop[y, x]) and not bg_mask[y, x]:
                bg_mask[y, x] = True
                q.append((y, x))
    while q:
        y, x = q.popleft()
        for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if 0 <= ny < ch and 0 <= nx < cw and not bg_mask[ny, nx] and near_bg(crop[ny, nx]):
                bg_mask[ny, nx] = True
                q.append((ny, nx))
    return bg_mask


def _soften_watermark(arr: np.ndarray) -> np.ndarray:
    out = arr.copy()
    dist = np.sqrt(((out.astype(np.float32) - BG_SAMPLE) ** 2).sum(axis=2))
    sat = out.max(axis=2) - out.min(axis=2)
    wm = (dist > 5) & (dist < 35) & (sat < 25) & (out.mean(axis=2) > 200)
    out[wm] = BG_SAMPLE.astype(np.uint8)
    return out


def process(src: Path, out_dir: Path = OUT_DIR) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    im = Image.open(src).convert("RGB")
    arr = np.array(im)
    x0, y0, x1, y1 = _content_bbox(arr)
    crop = arr[y0 : y1 + 1, x0 : x1 + 1]

    bg_mask = _flood_bg_mask(crop)
    alpha = np.where(bg_mask, 0, 255).astype(np.uint8)
    transparent = Image.fromarray(np.dstack([crop, alpha]), "RGBA")
    alpha_ch = transparent.split()[3]
    alpha_ch = alpha_ch.filter(ImageFilter.MaxFilter(5))
    alpha_ch = alpha_ch.filter(ImageFilter.MinFilter(5))
    alpha_ch = alpha_ch.filter(ImageFilter.GaussianBlur(1.0))
    transparent.putalpha(alpha_ch)

    hero = Image.fromarray(_soften_watermark(arr), "RGB").crop((x0, y0, x1 + 1, y1 + 1))

    corner = transparent.copy()
    if corner.width > 480:
        ratio = 480 / corner.width
        corner = corner.resize((480, int(corner.height * ratio)), Image.Resampling.LANCZOS)

    paths = {
        "transparent": out_dir / "lily-transparent.png",
        "hero": out_dir / "lily-hero.png",
        "corner": out_dir / "lily-corner.png",
    }
    transparent.save(paths["transparent"])
    hero.save(paths["hero"])
    corner.save(paths["corner"])
    return paths


def main() -> None:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SRC
    if not src.is_file():
        raise SystemExit(f"输入图不存在: {src}")
    paths = process(src)
    for name, path in paths.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
