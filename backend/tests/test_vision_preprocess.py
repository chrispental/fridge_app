"""Exercise the real Pillow upload boundary without storage or AI services."""
import base64
import io

import pytest
from conftest import LOCAL_USER
from fastapi import HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from app.config import settings
from app.routers import inventory
from app.services.vision import preprocess


def _image_bytes(mode="RGB", size=(80, 40), format="PNG", **save_options):
    image = Image.new(mode, size)
    buffer = io.BytesIO()
    image.save(buffer, format=format, **save_options)
    return buffer.getvalue()


@pytest.mark.parametrize("mode,format", [
    ("RGB", "JPEG"), ("RGBA", "PNG"), ("L", "PNG"),
    ("P", "PNG"), ("CMYK", "JPEG"),
])
def test_preprocess_normalizes_uploads_to_rgb_jpeg(mode, format, monkeypatch):
    monkeypatch.setattr(settings, "max_image_dim", 128)
    jpeg, data_url = preprocess(_image_bytes(mode, format=format))
    with Image.open(io.BytesIO(jpeg)) as image:
        image.load()
        assert image.format == "JPEG"
        assert image.mode == "RGB"
        assert image.size == (80, 40)  # Small uploads are not enlarged.
    prefix, payload = data_url.split(",", 1)
    assert prefix == "data:image/jpeg;base64"
    assert base64.b64decode(payload, validate=True) == jpeg


@pytest.mark.parametrize("size,expected", [
    ((320, 160), (128, 64)), ((160, 320), (64, 128)),
])
def test_preprocess_bounds_both_orientations(size, expected, monkeypatch):
    monkeypatch.setattr(settings, "max_image_dim", 128)
    jpeg, _ = preprocess(_image_bytes(size=size))
    with Image.open(io.BytesIO(jpeg)) as image:
        assert image.size == expected


def test_preprocess_applies_exif_orientation_before_resize(monkeypatch):
    monkeypatch.setattr(settings, "max_image_dim", 128)
    exif = Image.Exif()
    exif[274] = 6  # Rotate a landscape camera image clockwise into portrait.
    jpeg, _ = preprocess(_image_bytes(size=(320, 160), format="JPEG", exif=exif))
    with Image.open(io.BytesIO(jpeg)) as image:
        assert image.size == (64, 128)
        assert 274 not in image.getexif()  # Do not rotate the output again.


def test_preprocess_rejects_non_image_bytes():
    with pytest.raises(UnidentifiedImageError):
        preprocess(b"not an image")


def test_preprocess_retains_pillow_decompression_bomb_protection(monkeypatch):
    raw = _image_bytes(size=(20, 20))
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 100)
    with pytest.raises(Image.DecompressionBombError):
        preprocess(raw)


@pytest.mark.parametrize("raw", [b"", b"not an image"])
def test_invalid_upload_fails_before_storage_or_ai(raw, db, monkeypatch):
    def unexpected_call(*args, **kwargs):
        pytest.fail("Invalid uploads must not reach storage or AI")

    monkeypatch.setattr(inventory, "get_blob_storage", unexpected_call)
    monkeypatch.setattr(inventory, "extract_items", unexpected_call)
    upload = UploadFile(filename="invalid.png", file=io.BytesIO(raw))
    with pytest.raises(HTTPException) as error:
        inventory.extract(user=LOCAL_USER, file=upload, db=db)
    assert error.value.status_code == 400
