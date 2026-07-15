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
    assert not bot._context_matches_product(
        "La Roche-Posay Anthelios UVMune 400 крем SPF 50+",
        "La Roche-Posay Anthelios Shaka SPF 50 набор",
    )
    assert bot._context_matches_product(
        "La Roche-Posay Anthelios UVMune 400 крем SPF 50+",
        "La Roche-Posay Anthelios UVMune 400 SPF50",
    )


def test_duckduckgo_result_matches_product_uses_title_and_source():
    assert bot._duckduckgo_result_matches_product(
        "La Roche-Posay Anthelios UVMune 400 крем SPF 50+",
        {
            "title": "La Roche-Posay Anthelios UVMune 400 SPF50",
            "source": "laroche-posay.ru",
            "image": "https://example.com/anthelios-uvmune-400.jpg",
        },
    )
    assert not bot._duckduckgo_result_matches_product(
        "La Roche-Posay Anthelios UVMune 400 крем SPF 50+",
        {
            "title": "La Roche-Posay Toleriane Dermo-Cleanser",
            "source": "laroche-posay.ru",
            "image": "https://example.com/toleriane-cleanser.jpg",
        },
    )


def test_extract_duckduckgo_vqd():
    assert bot._extract_duckduckgo_vqd("DDG.pageLayout.load('x'); vqd='123-456';") == "123-456"


def test_extract_yandex_image_candidates_decodes_orig_url_and_context():
    page_html = (
        "&quot;origUrl&quot;:&quot;https://example.com/eucerin.jpg&quot;"
        "&quot;alt&quot;:&quot;Eucerin Sun Protection SPF 30&quot;"
    )

    result = bot._extract_yandex_image_candidates(page_html)

    assert result == [
        (
            "https://example.com/eucerin.jpg",
            '"origUrl":"https://example.com/eucerin.jpg""alt":"Eucerin Sun Protection SPF 30"',
        )
    ]


def test_remove_search_query_noise_from_yandex_context():
    context = (
        "title La Roche-Posay Anthelios Shaka "
        "&text=La+Roche-Posay+Anthelios+UVMune+400+SPF+50"
    )

    cleaned = bot._remove_search_query_noise(context)

    assert "UVMune" not in cleaned
    assert "400" not in cleaned
    assert "Anthelios Shaka" in cleaned


def test_format_price_range_uses_code_and_spaced_dash():
    assert bot.format_price_range("800-1000 ₽") == "💵 <b>Цена:</b> <code>800 – 1000 ₽</code>"


def test_product_image_search_queries_are_limited_by_runtime_constant():
    assert bot.MAX_IMAGE_SEARCH_QUERIES < len(bot._product_image_search_queries("Test Product"))


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


def test_every_mode_has_a_branded_fallback_image():
    for mode in ("skin", "hair", "perfume"):
        result = bot.load_mode_fallback_image(mode, "Test Product")
        assert result is not None
        assert result.filename == "Test_Product.jpg"
