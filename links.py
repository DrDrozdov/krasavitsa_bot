from urllib.parse import quote_plus


def make_market_links(query: str) -> dict:
    q = quote_plus(query)

    return {
        "Яндекс Маркет": f"https://market.yandex.ru/search?text={q}",
        "Золотое Яблоко": f"https://goldapple.ru/catalogsearch/result?q={q}",
        "Ozon": f"https://www.ozon.ru/search/?text={q}",
        "Wildberries": f"https://www.wildberries.ru/catalog/0/search.aspx?search={q}",
        "Лэтуаль": f"https://www.letu.ru/search?text={q}",
        "Рив Гош": f"https://rivegauche.ru/search?text={q}",
    }
