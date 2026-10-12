import os
import json
from datetime import datetime, timezone

import requests


GROQ_API_KEY = os.environ["GROQ_API_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
GOOGLE_SHEETS_WEBHOOK_URL = os.environ["GOOGLE_SHEETS_WEBHOOK_URL"]


PROMPT = """
Ты Trend Radar Bot.

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
- выбери 8-12 пунктов
- не выдумывай точные продажи
- если нет точных продаж, пиши "сигнал спроса", "поисковый интерес", "упоминания", "обсуждения"
- формат должен быть коротким и удобным для Telegram

Для каждого пункта дай:
1. Категория
2. Товар или бренд
3. Почему растёт
4. Источник сигнала
5. Сила тренда: низкая / средняя / высокая
6. Идея действия
7. Ссылка, если можешь дать

Верни результат строго в JSON-массиве.
Каждый элемент:
{
  "category": "...",
  "item": "...",
  "reason": "...",
  "source": "...",
  "strength": "...",
  "action": "...",
  "link": "..."
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
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {
                    "role": "system",
                    "content": "Ты русскоязычный аналитик трендов товаров, брендов и e-commerce.",
                },
                {
                    "role": "user",
                    "content": PROMPT,
                },
            ],
            "temperature": 0.4,
            "max_tokens": 2500,
        },
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]


def parse_json(text):
    text = text.strip()

    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    start = text.find("[")
    end = text.rfind("]")

    if start != -1 and end != -1:
        text = text[start : end + 1]

    return json.loads(text)


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
    trends = parse_json(groq_text)

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
        if category:
            message_parts.append(f"Категория: {category}")
        if reason:
            message_parts.append(f"Почему растёт: {reason}")
        if source:
            message_parts.append(f"Сигнал: {source}")
        if strength:
            message_parts.append(f"Сила: {strength}")
        if action:
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
