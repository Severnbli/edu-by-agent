"""Prepare local photos for use in site content."""

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

_SIDE = 1600
_GAP = 12


def _load_photo(path: Path) -> Image.Image:
    try:
        with Image.open(path) as original:
            photo = ImageOps.exif_transpose(original).convert("RGBA")
    except (OSError, Image.DecompressionBombError) as e:
        raise ValueError(f"{path}: can't read it as an image ({e})") from e
    photo.thumbnail((_SIDE, _SIDE), Image.Resampling.LANCZOS)
    return photo


def combine_photos(paths: list[Path], output: Path, columns: int = 2) -> dict:
    """Join photos in rows, in input order, preserving their aspect ratios."""
    if len(paths) < 2:
        raise ValueError("Provide at least two photos.")
    if not 1 <= columns <= 10:
        raise ValueError("Columns must be between 1 and 10.")
    if output.suffix.lower() not in {".jpg", ".jpeg"}:
        raise ValueError("The output filename must end in .jpg or .jpeg.")
    if output.exists():
        raise FileExistsError(f"{output}: output already exists")

    photos = [_load_photo(path) for path in paths]
    rows = [photos[i : i + columns] for i in range(0, len(photos), columns)]
    ratios = [[photo.width / photo.height for photo in row] for row in rows]
    heights = [(_SIDE - _GAP * (len(row) - 1)) / sum(row) for row in ratios]
    total_height = sum(heights) + _GAP * (len(rows) - 1)
    scale = _SIDE / max(_SIDE, total_height)
    dimensions = (max(1, round(_SIDE * scale)), max(1, round(total_height * scale)))
    canvas = Image.new("RGB", dimensions, "white")

    y = 0.0
    for row, aspects, height in zip(rows, ratios, heights, strict=True):
        x = 0.0
        for photo, aspect in zip(row, aspects, strict=True):
            width = height * aspect
            left, top = round(x * scale), round(y * scale)
            size = (
                max(1, round((x + width) * scale) - left),
                max(1, round((y + height) * scale) - top),
            )
            tile = photo.resize(size, Image.Resampling.LANCZOS)
            canvas.paste(tile, (left, top), tile.getchannel("A"))
            x += width + _GAP
        y += height + _GAP

    encoded = BytesIO()
    canvas.save(encoded, "JPEG", quality=87, optimize=True)
    with output.open("xb") as file:
        file.write(encoded.getbuffer())
    return {
        "path": str(output),
        "width": canvas.width,
        "height": canvas.height,
        "bytes": encoded.tell(),
    }
