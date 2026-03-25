from __future__ import annotations

from datetime import datetime

import httpx

from app.core.config import get_settings
from app.models.user import User


def _fallback_response(text: str) -> str:
    lowercase = text.lower()
    if "вод" in lowercase:
        return "Попробуй 5-минутный душ и проверь, нет ли протечек. Это дает стабильный эффект каждый день."
    if "транспорт" in lowercase or "машин" in lowercase:
        return "2-3 поездки в неделю на метро, автобусе или велосипеде уже заметно снижают личный след CO2."
    if "мотивац" in lowercase or "сложно" in lowercase:
        return "Сфокусируйся на серии: одно небольшое действие в день лучше, чем идеальный, но редкий рывок."
    return "Отличный вопрос. Держи ритм: выбери 1 активити из воды, 1 из энергии и 1 из пластика сегодня."


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
Ты EcoIZ AI assistant для экологического мобильного приложения.
Отвечай только на русском языке.
Отвечай коротко, практично, по делу и дружелюбно.
Не выдумывай данные и не обещай то, чего нет.
Если вопрос общий, давай 2-3 конкретных шага.
Если есть пользовательский контекст, используй его.

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


def ai_response(text: str, user: User) -> str:
    settings = get_settings()
    if not settings.openai_api_key:
        return _fallback_response(text)

    prompt = _build_prompt(user, text)

    try:
        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.openai_model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Ты персональный экологический ассистент EcoIZ. "
                            "Помогай пользователю формировать экопривычки, мотивируй, "
                            "давай короткие персональные советы на русском языке."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": settings.openai_temperature,
                "max_tokens": settings.openai_max_tokens,
            },
            timeout=settings.openai_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        content = payload["choices"][0]["message"]["content"].strip()
        return content or _fallback_response(text)
    except Exception:
        return _fallback_response(text)
