"""Image upload validation and classification (mocked provider; no network)."""
import asyncio
import io

import pytest
from PIL import Image

from app.ai import classifier
from app.ai.errors import AIError
from app.ai.groq_service import Completion
from tests.conftest import make_ai_settings
from tests.helpers.fakes import ScriptedGroq

MAX = 3 * 1024 * 1024


def img_bytes(fmt="JPEG", size=(200, 120), mode="RGB", color=(30, 160, 60), **save):
    buf = io.BytesIO()
    Image.new(mode, size, color).save(buf, format=fmt, **save)
    return buf.getvalue()


def reply(text):
    return ScriptedGroq(Completion(content=text, model="test-vision-model"))


def classify(raw, groq, mime="image/jpeg"):
    return asyncio.run(classifier.classify(raw, mime, groq, MAX))


# --- validation -----------------------------------------------------------------------------------

@pytest.mark.parametrize("mime", ["image/gif", "application/pdf", "text/plain", None, "image/svg+xml"])
def test_unsupported_declared_types_are_rejected(mime):
    with pytest.raises(AIError) as e:
        classifier.prepare_image(img_bytes(), mime, MAX)
    assert e.value.status_code == 415


def test_real_format_must_be_allowed_even_if_mime_lies():
    with pytest.raises(AIError) as e:
        classifier.prepare_image(img_bytes("GIF"), "image/jpeg", MAX)
    assert e.value.status_code == 415


def test_oversized_and_empty_uploads_are_rejected():
    with pytest.raises(AIError) as e:
        classifier.prepare_image(b"\xff" * (MAX + 1), "image/jpeg", MAX)
    assert e.value.status_code == 413 and e.value.code == "image_too_large"
    with pytest.raises(AIError) as e:
        classifier.prepare_image(b"", "image/jpeg", MAX)
    assert e.value.status_code == 400


@pytest.mark.parametrize("raw", [b"not an image at all", b"\xff\xd8\xff\xe0 truncated jpeg", img_bytes()[:60]])
def test_corrupt_images_are_rejected(raw):
    with pytest.raises(AIError) as e:
        classifier.prepare_image(raw, "image/jpeg", MAX)
    assert e.value.code in {"invalid_image", "unsupported_image_type"} and e.value.status_code in {400, 415}


def test_tiny_image_is_rejected():
    with pytest.raises(AIError) as e:
        classifier.prepare_image(img_bytes(size=(8, 8)), "image/jpeg", MAX)
    assert e.value.code == "image_too_small"


def test_decompression_bomb_is_rejected():
    bomb = img_bytes("PNG", size=(9000, 9000), mode="L", color=255)  # ~81 MP but tiny on disk
    assert len(bomb) < MAX
    with pytest.raises(AIError) as e:
        classifier.prepare_image(bomb, "image/png", MAX)
    assert e.value.code == "invalid_image"


# --- normalisation / privacy ----------------------------------------------------------------------

def test_output_is_a_small_metadata_free_jpeg():
    exif = Image.Exif()
    exif[0x010F] = "SecretCameraMaker"
    exif[0x8825] = {1: "N", 2: (17.0, 22.0, 0.0)}  # GPS IFD
    raw = img_bytes("JPEG", size=(3000, 2000), exif=exif)
    assert b"SecretCameraMaker" in raw
    out = classifier.prepare_image(raw, "image/jpeg", MAX)
    img = Image.open(io.BytesIO(out))
    assert img.format == "JPEG" and max(img.size) <= 1024
    assert b"SecretCameraMaker" not in out and not img.getexif()


@pytest.mark.parametrize("fmt,mime", [("PNG", "image/png"), ("WEBP", "image/webp")])
def test_png_and_webp_with_transparency_are_flattened(fmt, mime):
    out = classifier.prepare_image(img_bytes(fmt, mode="RGBA", color=(0, 0, 0, 0)), mime, MAX)
    assert Image.open(io.BytesIO(out)).mode == "RGB"


# --- classification -------------------------------------------------------------------------------

def test_successful_classification_shape_and_request():
    groq = reply('{"category": "organic", "explanation": "Food scraps are visible."}')
    r = classify(img_bytes(), groq)
    assert r.category == "organic" and r.confidence is None
    assert r.explanation == "Food scraps are visible." and r.handling_guidance == classifier.GUIDANCE["organic"]
    assert any("No confidence score" in x for x in r.limitations)
    call = groq.calls[0]
    assert call["kind"] == "vision"
    parts = call["messages"][0]["content"]
    assert parts[1]["type"] == "image_url" and parts[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_confidence_is_never_fabricated_even_if_model_offers_one():
    r = classify(img_bytes(), reply('{"category": "glass", "explanation": "Bottle.", "confidence": 0.99}'))
    assert r.confidence is None


@pytest.mark.parametrize("given,expected", [("Paper/Cardboard", "paper_cardboard"), ("e-waste", "electronic"), ("Hazardous Waste", "hazardous"),
                                            ("MIXED WASTE", "mixed"), ("uncertain", "unknown"), ("Plastic", "plastic")])
def test_category_synonyms_are_normalised(given, expected):
    assert classify(img_bytes(), reply('{"category": "%s", "explanation": "x"}' % given)).category == expected


def test_unknown_category_from_model_becomes_unknown():
    r = classify(img_bytes(), reply('{"category": "radioactive sludge", "explanation": "x"}'))
    assert r.category == "unknown" and any("outside the supported list" in x for x in r.limitations)


def test_json_wrapped_in_prose_is_still_parsed():
    assert classify(img_bytes(), reply('Sure! {"category": "metal", "explanation": "A can."} Hope that helps.')).category == "metal"


@pytest.mark.parametrize("text", ["I think it is plastic", "", "{broken", '{"explanation": "no category"}'])
def test_unparseable_output_is_an_error_not_a_fake_result(text):
    with pytest.raises(AIError) as e:
        classify(img_bytes(), reply(text))
    assert e.value.code == "ai_bad_response"


def test_hazardous_and_electronic_carry_extra_safety_limitations():
    for cat in ("hazardous", "electronic"):
        r = classify(img_bytes(), reply('{"category": "%s", "explanation": "x"}' % cat))
        assert any("not a laboratory test" in x or "batteries" in x for x in r.limitations)


def test_explanation_is_truncated():
    r = classify(img_bytes(), reply('{"category": "plastic", "explanation": "' + "word " * 200 + '"}'))
    assert len(r.explanation) <= 300


def test_provider_errors_propagate():
    groq = ScriptedGroq(AIError("ai_rate_limited", "slow down", 429, 5))
    with pytest.raises(AIError) as e:
        classify(img_bytes(), groq)
    assert e.value.status_code == 429


# --- HTTP endpoint ----------------------------------------------------------------------------------

def post(client, raw, mime="image/jpeg", name="photo.jpg"):
    return client.post("/api/v1/ai/classify-waste", files={"image": (name, raw, mime)})


def test_endpoint_success(ai_client):
    r = post(ai_client(groq=reply('{"category": "plastic", "explanation": "A bottle."}')), img_bytes())
    assert r.status_code == 200 and r.json()["category"] == "plastic" and r.json()["confidence"] is None


def test_endpoint_rejects_wrong_type_and_missing_file(ai_client):
    client = ai_client(groq=reply("{}"))
    assert post(client, b"GIF89a", "image/gif", "a.gif").status_code == 415
    assert client.post("/api/v1/ai/classify-waste").status_code == 422


def test_endpoint_rejects_oversized_upload_without_calling_provider(ai_client):
    groq = reply("{}")
    client = ai_client(make_ai_settings(upload_max_bytes=1000), groq=groq)
    r = post(client, img_bytes(size=(600, 600)))
    assert r.status_code == 413 and r.json()["detail"]["code"] == "image_too_large" and groq.calls == []


def test_endpoint_provider_error_is_safe(ai_client):
    r = post(ai_client(groq=ScriptedGroq(AIError("ai_model_unsupported", "The configured AI model is unavailable.", 502))), img_bytes())
    assert r.status_code == 502 and r.json()["detail"]["code"] == "ai_model_unsupported"


def test_nothing_is_written_to_disk(ai_client, tmp_path, monkeypatch):
    import os
    monkeypatch.chdir(tmp_path)
    before = set(os.listdir(tmp_path))
    post(ai_client(groq=reply('{"category": "glass", "explanation": "x"}')), img_bytes())
    assert set(os.listdir(tmp_path)) == before
