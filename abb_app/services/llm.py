import json
from typing import List

import requests
from django.conf import settings

GROQ_CHAT_URL = 'https://api.groq.com/openai/v1/chat/completions'
GROQ_TIMEOUT_SECONDS = 20


class LLMServiceError(Exception):
    pass


def generate_abbreviation_description(
    abbreviation: str,
    contexts: List[str],
) -> str:
    if not settings.GROQ_API_KEY:
        raise LLMServiceError('Groq API key is not configured')

    context_json = json.dumps(contexts, ensure_ascii=False)
    prompt = (
        'Задача: определить расшифровку медицинской или научной '
        'аббревиатуры только по приведенному контексту. '
        'Верни только саму расшифровку в поле description. '
        'Не объясняй ответ, не добавляй определения, комментарии, '
        'рекомендации или дополнительную информацию. '
        'Расшифровка должна быть максимально короткой и '
        'соответствовать буквам аббревиатуры. Если надежно определить '
        'ее нельзя, верни "не знаю".\n\n'
        f'Аббревиатура: {abbreviation}\n'
        'Фрагменты контекста в виде массива строк; текст каждого '
        'фрагмента передан без изменений:\n'
        f'{context_json}'
    )

    payload = {
        'model': settings.GROQ_MODEL,
        'reasoning_effort': 'low',
        'include_reasoning': False,
        'max_completion_tokens': 100,
        'messages': [
            {'role': 'user', 'content': prompt},
        ],
        'response_format': {
            'type': 'json_schema',
            'json_schema': {
                'name': 'abbreviation_description',
                'strict': True,
                'schema': {
                    'type': 'object',
                    'properties': {
                        'description': {'type': 'string'},
                    },
                    'required': ['description'],
                    'additionalProperties': False,
                },
            },
        },
    }

    try:
        response = requests.post(
            GROQ_CHAT_URL,
            headers={
                'Authorization': f'Bearer {settings.GROQ_API_KEY}',
                'Content-Type': 'application/json',
            },
            json=payload,
            timeout=GROQ_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        content = response.json()['choices'][0]['message']['content']
        description = json.loads(content)['description'].strip()
    except (
        requests.RequestException,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise LLMServiceError('AI service is unavailable') from exc

    if not description:
        raise LLMServiceError('AI service returned an empty response')

    return description
