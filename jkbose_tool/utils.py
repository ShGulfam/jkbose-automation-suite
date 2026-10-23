"""
Small shared helpers used across features.
"""
import re
import base64
from pathlib import Path
from PIL import Image

from . import config


def save_page_as_pdf(driver, output_path, landscape: bool = False,
                      print_background: bool = True, scale: float = 1.0) -> Path:
    """
    Saves the CURRENT page as a PDF using Chrome DevTools Protocol's
    Page.printToPDF. Captures the entire page height in one call -- no
    manual scroll+screenshot+stitch needed -- with crisp vector text and
    usually a much smaller file than an equivalent screenshot image
    (nothing to rasterize/compress). Requires a Chrome driver (Selenium's
    execute_cdp_cmd).

    Caveat: this uses Chrome's PRINT layout, which can differ slightly
    from the on-screen layout for pages with unusual print CSS. For a
    fairly plain form page this is rarely an issue, but if the PDF looks
    off compared to the live page, screenshots are the safer fallback.
    """
    output_path = Path(output_path)
    result = driver.execute_cdp_cmd("Page.printToPDF", {
        "landscape": landscape,
        "printBackground": print_background,
        "scale": scale,
        "preferCSSPageSize": False,
    })
    output_path.write_bytes(base64.b64decode(result["data"]))
    return output_path


def parse_serial_spec(spec: str) -> set:
    """
    Parses a serial-number spec like "1-40, 55, 60-65" into a set of ints.
    Comma-separated single numbers and inclusive ranges (a-b). Whitespace
    is ignored. Empty spec -> empty set.
    """
    result = set()
    spec = (spec or "").strip()
    if not spec:
        return result
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            a, b = int(a.strip()), int(b.strip())
            if a > b:
                a, b = b, a
            result.update(range(a, b + 1))
        else:
            result.add(int(part))
    return result


def build_stream_map(pairs) -> dict:
    """
    pairs: iterable of (stream_value, serial_spec_string), e.g.
           [("Science", "1-40,45"), ("Commerce", "41-90")]
    Returns {serial_number: stream_value}. Later pairs win on overlap.
    Serial numbers match the RR file's line order (1-indexed), i.e. the
    same 'idx' used for output filenames.
    """
    stream_map = {}
    for stream_value, spec in pairs:
        stream_value = (stream_value or "").strip()
        if not stream_value:
            continue
        for n in parse_serial_spec(spec):
            stream_map[n] = stream_value
    return stream_map


def parse_stream_map_string(spec: str) -> dict:
    """
    CLI-friendly single-string form:
        "Science:1-40,45;Commerce:41-90;Humanities:91-120"
    (semicolon-separated groups, each "StreamValue:serial-spec").
    """
    pairs = []
    for group in (spec or "").split(";"):
        group = group.strip()
        if not group or ":" not in group:
            continue
        stream_value, serials = group.split(":", 1)
        pairs.append((stream_value.strip(), serials.strip()))
    return build_stream_map(pairs)


def sanitize_filename(name: str) -> str:
    """Strip characters that are invalid in Windows filenames."""
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name).strip()


def read_lines(file_path, keep_blanks: bool = False) -> list:
    """
    Read a plain text file, one value per line.

    keep_blanks=False (default): only non-empty lines are returned, in
    file order -- fine when line position doesn't matter.

    keep_blanks=True: EVERY line is returned, blank ones as "". This
    matters whenever "serial number" = line number in the file (e.g.
    screenshots.py's stream_map, which maps line number -> Stream, and
    the '#' prefix on each output filename) -- if blank lines were
    silently dropped, every RR number after a gap would shift to the
    wrong serial number. With keep_blanks=True, callers should skip
    processing "" entries but the enumeration/index still lines up with
    the real file line numbers.
    """
    values = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            v = line.strip()
            if v or keep_blanks:
                values.append(v)
    return values


def stack_images_vertically(paths, output_path) -> Path:
    """
    Vertically stacks screenshots (top to bottom, in the given order) into
    one image -- e.g. the top-of-page personal details + a scrolled-down
    view of the subjects section, combined into a single file before
    compression. Widths are aligned to the widest input image; narrower
    ones are left-aligned on a white background.
    """
    output_path = Path(output_path)
    imgs = [Image.open(p).convert("RGB") for p in paths]
    width = max(im.width for im in imgs)
    total_height = sum(im.height for im in imgs)
    combined = Image.new("RGB", (width, total_height), "white")
    y = 0
    for im in imgs:
        combined.paste(im, (0, y))
        y += im.height
    combined.save(output_path)
    for im in imgs:
        im.close()
    return output_path


def compress_screenshot(raw_path: Path, fmt: str = None, jpeg_quality: int = None,
                         png_colors: int = None, max_width: int = None) -> Path:
    """
    Re-saves a screenshot at a much smaller file size while keeping text legible.

    fmt="png"  -> palette-quantized PNG. Crisp text edges, big size cut vs a
                  raw 24-bit screenshot (usually 5-10x smaller for a mostly
                  white/text page).
    fmt="jpeg" -> JPEG at given quality. Smallest files; fine down to ~q75
                  for legibility, but soft edges around text.

    raw_path is the screenshot Selenium just saved -- it gets replaced in
    place (same stem, correct extension for the chosen format).
    Returns the path of the final, compressed file.
    """
    raw_path = Path(raw_path)
    fmt = (fmt or config.SCREENSHOT_FORMAT).lower()
    jpeg_quality = jpeg_quality or config.SCREENSHOT_JPEG_QUALITY
    png_colors = png_colors or config.SCREENSHOT_PNG_COLORS
    max_width = config.SCREENSHOT_MAX_WIDTH if max_width is None else max_width

    img = Image.open(raw_path).convert("RGB")

    if max_width and img.width > max_width:
        ratio = max_width / float(img.width)
        img = img.resize((max_width, int(img.height * ratio)), Image.LANCZOS)

    if fmt == "jpeg":
        out_path = raw_path.with_suffix(".jpg")
        img.save(out_path, "JPEG", quality=jpeg_quality, optimize=True)
    else:
        quant = img.quantize(colors=png_colors, method=Image.MEDIANCUT)
        out_path = raw_path.with_suffix(".png")
        quant.save(out_path, "PNG", optimize=True)

    if out_path != raw_path and raw_path.exists():
        try:
            raw_path.unlink()
        except Exception:
            pass

    return out_path
