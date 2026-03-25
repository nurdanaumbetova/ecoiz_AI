from __future__ import annotations

from datetime import datetime

import httpx

from app.core.config import get_settings
from app.models.user import User


DEFAULT_SYSTEM_PROMPT = """
Ты EcoIZ AI, умный и дружелюбный ассистент внутри мобильного приложения EcoIZ.

Ты должен отвечать как современный качественный AI-ассистент уровня ChatGPT:
- понимать любые вопросы пользователя, а не только про экологию;
- отвечать по-русски, естественно, внятно и по-человечески;
- быть полезным, конкретным и поддерживающим;
- помнить, что ты находишься внутри eco-приложения, поэтому, когда уместно, можешь мягко связывать советы с привычками, мотивацией, устойчивым образом жизни и личным прогрессом пользователя;
- не сводить каждый ответ к шаблонным eco-советам, если вопрос пользователя про другое;
- если пользователь просит объяснение, объясняй понятно;
- если пользователь просит план, давай план;
- если пользователь растерян, сначала поддержи, потом предложи следующий шаг;
- если вопрос личный, бытовой, учебный или общий, отвечай как обычный умный ассистент, а не как узкий бот;
- не выдумывай факты о пользователе, используй только тот контекст, который передан системой.

Формат:
- обычно 1 короткий абзац или 2-5 предложений;
- если полезно, давай список из 2-4 шагов;
- избегай однотипных повторов и одних и тех же фраз.
""".strip()


def _fallback_response(text: str) -> str:
    lowercase = text.lower()
    if any(word in lowercase for word in ("привет", "здрав", "hello", "hi")):
        return "Привет. Я рядом и могу помочь с любым вопросом: от экопривычек и мотивации до повседневных решений и планов."
    if "что делать сегодня" in lowercase or "что мне делать сегодня" in lowercase:
        return "На сегодня выбери 3 простых шага: короткий душ, отказаться от одноразового пакета и выключить лишний свет вечером. Это реалистично и поможет сохранить ритм."
    if "вод" in lowercase:
        return "Попробуй 5-минутный душ и проверь, нет ли протечек. Это дает стабильный эффект каждый день."
    if "транспорт" in lowercase or "машин" in lowercase:
        return "2-3 поездки в неделю на метро, автобусе или велосипеде уже заметно снижают личный след CO2."
    if "мотивац" in lowercase or "сложно" in lowercase:
        return "Сфокусируйся на серии: одно небольшое действие в день лучше, чем идеальный, но редкий рывок."
    if any(word in lowercase for word in ("как", "почему", "зачем", "что")):
        return "Могу помочь с этим. Если говорить коротко, начни с самого простого практического шага, который можно сделать сегодня, и потом постепенно усложняй."
    return "Я могу помочь с вопросами про привычки, мотивацию, планы на день и повседневные решения. Напиши чуть подробнее, и я отвечу точнее."


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


def ai_response(text: str, user: User) -> str:
    settings = get_settings()
    if not settings.openai_api_key:
        return _fallback_response(text)

    try:
        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.openai_model,
                "messages": _conversation_messages(user, text, settings.openai_history_limit),
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
