from __future__ import annotations

from datetime import datetime

import httpx

from app.core.config import get_settings
from app.models.user import User


DEFAULT_SYSTEM_PROMPT = """
Ты EcoIZ AI, умный помощник внутри мобильного приложения EcoIZ.

Твоя задача:
- отвечать пользователю коротко, ясно и по факту;
- понимать обычные вопросы пользователя, а не только вопросы про экологию;
- если вопрос про экопривычки, мотивацию, день, цели или повседневные решения, помогать практично;
- если вопрос общий, отвечать как нормальный полезный ассистент;
- использовать контекст пользователя только когда он реально помогает ответу.

Правила ответа:
- отвечай только на русском языке;
- не выдумывай факты;
- не повторяй шаблонные eco-фразы без причины;
- не уходи в длинные рассуждения;
- не пиши слишком формально;
- если ответа точно не знаешь, честно скажи об этом и дай осторожный полезный ориентир;
- если вопрос широкий, сначала дай прямой ответ, потом 1-3 коротких шага;
- если пользователь спрашивает "что делать", дай конкретные действия;
- если пользовательу нужна поддержка, поддержи спокойно, но без лишней воды.

Стиль:
- коротко;
- понятно;
- по делу;
- дружелюбно;
- без канцелярита.

Формат:
- обычно 1-4 предложения;
- при необходимости короткий список из 2-3 пунктов;
- никаких длинных вступлений.
""".strip()


def _fallback_response(text: str) -> str:
    lowercase = text.lower()
    if any(word in lowercase for word in ("привет", "здрав", "hello", "hi")):
        return "Привет. Могу помочь коротко и по делу: с экопривычками, планом на день или обычными вопросами."
    if "что делать сегодня" in lowercase or "что мне делать сегодня" in lowercase:
        return "На сегодня начни с трех простых шагов: короткий душ, многоразовая сумка и выключать лишний свет. Это легко выполнить за один день."
    if "вод" in lowercase:
        return "Начни с двух вещей: 5-минутный душ и не оставляй воду включенной без надобности. Это самые простые и заметные шаги."
    if "транспорт" in lowercase or "машин" in lowercase:
        return "Если можешь, замени хотя бы 2-3 поездки в неделю на метро, автобус или пешую ходьбу. Это уже даст заметный эффект."
    if "мотивац" in lowercase or "сложно" in lowercase:
        return "Не пытайся менять всё сразу. Выбери одно маленькое действие на сегодня и держи регулярность."
    if any(word in lowercase for word in ("как", "почему", "зачем", "что")):
        return "Если коротко: начни с самого простого практического шага, который можно сделать сегодня. Если хочешь, уточни вопрос, и я отвечу точнее."
    return "Напиши вопрос чуть точнее, и я отвечу коротко и по делу."


def _fmt_dt(value: datetime) -> str:
    return value.strftime("%Y-%m-%d")


def _activities_summary(user: User, limit: int) -> str:
    activities = sorted(user.activities, key=lambda item: item.created_at, reverse=True)[:limit]
    if not activities:
        return "Нет записанных активностей."
    return "\n".join(
        f"- {_fmt_dt(item.created_at)} | {item.title} | категория: {item.category} | "
        f"баллы: {item.points} | co2Saved: {item.co2_saved}"
        for item in activities
    )


def _challenges_summary(user: User, limit: int) -> str:
    items = sorted(
        user.user_challenges,
        key=lambda item: (item.is_completed, item.challenge.title),
    )[:limit]
    if not items:
        return "Нет челленджей."
    lines: list[str] = []
    for item in items:
        status = "completed" if item.is_completed else "active"
        lines.append(
            f"- {item.challenge.title} | {item.current_count}/{item.challenge.target_count} | "
            f"status: {status} | reward: {item.challenge.reward_points}"
        )
    return "\n".join(lines)


def _posts_summary(user: User, limit: int) -> str:
    posts = sorted(user.posts, key=lambda item: item.created_at, reverse=True)[:limit]
    if not posts:
        return "Нет постов."
    return "\n".join(
        f"- {_fmt_dt(item.created_at)} | {item.text[:120]}"
        for item in posts
    )


def _chat_summary(user: User, limit: int) -> str:
    messages = sorted(user.chat_messages, key=lambda item: item.created_at)[-limit:]
    if not messages:
        return "История чата пустая."
    return "\n".join(
        f"{'User' if item.role == 'user' else 'Assistant'}: {item.text}"
        for item in messages
    )


def _build_prompt(user: User, text: str) -> str:
    display_name = user.full_name.strip() or user.username
    return f"""
Пользователь:
- name: {display_name}
- username: {user.username}
- points: {user.points}
- streakDays: {user.streak_days}
- co2SavedTotal: {user.co2_saved_total}

Последние активности:
{_activities_summary(user, 6)}

Челленджи:
{_challenges_summary(user, 5)}

Последние посты:
{_posts_summary(user, 3)}

История диалога:
{_chat_summary(user, 8)}

Сообщение пользователя:
{text.strip()}
""".strip()


def _conversation_messages(user: User, text: str, history_limit: int) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [
        {"role": "system", "content": DEFAULT_SYSTEM_PROMPT},
        {
            "role": "system",
            "content": (
                "Ниже контекст пользователя EcoIZ. Используй его только как вспомогательный персональный контекст. "
                "Не перечисляй всё подряд, если это не помогает ответу.\n\n"
                f"{_build_prompt(user, text)}"
            ),
        },
    ]

    history = sorted(user.chat_messages, key=lambda item: item.created_at)[-history_limit:]
    for item in history:
        if not item.text.strip():
            continue
        role = "assistant" if item.role == "assistant" else "user"
        messages.append({"role": role, "content": item.text.strip()})

    messages.append({"role": "user", "content": text.strip()})
    return messages


def _openrouter_response(messages: list[dict[str, str]]) -> str | None:
    settings = get_settings()
    if not settings.openrouter_api_key:
        return None

    response = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.openrouter_model,
            "messages": messages,
            "temperature": settings.ai_temperature,
            "max_tokens": settings.ai_max_tokens,
        },
        timeout=settings.ai_timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()
    content = payload["choices"][0]["message"]["content"].strip()
    return content or None


def _openai_response(messages: list[dict[str, str]]) -> str | None:
    settings = get_settings()
    if not settings.openai_api_key:
        return None

    response = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.openai_model,
            "messages": messages,
            "temperature": settings.ai_temperature,
            "max_tokens": settings.ai_max_tokens,
        },
        timeout=settings.ai_timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()
    content = payload["choices"][0]["message"]["content"].strip()
    return content or None


def ai_response(text: str, user: User) -> str:
    settings = get_settings()
    messages = _conversation_messages(user, text, settings.ai_history_limit)

    if settings.ai_provider == "openrouter" and not settings.openrouter_api_key:
        return _fallback_response(text)
    if settings.ai_provider == "openai" and not settings.openai_api_key:
        return _fallback_response(text)

    try:
        if settings.ai_provider == "openai":
            content = _openai_response(messages)
        else:
            content = _openrouter_response(messages)
        return content or _fallback_response(text)
    except Exception:
        return _fallback_response(text)
