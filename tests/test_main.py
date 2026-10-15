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

    def test_history_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.json"
            expected = [{"date": "2026-10-15", "trend": trend("Товар")}]
            main.save_history(expected, path)
            self.assertEqual(main.load_history(path), expected)


if __name__ == "__main__":
    unittest.main()
