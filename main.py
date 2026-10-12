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
Найти конкретные коммерчески интересные сигналы, которые можно проверить в e-commerce, контенте, рекламе, перепродаже или ассортименте.

Ищи:
- трендовые товары
- товарные категории
- реальные бренды
- ниши на маркетплейсах
- TikTok / Instagram / YouTube / Pinterest сигналы
- Google Trends / поисковый спрос
- идеи для малого бизнеса, рекламы, контента или перепродажи

Строгие правила:
- Пиши только на русском языке.
- Дай ровно 8 пунктов.
- Каждый пункт должен быть конкретным товаром, нишей или реальным брендом.
- Не выдумывай бренды.
- Если не уверен в бренде, пиши категорию товара.
- Не пиши абстрактные названия вроде ShopLocal, EcoWear, LocalMarket, если это не реальный известный бренд.
- Не пиши общие пункты вроде "локальные товары", "здоровый образ жизни", "переезд", "маркетплейсы", "соцсети".
- Не выдумывай точные продажи, выручку, проценты и рейтинги.
- Если нет точных продаж, используй формулировки: "сигнал спроса", "поисковый интерес", "упоминания", "обсуждения", "рост внимания".
- Не повторяй одну и ту же причину во всех пунктах. Избегай шаблонов.
- Не пиши везде "проверить сертификаты". Сертификаты упоминай только там, где это реально важно: косметика, еда, электроника, детские товары.
- Для каждого пункта дай 2-4 конкретных примера брендов, товаров, площадок или похожих продуктов.
- Добавь конкретные поисковые запросы, которые можно вручную проверить в Google, Amazon, TikTok, YouTube или маркетплейсах.
- Добавь первый простой тест на 10-20 минут.
- Оцени коммерческий потенциал: низкий / средний / высокий.
- Оцени сложность входа: низкая / средняя / высокая.
- Добавь, что проверить перед вложениями.
- Не используй переносы строк внутри значений JSON.

Хорошие примеры:
- "AI glasses / умные очки", примеры: Ray-Ban Meta, Brilliant Labs Frame, Solos
- "корейские SPF-стики", примеры: Beauty of Joseon, Round Lab, Tocobo
- "умные кольца", примеры: Oura Ring, Samsung Galaxy Ring, Ultrahuman Ring
- "портативные блендеры", примеры: BlendJet, Ninja Blast, аналоги на Amazon
- "органайзеры для дома", примеры: clear storage bins, drawer organizers, vacuum bags
- "мини-принтеры для наклеек", примеры: Phomemo, Nelko, JADENS
- "pet camera / камеры для питомцев", примеры: Furbo, Eufy Pet Camera, Petcube
- "travel compression bags", примеры: vacuum travel bags, packing cubes, compression organizers

Плохие примеры:
- "ShopLocal"
- "EcoWear"
- "переезд в город"
- "локальные товары"
- "соцсети растут"
- "маркетплейсы развиваются"
- "здоровый образ жизни"

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
            "max_tokens": 4000,
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
        search_queries = trend.get("search_queries", "")
        first_test = trend.get("first_test", "")
        commercial_potential = trend.get("commercial_potential", "")
        entry_difficulty = trend.get("entry_difficulty", "")
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

        if search_queries:
            message_parts.append(f"Что искать: {search_queries}")

        if first_test:
            message_parts.append(f"Первый тест: {first_test}")

        if commercial_potential:
            message_parts.append(f"Потенциал: {commercial_potential}")

        if entry_difficulty:
            message_parts.append(f"Сложность входа: {entry_difficulty}")

        if strength:
            message_parts.append(f"Сила сигнала: {strength}")

        if action:
            message_parts.append(f"Идея: {action}")

        if check:
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
