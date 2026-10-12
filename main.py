import os
import json
from datetime import datetime, timezone

import requests


TAVILY_API_KEY = os.environ["TAVILY_API_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
GOOGLE_SHEETS_WEBHOOK_URL = os.environ["GOOGLE_SHEETS_WEBHOOK_URL"]


QUERIES = [
    {
        "category": "Товары",
        "query": """
Найди трендовые потребительские товары за последние 24-48 часов.
Фокус: viral products, Amazon best sellers, TikTok products, gadgets, beauty, home, fitness, fashion.
Ответ на русском. Для каждого товара объясни, почему он растёт, где это видно, и дай ссылку.
""",
    },
    {
        "category": "Бренды",
        "query": """
Найди бренды, которые резко набирают популярность за последние 24-48 часов.
Фокус: consumer brands, fashion brands, beauty brands, tech brands, food brands, DTC brands.
Ответ на русском. Укажи причину роста и источники.
""",
    },
    {
        "category": "Google Trends",
        "query": """
Найди самые заметные Google Trends и поисковые тренды за последние сутки, связанные с товарами, покупками, брендами и e-commerce.
Ответ на русском. Объясни, какие из них могут быть коммерчески интересны.
""",
    },
    {
        "category": "Идеи",
        "query": """
На основе свежих трендов товаров и брендов найди идеи для малого бизнеса, контента, рекламы или перепродажи.
Ответ на русском. Для каждой идеи дай: товар или ниша, почему интересно, риск, первый простой тест.
""",
    },
]


def tavily_search(query):
    response = requests.post(
        "https://api.tavily.com/search",
        json={
            "api_key": TAVILY_API_KEY,
            "query": query,
            "search_depth": "advanced",
            "max_results": 5,
            "include_answer": True,
            "include_raw_content": False,
        },
        timeout=45,
    )
    response.raise_for_status()
    return response.json()


def send_telegram(text):
    response = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text[:4000],
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


def short_text(value, limit=350):
    value = (value or "").strip()
    if len(value) <= limit:
        return value
    return value[:limit].rsplit(" ", 1)[0] + "..."


def main():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    telegram_parts = [
        "Trend Radar Bot",
        "Утренний дайджест трендов",
        "",
        "Формат: 100% free / zero cost, с лимитами бесплатных сервисов.",
        "",
    ]

    saved_rows = 0

    for block in QUERIES:
        category = block["category"]
        data = tavily_search(block["query"])
        answer = data.get("answer", "").strip()
        results = data.get("results", [])

        telegram_parts.append(f"== {category} ==")

        if answer:
            telegram_parts.append(short_text(answer, 700))
            telegram_parts.append("")

        if not results:
            telegram_parts.append("Ничего заметного не найдено.")
            telegram_parts.append("")
            continue

        for index, item in enumerate(results, start=1):
            title = item.get("title") or "Без заголовка"
            url = item.get("url") or ""
            content = item.get("content") or ""

            reason = short_text(content, 450)
            source = "Tavily / web search"
            strength = "средняя"
            action = "Проверить спрос, цены, конкурентов и возможность теста"
            status = "новое"

            telegram_parts.append(f"{index}. {title}")
            if reason:
                telegram_parts.append(short_text(reason, 250))
            if url:
                telegram_parts.append(url)
            telegram_parts.append("")

            send_sheet_row(
                {
                    "date": today,
                    "category": category,
                    "item": title,
                    "reason": reason,
                    "source": source,
                    "strength": strength,
                    "action": action,
                    "link": url,
                    "status": status,
                }
            )
            saved_rows += 1

    telegram_parts.append(f"Сохранено в Google Sheets: {saved_rows} строк")

    send_telegram("\n".join(telegram_parts))


if __name__ == "__main__":
    main()
