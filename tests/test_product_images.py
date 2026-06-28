import importlib
import os
from io import BytesIO

from PIL import Image


os.environ.setdefault("BOT_TOKEN", "123:ABC")
bot = importlib.import_module("bot")


def test_extract_meta_image_url_resolves_relative_url():
    page_html = '<meta property="og:image" content="/images/product.jpg">'

    result = bot._extract_meta_image_url("https://example.com/products/item", page_html)

    assert result == "https://example.com/images/product.jpg"


def test_extract_candidate_image_urls_filters_logo_and_resolves_product_image():
    page_html = """
    <img src="/assets/logo.svg">
    <img src="/catalog/product-card.webp" alt="Test Product cream">
    """

    result = bot._extract_candidate_image_urls(
        "https://example.com/search",
        page_html,
        product_name="Test Product cream",
        strict_match=True,
    )

    assert result == ["https://example.com/catalog/product-card.webp"]


def test_extract_candidate_image_urls_rejects_same_brand_wrong_product():
    page_html = """
    <img src="/catalog/eucerin-anti-pigment.webp" alt="Eucerin Anti-Pigment Dual Serum">
    <img src="/catalog/eucerin-sun-protection.webp" alt="Eucerin Sun Protection крем SPF 30">
    """

    result = bot._extract_candidate_image_urls(
        "https://example.com/search",
        page_html,
        product_name="Eucerin Sun Protection крем с SPF 30",
        strict_match=True,
    )

    assert result == ["https://example.com/catalog/eucerin-sun-protection.webp"]


def test_context_matches_product_requires_more_than_brand():
    assert not bot._context_matches_product(
        "La Roche-Posay Anthelios UVMune 400 крем SPF 50+",
        "La Roche-Posay Toleriane Dermo-Cleanser",
    )
    assert bot._context_matches_product(
        "La Roche-Posay Anthelios UVMune 400 крем SPF 50+",
        "La Roche-Posay Anthelios UVMune 400 SPF50",
    )


def test_prepare_telegram_photo_converts_webp_to_jpeg():
    image = Image.new("RGB", (32, 32), color="white")
    output = BytesIO()
    image.save(output, format="WEBP")

    result = bot._prepare_telegram_photo(
        output.getvalue(),
        "image/webp",
        "Test Product",
    )

    assert result is not None
    assert result.filename == "Test_Product.jpg"
