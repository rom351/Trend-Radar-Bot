import os
import json
from datetime import datetime, timezone

import requests


GROQ_API_KEY = os.environ["GROQ_API_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
GOOGLE_SHEETS_WEBHOOK_URL = os.environ["GOOGLE_SHEETS_WEBHOOK_URL"]


PROMPT = """
Ты Trend Radar Bot — русскоязычный аналитик трендов товаров, брендов, e-commerce и потребительского спроса.

Сделай утренний тренд-дайджест на русском языке.

Цель:
Найти не абстрактные новости, а конкретные коммерчески интересные сигналы:
- трендовые товары
- товарные категории
- реальные бренды
- маркетплейс-сигналы
- TikTok / Instagram / YouTube / соцсети
- Google Trends / поисковый спрос
- идеи для малого бизнеса, рекламы, контента, теста спроса или перепродажи

Строгие правила:
- Пиши только на русском языке.
- Дай ровно 8 пунктов.
- Каждый пункт должен быть конкретным и понятным.
- Не выдумывай бренды. Если не уверен, пиши категорию товара, а не название бренда.
- Не используй абстрактные названия вроде ShopLocal, EcoWear, LocalMarket, если это не реальный известный бренд.
- Не пиши общие пункты вроде "переезд в город", "локальные товары", "здоровый образ жизни" без конкретного товара или ниши.
- Не выдумывай точные продажи, выручку или проценты.
- Если нет точных продаж, используй формулировки: "сигнал спроса", "поисковый интерес", "упоминания", "обсуждения", "рост внимания".
- Для каждого пункта обязательно дай 2-4 примера брендов, товаров, площадок или похожих продуктов. Если точных брендов нет, дай примеры форматов товара.
- Идея действия должна быть практической: что можно проверить, купить, протестировать, снять в контент, добавить в ассортимент или сравнить.
- Добавь поле "check": что проверить перед тем, как тратить деньги.
- Не используй переносы строк внутри значений JSON.

Хорошие примеры конкретики:
- "AI glasses / умные очки", примеры: Ray-Ban Meta, Brilliant Labs Frame, Solos
- "корейские солнцезащитные стики SPF", примеры: Beauty of Joseon, Round Lab, Tocobo
- "умные кольца", примеры: Oura Ring, Samsung Galaxy Ring, Ultrahuman Ring
- "портативные блендеры", примеры: BlendJet, Ninja Blast, аналоги на Amazon
- "товары для организации дома", примеры: clear storage bins, drawer organizers, vacuum bags

Плохие примеры, которые нельзя давать:
- "ShopLocal"
- "EcoWear"
- "переезд в город"
- "локальные товары"
- "соцсети растут"
- "маркетплейсы развиваются"

Верни строго JSON object такого вида:

{
  "trends": [
    {
      "category": "категория",
      "item": "конкретный товар, бренд или ниша",
      "examples": "2-4 конкретных примера",
      "reason": "почему растёт",
      "source": "где виден сигнал",
      "strength": "низкая / средняя / высокая",
      "action": "практическая идея действия",
      "check": "что проверить перед вложениями",
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
            "temperature": 0.25,
            "max_tokens": 3500,
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
        examples = trend.get("examples", "")
        reason = trend.get("reason", "")
        source = trend.get("source", "")
        strength = trend.get("strength", "")
        action = trend.get("action", "")
        check = trend.get("check", "")
        link = trend.get("link", "")

        message_parts.append(f"{index}. {item}")

        if category:
            message_parts.append(f"Категория: {category}")

        if examples:
            message_parts.append(f"Примеры: {examples}")

        if reason:
            message_parts.append(f"Почему растёт: {reason}")

        if source:
            message_parts.append(f"Сигнал: {source}")

        if strength:
            message_parts.append(f"Сила: {strength}")

        if action:
            message_parts.append(f"Идея: {action}")

        if check:
            message_parts.append(f"Проверить: {check}")

        if link:
            message_parts.append(link)

        message_parts.append("")

        send_sheet_row(
            {
                "date": today,
                "category": category,
                "item": item,
                "reason": f"Примеры: {examples}. {reason}. Проверить: {check}",
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
