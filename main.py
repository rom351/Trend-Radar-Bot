import os
import json
from datetime import datetime, timezone

import requests


GROQ_API_KEY = os.environ["GROQ_API_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
GOOGLE_SHEETS_WEBHOOK_URL = os.environ["GOOGLE_SHEETS_WEBHOOK_URL"]


BASE_RULES = """
Ты Trend Radar Bot — русскоязычный аналитик трендов товаров, брендов, e-commerce и потребительского спроса.

Дай конкретные коммерчески интересные сигналы:
- трендовые товары
- товарные категории
- реальные бренды
- ниши на маркетплейсах
- TikTok / Instagram / YouTube / Pinterest сигналы
- Google Trends / поисковый спрос
- идеи для малого бизнеса, рекламы, контента или перепродажи

Строгие правила:
- Пиши только на русском языке.
- Каждый пункт должен быть конкретным товаром, нишей или реальным брендом.
- Не выдумывай бренды.
- Не пиши абстрактные названия вроде ShopLocal, EcoWear, LocalMarket.
- Не пиши общие пункты вроде "локальные товары", "здоровый образ жизни", "переезд", "маркетплейсы", "соцсети".
- Не выдумывай точные продажи, выручку, проценты и рейтинги.
- Если нет точных продаж, используй: "сигнал спроса", "поисковый интерес", "упоминания", "обсуждения", "рост внимания".
- Не повторяй одну и ту же причину во всех пунктах.
- Сертификаты упоминай только там, где это важно: косметика, еда, электроника, детские товары.
- Для каждого пункта дай 2-4 конкретных примера брендов, товаров, площадок или похожих продуктов.
- Добавь конкретные поисковые запросы для Google, Amazon, TikTok, YouTube или маркетплейсов.
- Добавь первый простой тест на 10-20 минут.
- Оцени коммерческий потенциал: низкий / средний / высокий.
- Оцени сложность входа: низкая / средняя / высокая.
- Добавь, что проверить перед вложениями.
- Не используй переносы строк внутри значений JSON.

Верни строго JSON object такого вида:

{
  "trends": [
    {
      "category": "категория",
      "item": "конкретный товар, бренд или ниша",
      "examples": "2-4 конкретных примера",
      "reason": "почему растёт",
      "source": "где виден сигнал",
      "search_queries": "2-4 конкретных запроса для проверки",
      "first_test": "простое действие на 10-20 минут",
      "commercial_potential": "низкий / средний / высокий",
      "entry_difficulty": "низкая / средняя / высокая",
      "strength": "низкая / средняя / высокая",
      "action": "практическая идея действия",
      "check": "что проверить перед вложениями",
      "link": "ссылка или пустая строка"
    }
  ]
}
"""


def build_prompt(count, exclude_items=None):
    exclude_text = ""
    if exclude_items:
        exclude_text = "Не повторяй эти пункты: " + ", ".join(exclude_items) + "."

    return f"""
Сделай утренний тренд-дайджест на русском языке.

Нужно дать ровно {count} разных трендов.
{exclude_text}

Хорошие направления:
- AI-гаджеты и носимые устройства
- beauty / skincare / SPF
- товары для дома и организации пространства
- fitness / wellness / sleep tech
- pet tech / товары для животных
- travel accessories
- kitchen gadgets
- creator economy tools
- детские товары, если есть понятный тренд
- недорогие товары для маркетплейсов

{BASE_RULES}
"""


def ask_groq(prompt):
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": "openai/gpt-oss-20b",
            "messages": [
                {
                    "role": "system",
                    "content": "Ты русскоязычный аналитик трендов товаров, брендов и e-commerce. Отвечай только валидным JSON.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            "temperature": 0.35,
            "max_tokens": 8000,
            "response_format": {"type": "json_object"},
        },
        timeout=90,
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]


def parse_trends(text):
    data = json.loads(text)
    trends = data.get("trends", [])
    if not isinstance(trends, list):
        return []
    return trends


def get_trends():
    trends = parse_trends(ask_groq(build_prompt(10)))

    if len(trends) < 8:
        existing_items = [trend.get("item", "") for trend in trends if trend.get("item")]
        missing_count = 10 - len(trends)
        more_trends = parse_trends(ask_groq(build_prompt(missing_count, existing_items)))
        trends.extend(more_trends)

    return trends[:10]


def send_telegram(text):
    chunks = []
    current = ""

    for block in text.split("\n\n"):
        part = block + "\n\n"
        if len(current) + len(part) > 3800:
            chunks.append(current.strip())
            current = part
        else:
            current += part

    if current.strip():
        chunks.append(current.strip())

    for chunk in chunks:
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": chunk,
                "disable_web_page_preview": True,
            },
            timeout=30,
        )
        response.raise_for_status()


def send_sheet_row(row):
    response = requests.post(
        GOOGLE_SHEETS_WEBHOOK_URL,
        data=json.dumps(row, ensure_ascii=False),
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    response.raise_for_status()


def main():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    trends = get_trends()

    message_parts = [
        "Trend Radar Bot",
        "Утренний дайджест трендов",
        "",
    ]

    saved_rows = 0

    for index, trend in enumerate(trends, start=1):
        category = trend.get("category", "")
        item = trend.get("item", "")
        examples = trend.get("examples", "")
        reason = trend.get("reason", "")
        source = trend.get("source", "")
        search_queries = trend.get("search_queries", "")
        first_test = trend.get("first_test", "")
        commercial_potential = trend.get("commercial_potential", "")
        entry_difficulty = trend.get("entry_difficulty", "")
        strength = trend.get("strength", "")
        action = trend.get("action", "")
        check = trend.get("check", "")
        link = trend.get("link", "")

        message_parts.append(f"{index}. {item}")
        message_parts.append(f"Категория: {category}")
        message_parts.append(f"Примеры: {examples}")
        message_parts.append(f"Почему растёт: {reason}")
        message_parts.append(f"Сигнал: {source}")
        message_parts.append(f"Что искать: {search_queries}")
        message_parts.append(f"Первый тест: {first_test}")
        message_parts.append(f"Потенциал: {commercial_potential}")
        message_parts.append(f"Сложность входа: {entry_difficulty}")
        message_parts.append(f"Сила сигнала: {strength}")
        message_parts.append(f"Идея: {action}")
        message_parts.append(f"Проверить: {check}")

        if link:
            message_parts.append(link)

        message_parts.append("")

        sheet_reason = (
            f"Примеры: {examples}. "
            f"Почему растёт: {reason}. "
            f"Что искать: {search_queries}. "
            f"Первый тест: {first_test}. "
            f"Проверить: {check}."
        )

        send_sheet_row(
            {
                "date": today,
                "category": category,
                "item": item,
                "reason": sheet_reason,
                "source": source,
                "strength": strength,
                "action": action,
                "link": link,
                "status": "новое",
            }
        )

        saved_rows += 1

    message_parts.append(f"Сохранено в Google Sheets: {saved_rows} строк")
    send_telegram("\n".join(message_parts))


if __name__ == "__main__":
    main()
