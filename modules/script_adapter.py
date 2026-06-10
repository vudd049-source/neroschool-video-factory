import os
import sys
import json
import random
import requests
import time
import gc

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.config import OPENROUTER_API_KEY, OPENROUTER_MODEL
from modules.logger import info, warn, error, ok, debug

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "cache")

TOPICS_POOL = [
    "Как нейросети пишут музыку",
    "Может ли AI заменить учителя",
    "Как ChatGPT понимает вопросы",
    "Что такое нейронные сети простыми словами",
    "Как AI учится рисовать",
    "Почему AI не заменит друзей",
    "Как нейросети помогают врачам",
    "Что такое промпт-инжиниринг",
    "Как AI переводит языки",
    "Может ли AI чувствовать эмоции",
    "Как работают рекомендации в TikTok",
    "Что такое deep learning",
    "Как AI распознаёт лица",
    "Зачем нейросетям математика",
    "Как создать своего AI-ассистента",
    "Что такое машинное обучение",
    "Как AI играет в шахматы",
    "Почему AI ошибается",
    "Как AI понимает картинки",
    "Что такое Vibe Coding",
    "Как написать промпт для нейросети",
    "Как AI предсказывает погоду",
    "Зачем нужны данные для AI",
    "Как работает автопилот в машинах",
    "Может ли AI написать книгу",
    "Как AI сортирует спам",
    "Что такое искусственный интеллект",
    "Как AI учится на ошибках",
    "Как AI генерирует видео",
    "Зачем нейросетям GPU",
    "Как AI понимает голос",
    "Что такое токены в AI",
    "Как тренируют нейросети",
    "Почему AI иногда врёт",
    "Что такое распознавание образов",
    "Как AI делает переводчики",
    "Как AI помогает в науке",
    "Что такое Big Data",
    "Как работает Midjourney",
    "Что такое алгоритм в программировании",
]

SYSTEM_PROMPT = """Ты — сценарист образовательных видео о нейросетях и AI для детей 10-17 лет.
Правила:
1. Каждый сценарий — 3-4 кадра, разделённых |||
2. Формат: текст на экране ||| текст для озвучки (voice_text)
3. В hook_text — шок/вопрос/противоречие (1 короткое предложение, 4-8 слов)
4. В body_text — РАЗВЁРНУТОЕ объяснение. КАЖДАЯ часть body_text = 2-3 предложения. Пиши детально, с примерами, аналогиями.
5. В cta_text — призыв (1 предложение, 3-6 слов)
6. voice_text должен быть длинным — каждая часть озвучки 10-20 секунд
7. Без сложных терминов. Без воды. Язык — русский.
8. Категории: ai_for_kids, prompt_engineering, vibe_coding, bot_creation
9. Не используй смайлики и эмодзи

Формат ответа (строго JSON):
{
  "category": "ai_for_kids",
  "topic": "Короткая тема",
  "hook_text": "Текст крючка на экране (4-8 слов)",
  "hook_voice_text": "Текст для озвучки крючка (1 предложение)",
  "body_text": "Первая часть объяснения, 2-3 предложения ||| Вторая часть объяснения, 2-3 предложения ||| Третья часть (если есть)",
  "body_voice_text": "Текст для озвучки первой части, подробно ||| Текст для озвучки второй части ||| Текст для озвучки третьей части",
  "cta_text": "Призыв на экране (3-6 слов)",
  "cta_voice_text": "Текст для озвучки CTA (1 предложение)"
}

ВАЖНО: body_text и body_voice_text разделены на части символом |||.
Каждая часть body_text должна быть 2-3 предложения (не 1!).
Количество частей = 2 для формата A (миф), 3 для B (детектив), 3 для D (топ-N).
"""


def call_llm(prompt, topic, format_code="A"):
    parts_count = {"A": 2, "B": 3, "D": 3}.get(format_code, 2)
    system = SYSTEM_PROMPT.replace("2 части", f"{parts_count} части")
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Напиши сценарий для формата {format_code} на тему: {topic}"},
    ]

    api_key = OPENROUTER_API_KEY
    base_url = "https://openrouter.ai/api/v1/chat/completions"
    model = OPENROUTER_MODEL

    for attempt in range(2):
        try:
            payload = {
                "model": model,
                "messages": messages,
                "temperature": 0.8,
                "max_tokens": 1000,
            }
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            resp = requests.post(base_url, headers=headers, json=payload, timeout=60)
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                content = content.strip()
                if content.startswith("```"):
                    content = content.split("\n", 1)[1]
                    content = content.rsplit("```", 1)[0]
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    import re
                    m = re.search(r'\{.*\}', content, re.DOTALL)
                    if m:
                        return json.loads(m.group())
                    warn("LLM ответ не JSON: %s", content[:100])
            else:
                warn("LLM API %d: %s", resp.status_code, resp.text[:100])
        except Exception as e:
            warn("Ошибка LLM (%s): %s", model, e)

    raise RuntimeError("OpenRouter не ответил")


def get_script(topic=None, format_code="A"):
    if not topic:
        topic = random.choice(TOPICS_POOL)
    info("Генерация сценария: \"%s\" [%s]", topic, format_code)
    try:
        result = call_llm(None, topic, format_code)
        result["format"] = format_code
        ok("Сценарий получен: %s", result.get("topic", topic))
        return result
    except Exception as e:
        error("Не удалось получить сценарий: %s", e)
        return _get_fallback_script(format_code)


def _get_fallback_script(format_code):
    topic = random.choice(TOPICS_POOL)
    return {
        "category": "ai_for_kids",
        "topic": topic,
        "hook_text": "А ты знал?",
        "hook_voice_text": f"А ты знал, что {topic.lower()}?",
        "body_text": "Это работает так ||| Попробуй сам",
        "body_voice_text": f"Вот как это работает. {topic} — это увлекательно. ||| Попробуй сам создать свою нейросеть в NeroSchool.",
        "cta_text": "Узнай в NeroSchool",
        "cta_voice_text": "Хочешь научиться создавать нейросети? Приходи в NeroSchool!",
        "format": format_code,
    }
