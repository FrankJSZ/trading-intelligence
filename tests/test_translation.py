import asyncio

from app.providers.translator import SpanishNewsTranslator


def test_parse_google_translation_payload():
    payload = [
        [["Bitcoin sube tras los datos de inflación", "Bitcoin rises after inflation data", None, None]],
        None,
        "en",
    ]
    assert SpanishNewsTranslator._parse_payload(payload) == "Bitcoin sube tras los datos de inflación"


async def _translate_articles_without_network():
    translator = SpanishNewsTranslator()

    async def fake_translate(text):
        mapping = {
            "Bitcoin rises after inflation data": "Bitcoin sube tras los datos de inflación",
            "Fed keeps rates unchanged": "La Fed mantiene las tasas sin cambios",
        }
        return mapping.get(text, text), text in mapping

    translator.translate = fake_translate
    articles = [
        {"title": "Bitcoin rises after inflation data", "sentiment": 0.5},
        {"title": "Fed keeps rates unchanged", "sentiment": 0.0},
    ]

    translated, meta = await translator.translate_articles(articles)

    assert translated[0]["title"] == "Bitcoin sube tras los datos de inflación"
    assert translated[0]["original_title"] == "Bitcoin rises after inflation data"
    assert translated[0]["sentiment"] == 0.5
    assert translated[0]["translated"] is True
    assert translated[1]["title"] == "La Fed mantiene las tasas sin cambios"
    assert meta == {"target_language": "es", "translated": 2, "fallback": 0}


def test_translate_articles_preserves_original_and_analysis_fields():
    asyncio.run(_translate_articles_without_network())
