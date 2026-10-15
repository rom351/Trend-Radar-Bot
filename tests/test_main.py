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


class TrendRadarTests(unittest.TestCase):
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
