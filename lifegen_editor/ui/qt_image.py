"""Convert Pillow images to Qt for display."""
from __future__ import annotations

from PIL import Image
from PySide6.QtGui import QImage, QPixmap


def pil_to_qpixmap(img: Image.Image) -> QPixmap:
    """Convert an RGBA Pillow image to a QPixmap. Caller may then scale with
    Qt.TransformationMode.FastTransformation for nearest-neighbor pixel art."""
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    data = img.tobytes("raw", "RGBA")
    qimg = QImage(data, img.width, img.height, img.width * 4, QImage.Format.Format_RGBA8888)
    # copy so the QImage owns the data (the bytes object would otherwise be freed)
    return QPixmap.fromImage(qimg.copy())
