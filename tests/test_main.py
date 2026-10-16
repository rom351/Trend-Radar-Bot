import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

import main


def trend(
    item,
    potential="высокий",
    strength="высокая",
    margin="средний",
    entry="низкая",
    competition="средняя",
):
    return {
        "item": item,
        "commercial_potential": potential,
        "strength": strength,
        "margin_potential": margin,
        "entry_difficulty": entry,
        "competition": competition,
    }


def full_trend(item="Умная кормушка"):
    return {
        "category": "товары для животных",
        "item": item,
        "examples": "Xiaomi Smart Pet Feeder, Petkit Fresh Element",
        "reason": "Покупатели хотят выдавать корм по расписанию и контролировать порции",
        "source": "Гипотеза, которую нужно проверить вручную",
        "search_queries": "умная кормушка отзывы, автоматическая кормушка цена",
        "purchase_price": "ориентир закупки требует проверки",
        "retail_price": "ориентир розницы требует проверки",
        "margin_potential": "средний",
        "competition": "средний",
        "audience": "владельцы кошек и собак",
        "sales_angle": "показать выдачу корма по расписанию",
        "first_test": "сравнить десять предложений на маркетплейсах",
        "commercial_potential": "средний",
        "entry_difficulty": "средняя",
        "strength": "средняя",
        "risks": "надёжность механизма и возвраты",
        "check": "отзывы, гарантию и совместимость приложения",
        "link": "",
    }


class TrendRadarTests(unittest.TestCase):
    def test_response_schema_requires_exact_count(self):
        schema = main.build_response_schema(10)
        trends_schema = schema["properties"]["trends"]
        self.assertEqual(trends_schema["minItems"], 10)
        self.assertEqual(trends_schema["maxItems"], 10)

    def test_clean_trend_requires_russian_text_and_valid_ratings(self):
        self.assertIsNotNone(main.clean_trend(full_trend()))
        self.assertIsNone(main.clean_trend(full_trend("Smart pet feeder")))
        invalid = full_trend()
        invalid["strength"] = "сильная"
        self.assertIsNone(main.clean_trend(invalid))

    def test_unverified_google_claim_is_relabelled(self):
        candidate = full_trend()
        candidate["source"] = "Google Trends показывает растущий интерес"
        candidate["link"] = "https://example.com/unverified"
        grounded = main.ground_source(candidate, set())
        self.assertEqual(grounded["link"], "")
        self.assertIn("Гипотеза Groq", grounded["source"])

    def test_rating_only_entries_are_not_marked_published(self):
        today = date(2026, 10, 17)
        entries = main.build_history_entries(today, [full_trend()], rating_only=True)
        self.assertFalse(entries[0]["published"])

    def test_similar_items_are_duplicates(self):
        self.assertTrue(
            main.items_match(
                "Складная бутылка для собак",
                "складные бутылки для собак",
            )
        )
        self.assertFalse(main.items_match("Умная кормушка", "Дорожный органайзер"))

    def test_recent_history_filters_by_date(self):
        today = date(2026, 10, 15)
        history = [
            {"date": today.isoformat(), "trend": trend("A")},
            {"date": (today - timedelta(days=30)).isoformat(), "trend": trend("B")},
        ]
        self.assertEqual(len(main.recent_history(history, today, 30)), 1)

    def test_weekly_top_ranks_and_deduplicates(self):
        today = date(2026, 10, 15)
        history = [
            {"date": today.isoformat(), "trend": trend("Умная кормушка")},
            {"date": today.isoformat(), "trend": trend("Умные кормушки")},
            {
                "date": today.isoformat(),
                "published": False,
                "trend": trend("Резервный товар"),
            },
            {
                "date": today.isoformat(),
                "trend": trend(
                    "Органайзер",
                    potential="средний",
                    strength="средняя",
                ),
            },
        ]
        result = main.weekly_top(history, today)
        self.assertEqual(
            [entry["trend"]["item"] for entry in result],
            ["Умная кормушка", "Органайзер"],
        )
        rating = main.rating_top(history, today)
        self.assertIn("Резервный товар", [entry["trend"]["item"] for entry in rating])

    def test_state_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.json"
            expected = {
                "entries": [{"date": "2026-10-15", "trend": trend("Товар")}],
                "pinned_rating_message_id": 123,
            }
            main.save_state(expected, path)
            self.assertEqual(main.load_state(path), expected)

    def test_legacy_history_is_migrated(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.json"
            path.write_text('[]', encoding="utf-8")
            self.assertEqual(
                main.load_state(path),
                {"entries": [], "pinned_rating_message_id": None},
            )


if __name__ == "__main__":
    unittest.main()
