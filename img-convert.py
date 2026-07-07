import os
from pathlib import Path
from io import BytesIO
from PIL import Image, ImageOps

# --------- Config ---------
INPUT_ROOT = r"/home/Mark/Projects/battle-maps/toConvert"
OUTPUT_ROOT = r"/home/Mark/Projects/battle-maps/converted"
MAX_HEIGHT = 1920

JPEG_QUALITIES = [95, 90, 85]   # highest -> lowest; we pick smallest output size among these
PNG_COMPRESS_LEVEL = 9           # 0-9; higher is smaller/slower
# --------------------------


def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def open_and_orient(path: Path) -> Image.Image:
    # applies EXIF orientation (phone cameras)
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img)
        # for safety, detach from context
        return img.copy()


def rotate_to_portrait_if_needed(img: Image.Image) -> Image.Image:
    # Rotate 90° only when landscape -> portrait (height >= width)
    if img.width > img.height:
        return img.rotate(90, expand=True)
    return img


def resize_if_taller_than_max_height(img: Image.Image) -> Image.Image:
    if img.height <= MAX_HEIGHT:
        return img
    scale = MAX_HEIGHT / img.height
    new_w = max(1, round(img.width * scale))
    return img.resize((new_w, MAX_HEIGHT), resample=Image.LANCZOS)


def has_alpha(img: Image.Image) -> bool:
    return img.mode in ("RGBA", "LA") or ("transparency" in img.info)


def to_rgb_for_jpeg(img: Image.Image) -> Image.Image:
    # JPEG can't keep alpha; flatten over white
    if img.mode in ("RGBA", "LA") or has_alpha(img):
        base = Image.new("RGB", img.size, (255, 255, 255))
        base.paste(img, mask=img.split()[-1])
        return base
    return img.convert("RGB")


def choose_smaller_format(img: Image.Image) -> bytes:
    """
    Returns bytes for the smaller between:
    - JPEG (try multiple qualities, choose smallest)
    - PNG (single compress level)
    """
    # JPEG candidate (flatten alpha)
    rgb = to_rgb_for_jpeg(img)
    best_jpeg = None
    for q in JPEG_QUALITIES:
        buf = BytesIO()
        rgb.save(buf, format="JPEG", quality=q, optimize=True)
        b = buf.getvalue()
        if best_jpeg is None or len(b) < len(best_jpeg):
            best_jpeg = b

    # PNG candidate (keep alpha if present)
    png_img = img
    if png_img.mode not in ("RGB", "RGBA", "P", "L", "LA"):
        png_img = png_img.convert("RGBA" if has_alpha(png_img) else "RGB")
    buf = BytesIO()
    png_img.save(buf, format="PNG", optimize=True, compress_level=PNG_COMPRESS_LEVEL)
    png_bytes = buf.getvalue()

    if len(best_jpeg) <= len(png_bytes):
        return best_jpeg, ".jpg"
    else:
        return png_bytes, ".png"


def process_file(in_path: Path, out_root: Path):
    rel = in_path.relative_to(INPUT_ROOT)
    out_dir = out_root / rel.parent
    ensure_dir(out_dir)

    out_base = out_dir / rel.stem

    img = open_and_orient(in_path)
    if getattr(img, "is_animated", False):
        img.seek(0)

    # 1) rotate first (no cropping)
    img = rotate_to_portrait_if_needed(img)
    # 2) shrink if needed (no cropping)
    img = resize_if_taller_than_max_height(img)
    # 3) convert to whichever is smaller (JPEG vs PNG)
    chosen_bytes, ext = choose_smaller_format(img)

    out_path = out_base.with_suffix(ext)
    with open(out_path, "wb") as f:
        f.write(chosen_bytes)
    return out_path


def main():
    in_root = Path(INPUT_ROOT)
    out_root = Path(OUTPUT_ROOT)
    ensure_dir(out_root)

    exts = {".jpg", ".jpeg", ".png"}
    count = 0

    for p in in_root.rglob("*"):
        if p.is_file() and p.suffix.lower() in exts:
            try:
                out = process_file(p, out_root)
                print(f"{count:06d} {p} -> {out}")
                count += 1
            except Exception as e:
                print(f"FAIL: {p} ({e})")

    print(f"Done. Processed {count} images.")


if __name__ == "__main__":
    main()
