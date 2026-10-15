import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from zoneinfo import ZoneInfo

import requests


KYIV = ZoneInfo("Europe/Kyiv")
DAILY_COUNT = 8
HISTORY_DAYS = 60
DEDUP_DAYS = 30
WEEKLY_DAYS = 7
HISTORY_PATH = Path(__file__).resolve().parent / "data" / "trend_history.json"
GOOGLE_TRENDS_GEOS = ("UA", "PL", "DE", "US")

TREND_FIELDS = (
    "category",
    "item",
    "examples",
    "reason",
    "source",
    "search_queries",
    "purchase_price",
    "retail_price",
    "margin_potential",
    "competition",
    "audience",
    "sales_angle",
    "first_test",
    "commercial_potential",
    "entry_difficulty",
    "strength",
    "risks",
    "check",
    "link",
)

BASE_RULES = """
Ты Trend Radar Bot — русскоязычный аналитик товарных трендов и e-commerce.

Строгие правила:
- Пиши только на русском языке.
- Каждый пункт — конкретный товар, узкая ниша или реальный бренд, который можно проверить.
- Не выдумывай бренды, ссылки, продажи, проценты, рейтинги и точные объёмы спроса.
- Не используй абстракции вроде «локальные товары», «здоровый образ жизни» или ShopLocal.
- Отделяй наблюдаемый сигнал от гипотезы. Если точных данных нет, так и напиши.
- Цены указывай только ориентировочным диапазоном и отмечай, что их нужно проверить.
- Для каждого пункта дай 2–4 реальных примера товаров, брендов или площадок.
- Дай 2–4 конкретных поисковых запроса для самостоятельной проверки.
- Первый тест должен занимать не больше 20 минут и не требовать закупки партии.
- Оцени поля commercial_potential, entry_difficulty, strength, competition и margin_potential
  одним из значений: низкий, средний, высокий.
- В link ставь только реальную ссылку из блока живых сигналов, если она прямо относится к товару.
  Иначе оставь пустую строку.
- Не используй переносы строк внутри строковых значений JSON.

Верни строго JSON object:
{
  "trends": [
    {
      "category": "категория",
      "item": "конкретный товар или узкая ниша",
      "examples": "2–4 реальных примера",
      "reason": "почему интерес может расти именно сейчас",
      "source": "наблюдаемый сигнал и где его проверить",
      "search_queries": "2–4 поисковых запроса",
      "purchase_price": "ориентир закупочной цены или требует проверки",
      "retail_price": "ориентир розничной цены или требует проверки",
      "margin_potential": "низкий / средний / высокий",
      "competition": "низкий / средний / высокий",
      "audience": "кому продавать",
      "sales_angle": "как показать товар в рекламе или контенте",
      "first_test": "тест на 10–20 минут без закупки партии",
      "commercial_potential": "низкий / средний / высокий",
      "entry_difficulty": "низкая / средняя / высокая",
      "strength": "низкая / средняя / высокая",
      "risks": "сезонность, доставка, сертификация или другие риски",
      "check": "что проверить перед вложениями",
      "link": "проверяемая ссылка или пустая строка"
    }
  ]
}
"""


def env(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Не задан обязательный секрет {name}")
    return value


def normalize_item(value):
    return " ".join(re.findall(r"[a-zа-яё0-9]+", str(value).lower()))


def item_stems(value):
    suffixes = (
        "иями",
        "ами",
        "ями",
        "ого",
        "ему",
        "ому",
        "ая",
        "яя",
        "ые",
        "ие",
        "ий",
        "ый",
        "ой",
        "ов",
        "ев",
        "ам",
        "ям",
        "ах",
        "ях",
        "а",
        "я",
        "ы",
        "и",
    )
    stems = []
    for token in normalize_item(value).split():
        stem = token
        for suffix in suffixes:
            if len(token) - len(suffix) >= 3 and token.endswith(suffix):
                stem = token[: -len(suffix)]
                break
        stems.append(stem)
    return set(stems)


def items_match(left, right):
    left = normalize_item(left)
    right = normalize_item(right)
    if not left or not right:
        return False
    if left == right:
        return True
    if min(len(left), len(right)) >= 10 and (left in right or right in left):
        return True
    left_stems = item_stems(left)
    right_stems = item_stems(right)
    if left_stems and right_stems:
        overlap = len(left_stems & right_stems) / max(len(left_stems), len(right_stems))
        if overlap >= 0.75:
            return True
    return SequenceMatcher(None, left, right).ratio() >= 0.84


def is_duplicate(item, existing_items):
    return any(items_match(item, existing) for existing in existing_items)


def fetch_live_signals(limit_per_geo=6):
    signals = []
    for geo in GOOGLE_TRENDS_GEOS:
        try:
            response = requests.get(
                "https://trends.google.com/trending/rss",
                params={"geo": geo},
                timeout=20,
            )
            response.raise_for_status()
            root = ET.fromstring(response.content)
            for item in root.findall("./channel/item")[:limit_per_geo]:
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                if title:
                    signals.append({"market": geo, "title": title, "link": link})
        except (requests.RequestException, ET.ParseError):
            continue
    return signals


def build_prompt(count, excluded_items, live_signals):
    excluded = ", ".join(excluded_items[-160:]) or "нет"
    signal_lines = [
        f"- {signal['market']}: {signal['title']} — {signal['link']}"
        for signal in live_signals
    ]
    signals = "\n".join(signal_lines) or "Живые сигналы сейчас недоступны. Не изображай их наличие."

    return f"""
Составь утренний товарный дайджест. Верни ровно {count} разных новых позиций.

Не повторяй товары и близкие варианты из списка последних 30 дней:
{excluded}

Приоритетные направления: товары для дома, beauty и skincare, fitness и sleep tech,
товары для животных, travel accessories, kitchen gadgets, creator tools, AI-гаджеты,
детские товары и недорогие товары для маркетплейсов.

Живые поисковые сигналы Google Trends по рынкам UA, PL, DE и US приведены ниже.
Используй только релевантные товарные сигналы. Не превращай новости, спорт и имена людей
в товарный тренд без ясной коммерческой связи.
{signals}

{BASE_RULES}
"""


def ask_groq(prompt):
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {env('GROQ_API_KEY')}",
            "Content-Type": "application/json",
        },
        json={
            "model": "openai/gpt-oss-20b",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Ты осторожный русскоязычный аналитик товарных трендов. "
                        "Не выдумывай факты и отвечай только валидным JSON."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 10000,
            "response_format": {"type": "json_object"},
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def parse_trends(text):
    try:
        data = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return []
    trends = data.get("trends", [])
    return trends if isinstance(trends, list) else []


def clean_trend(raw):
    if not isinstance(raw, dict):
        return None
    trend = {field: str(raw.get(field, "")).strip() for field in TREND_FIELDS}
    required = TREND_FIELDS[:-1]
    if any(not trend[field] for field in required):
        return None
    if len(trend["item"]) < 4 or len(trend["reason"]) < 20:
        return None
    return trend


def get_trends(recent_items, live_signals):
    collected = []
    excluded = list(recent_items)
    allowed_links = {signal["link"] for signal in live_signals if signal.get("link")}

    for attempt in range(4):
        missing = DAILY_COUNT - len(collected)
        if missing <= 0:
            break
        requested = min(12, missing + 4)
        try:
            raw_trends = parse_trends(
                ask_groq(build_prompt(requested, excluded, live_signals))
            )
        except (requests.RequestException, KeyError, TypeError):
            if attempt == 3:
                raise
            time.sleep(3 * (attempt + 1))
            continue
        added = 0
        for raw in raw_trends:
            trend = clean_trend(raw)
            if not trend or is_duplicate(trend["item"], excluded):
                continue
            if trend["link"] not in allowed_links:
                trend["link"] = ""
            collected.append(trend)
            excluded.append(trend["item"])
            added += 1
            if len(collected) == DAILY_COUNT:
                break
        if added == 0 and attempt < 3:
            time.sleep(2)

    if len(collected) != DAILY_COUNT:
        raise RuntimeError(
            f"Не удалось собрать {DAILY_COUNT} качественных новых трендов: "
            f"получено {len(collected)}"
        )
    return collected


def load_history(path=HISTORY_PATH):
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def recent_history(history, today, days):
    cutoff = today - timedelta(days=days - 1)
    return [
        entry
        for entry in history
        if parse_date(entry.get("date"))
        and cutoff <= parse_date(entry.get("date")) <= today
    ]


def save_history(history, path=HISTORY_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(history, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def label_score(value, reverse=False):
    normalized = str(value).strip().lower()
    scores = {"низкий": 1, "низкая": 1, "средний": 2, "средняя": 2, "высокий": 3, "высокая": 3}
    score = scores.get(normalized, 2)
    return 4 - score if reverse else score


def trend_score(trend):
    raw = (
        2 * label_score(trend.get("commercial_potential"))
        + 2 * label_score(trend.get("strength"))
        + label_score(trend.get("margin_potential"))
        + label_score(trend.get("entry_difficulty"), reverse=True)
        + label_score(trend.get("competition"), reverse=True)
    )
    return round(raw / 21 * 10, 1)


def weekly_top(history, today, count=5):
    candidates = recent_history(history, today, WEEKLY_DAYS)
    unique = []
    seen = []
    for entry in sorted(
        candidates,
        key=lambda candidate: trend_score(candidate.get("trend", {})),
        reverse=True,
    ):
        trend = entry.get("trend", {})
        item = trend.get("item", "")
        if item and not is_duplicate(item, seen):
            unique.append(entry)
            seen.append(item)
        if len(unique) == count:
            break
    return unique


def send_telegram(text):
    chunks = []
    current = ""
    for block in text.split("\n\n"):
        part = block.strip() + "\n\n"
        if current and len(current) + len(part) > 3800:
            chunks.append(current.strip())
            current = part
        else:
            current += part
    if current.strip():
        chunks.append(current.strip())

    for chunk in chunks:
        response = requests.post(
            f"https://api.telegram.org/bot{env('TELEGRAM_BOT_TOKEN')}/sendMessage",
            data={
                "chat_id": env("TELEGRAM_CHAT_ID"),
                "text": chunk,
                "disable_web_page_preview": True,
            },
            timeout=30,
        )
        response.raise_for_status()


def send_sheet_row(row):
    response = requests.post(
        env("GOOGLE_SHEETS_WEBHOOK_URL"),
        data=json.dumps(row, ensure_ascii=False),
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    response.raise_for_status()


def format_trend(index, trend):
    lines = [
        f"{index}. {trend['item']}",
        f"Категория: {trend['category']}",
        f"Примеры: {trend['examples']}",
        f"Почему растёт: {trend['reason']}",
        f"Сигнал: {trend['source']}",
        f"Закупка: {trend['purchase_price']}",
        f"Розница: {trend['retail_price']}",
        f"Маржа: {trend['margin_potential']}",
        f"Конкуренция: {trend['competition']}",
        f"Аудитория: {trend['audience']}",
        f"Как продавать: {trend['sales_angle']}",
        f"Что искать: {trend['search_queries']}",
        f"Первый тест: {trend['first_test']}",
        f"Потенциал: {trend['commercial_potential']}",
        f"Сложность входа: {trend['entry_difficulty']}",
        f"Сила сигнала: {trend['strength']}",
        f"Риски: {trend['risks']}",
        f"Проверить: {trend['check']}",
    ]
    if trend.get("link"):
        lines.append(trend["link"])
    return "\n".join(lines)


def sheet_payload(today, trend):
    reason = (
        f"Примеры: {trend['examples']}. Почему растёт: {trend['reason']}. "
        f"Закупка: {trend['purchase_price']}. Розница: {trend['retail_price']}. "
        f"Маржа: {trend['margin_potential']}. Конкуренция: {trend['competition']}. "
        f"Аудитория: {trend['audience']}. Риски: {trend['risks']}. "
        f"Что искать: {trend['search_queries']}. Проверить: {trend['check']}."
    )
    action = f"{trend['sales_angle']}. Первый тест: {trend['first_test']}"
    return {
        "date": today.isoformat(),
        "category": trend["category"],
        "item": trend["item"],
        "reason": reason,
        "source": trend["source"],
        "strength": trend["strength"],
        "action": action,
        "link": trend["link"],
        "status": "новое",
    }


def build_weekly_digest(history, today):
    top = weekly_top(history, today)
    blocks = [f"Субботний Trend Radar — топ-{len(top)} за неделю"]
    for index, entry in enumerate(top, start=1):
        trend = entry["trend"]
        blocks.append(
            "\n".join(
                [
                    f"{index}. {trend['item']} — {trend_score(trend)}/10",
                    f"Почему в топе: {trend['reason']}",
                    f"Потенциал: {trend['commercial_potential']}",
                    f"Конкуренция: {trend['competition']}",
                    f"Маржа: {trend['margin_potential']}",
                    f"Риски: {trend['risks']}",
                    f"Рекомендуемый тест: {trend['first_test']}",
                ]
            )
        )
    return "\n\n".join(blocks)


def main():
    now = datetime.now(KYIV)
    today = now.date()
    history = load_history()
    recent = recent_history(history, today, DEDUP_DAYS)
    recent_items = [entry.get("trend", {}).get("item", "") for entry in recent]
    live_signals = fetch_live_signals()
    trends = get_trends(recent_items, live_signals)

    daily_blocks = [f"Trend Radar — {today.strftime('%d.%m.%Y')}", "8 товарных трендов на сегодня"]
    for index, trend in enumerate(trends, start=1):
        send_sheet_row(sheet_payload(today, trend))
        daily_blocks.append(format_trend(index, trend))
    daily_blocks.append("Сохранено в Google Sheets: 8 строк")
    send_telegram("\n\n".join(daily_blocks))

    history.extend({"date": today.isoformat(), "trend": trend} for trend in trends)
    history = recent_history(history, today, HISTORY_DAYS)

    if now.weekday() == 5:
        send_telegram(build_weekly_digest(history, today))

    save_history(history)
    print(
        json.dumps(
            {
                "date": today.isoformat(),
                "daily_trends": len(trends),
                "weekly_digest": now.weekday() == 5,
                "history_entries": len(history),
                "live_signals": len(live_signals),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
