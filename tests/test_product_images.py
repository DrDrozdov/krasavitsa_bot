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
    <img src="/catalog/product-card.webp">
    """

    result = bot._extract_candidate_image_urls("https://example.com/search", page_html)

    assert result == ["https://example.com/catalog/product-card.webp"]


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
