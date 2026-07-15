CURATED_PRODUCTS = {
    "skin": [
        {
            "name": "PURITO Oat In Calming Gel Cream",
            "category": "Увлажняющий крем-гель",
            "reason": "Лёгкий базовый вариант для увлажнения; окончательный выбор зависит от переносимости и текущего ухода.",
            "matchScore": 72,
            "priceRange": "1 300–2 600 ₽",
            "usage": "Наносить после очищения; сначала протестировать на небольшом участке.",
            "tradeoffs": ["При выраженной сухости одного крем-геля может быть недостаточно."],
            "marketplaces": [],
        },
        {
            "name": "COSRX Low pH Good Morning Gel Cleanser",
            "category": "Очищение",
            "reason": "Проверенный гель для базового очищения; частоту лучше подбирать по ощущениям после умывания.",
            "matchScore": 68,
            "priceRange": "900–1 900 ₽",
            "usage": "Использовать небольшое количество и уменьшить частоту при стянутости.",
            "tradeoffs": ["Реактивной коже может не подойти отдушка отдельных растительных компонентов."],
            "marketplaces": [],
        },
        {
            "name": "Beauty of Joseon Relief Sun: Rice + Probiotics SPF50+ PA++++",
            "category": "Солнцезащита",
            "reason": "Ежедневный SPF с комфортным форматом; финиш и совместимость с макияжем индивидуальны.",
            "matchScore": 70,
            "priceRange": "1 300–2 900 ₽",
            "usage": "Наносить достаточное количество последним шагом утреннего ухода и обновлять по ситуации.",
            "tradeoffs": ["Формулы для разных рынков могут отличаться."],
            "marketplaces": [{"label": "Яндекс Маркет", "href": "https://ngo.integration.market.yandex.ru/card/krem-dlya-litsa-s-probiotikami-solntsezashchitnyy--beauty-of-joseon-relief-sun-riceprobiotics-spf-50-pa-50-ml/103197717356", "kind": "marketplace"}],
        },
    ],
    "hair": [
        {
            "name": "Lador Dermatical Hair-Loss Shampoo",
            "category": "Шампунь для кожи головы",
            "reason": "Проверенный вариант очищения кожи головы; название продукта не означает лечение выпадения.",
            "matchScore": 65,
            "priceRange": "900–2 100 ₽",
            "usage": "Наносить преимущественно на кожу головы и тщательно смывать.",
            "tradeoffs": ["При выраженном выпадении нужен врач, а не косметический шампунь."],
            "marketplaces": [],
        },
        {
            "name": "OLAPLEX Nº.5 Bond Maintenance® Conditioner",
            "category": "Кондиционер",
            "reason": "Кондиционер для повреждённой и окрашенной длины; количество важно подбирать по толщине волос.",
            "matchScore": 72,
            "priceRange": "2 900–5 500 ₽",
            "usage": "Распределять по длине после шампуня, не перегружая корни.",
            "tradeoffs": ["Для очень тонких волос может потребоваться минимальное количество."],
            "marketplaces": [{"label": "Яндекс Маркет", "href": "https://ngo.integration.market.yandex.ru/card/olaplex-no-5-bond-maintenance---konditsioner-vosstanavlivayushchiy-250ml/103527276110", "kind": "marketplace"}],
        },
        {
            "name": "CHI 44 Iron Guard Thermal Protection Spray",
            "category": "Термозащита",
            "reason": "Спрей для сценария с горячей укладкой; снижает риск повреждения, но не делает любой нагрев безопасным.",
            "matchScore": 69,
            "priceRange": "1 300–2 900 ₽",
            "usage": "Равномерно наносить до горячей укладки и использовать разумную температуру.",
            "tradeoffs": ["Количество и дистанцию нанесения нужно подбирать под толщину волос."],
            "marketplaces": [],
        },
    ],
    "perfume": [
        {
            "name": "Maison Margiela Replica Lazy Sunday Morning Eau de Toilette",
            "category": "Чистый цветочно-мускусный аромат",
            "reason": "Светлый профиль с ассоциацией чистого белья; восприятие мускусов особенно индивидуально.",
            "matchScore": 70,
            "priceRange": "8 000–18 000 ₽",
            "usage": "Сначала протестировать на коже и оценить звучание через несколько часов.",
            "tradeoffs": ["Стойкость и шлейф зависят от кожи и условий."],
            "marketplaces": [],
        },
        {
            "name": "Jo Malone London Wood Sage & Sea Salt Cologne",
            "category": "Минеральный древесный аромат",
            "reason": "Несладкое свежее направление с морской солью и шалфеем.",
            "matchScore": 72,
            "usage": "Тестировать на коже и отдельно оценить мягкую громкость формата cologne.",
            "tradeoffs": ["Не стоит ожидать одинаковой стойкости на разной коже."],
            "priceRange": "около 5 600 ₽",
            "marketplaces": [{"label": "ЦУМ", "href": "https://www.tsum.ru/product/he00455756-odekolon-wood-sage-sea-salt-50ml-jo-malone-london-bestcvetnyi/", "kind": "marketplace"}],
        },
        {
            "name": "Diptyque Eau Duelle Eau de Parfum",
            "category": "Пряная ваниль",
            "reason": "Ваниль с пряным и дымным направлением, а не только кондитерской сладостью.",
            "matchScore": 71,
            "priceRange": "17 000–28 000 ₽",
            "usage": "Сначала сравнить на коже с Eau de Toilette: это разные концентрации и характер звучания.",
            "tradeoffs": ["Ваниль и дымные нюансы могут ощущаться интенсивнее в тепле."],
            "marketplaces": [],
        },
    ],
}


def curated_fallback(mode: str, summary: str | None = None) -> dict:
    label = {"skin": "уходу за кожей", "hair": "уходу за волосами", "perfume": "парфюмерии"}[mode]
    return {
        "status": "complete",
        "mode": mode,
        "summary": summary or (
            f"Основной AI-поиск временно недоступен, поэтому показываю надёжную стартовую подборку по {label}. "
            "Кнопки магазинов показываю только там, где подтвердилась отдельная карточка товара; уточнить параметры можно следующим запросом."
        ),
        "insight": {
            "skin": "Новый уход лучше вводить по одному средству и сначала проверять переносимость на небольшом участке кожи.",
            "hair": "Кожу головы и длину оценивают отдельно: очищение и кондиционирование решают разные задачи.",
            "perfume": "Аромат лучше оценивать на коже минимум 20–30 минут — блоттер показывает только старт.",
        }[mode],
        "products": [dict(product) for product in CURATED_PRODUCTS[mode]],
        "methodology": "curated-fallback",
    }
