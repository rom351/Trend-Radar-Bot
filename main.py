import os
import json
from datetime import datetime, timezone

import requests


GROQ_API_KEY = os.environ["GROQ_API_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
GOOGLE_SHEETS_WEBHOOK_URL = os.environ["GOOGLE_SHEETS_WEBHOOK_URL"]


PROMPT = """
Сделай утренний тренд-дайджест на русском языке.

Тема:
- трендовые товары
- бренды
- e-commerce
- маркетплейсы
- TikTok / соцсети
- Google Trends / поисковый спрос
- идеи для малого бизнеса, рекламы, контента или перепродажи

Важно:
- пиши только на русском языке
- выбери 8 пунктов
- не выдумывай точные продажи
- если нет точных продаж, пиши: сигнал спроса, поисковый интерес, упоминания или обсуждения
- не используй переносы строк внутри значений JSON

Верни строго JSON object такого вида:

{
  "trends": [
    {
      "category": "категория",
      "item": "товар или бренд",
      "reason": "почему растёт",
      "source": "источник сигнала",
      "strength": "низкая / средняя / высокая",
      "action": "идея действия",
      "link": "ссылка или пустая строка"
    }
  ]
}
"""


def ask_groq():
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
                    "content": PROMPT,
                },
            ],
            "temperature": 0.2,
            "max_tokens": 2500,
            "response_format": {"type": "json_object"},
        },
        timeout=60,
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


def main():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    groq_text = ask_groq()
    trends = parse_trends(groq_text)

    message_parts = [
        "Trend Radar Bot",
        "Утренний дайджест трендов",
        "",
    ]

    saved_rows = 0

    for index, trend in enumerate(trends, start=1):
        category = trend.get("category", "")
        item = trend.get("item", "")
        reason = trend.get("reason", "")
        source = trend.get("source", "")
        strength = trend.get("strength", "")
        action = trend.get("action", "")
        link = trend.get("link", "")

        message_parts.append(f"{index}. {item}")
        message_parts.append(f"Категория: {category}")
        message_parts.append(f"Почему растёт: {reason}")
        message_parts.append(f"Сигнал: {source}")
        message_parts.append(f"Сила: {strength}")
        message_parts.append(f"Идея: {action}")

        if link:
            message_parts.append(link)

        message_parts.append("")

        send_sheet_row(
            {
                "date": today,
                "category": category,
                "item": item,
                "reason": reason,
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
