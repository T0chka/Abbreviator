import json
import time
import uuid
from typing import List

import requests
from django.conf import settings

GIGACHAT_AUTH_URL = (
    'https://ngw.devices.sberbank.ru:9443/api/v2/oauth'
)
GIGACHAT_CHAT_URL = 'https://api.giga.chat/v1/chat/completions'
GIGACHAT_TIMEOUT_SECONDS = 20

_access_token = None
_access_token_expires_at = 0.0


class LLMServiceError(Exception):
    pass


def _get_access_token() -> str:
    global _access_token, _access_token_expires_at

    if _access_token and time.time() < _access_token_expires_at - 60:
        return _access_token

    response = requests.post(
        GIGACHAT_AUTH_URL,
        headers={
            'Authorization': f'Basic {settings.GIGACHAT_CREDENTIALS}',
            'RqUID': str(uuid.uuid4()),
            'Accept': 'application/json',
        },
        data={'scope': settings.GIGACHAT_SCOPE},
        timeout=GIGACHAT_TIMEOUT_SECONDS,
        verify=settings.GIGACHAT_CA_BUNDLE or True,
    )
    response.raise_for_status()
    data = response.json()

    token = data['access_token']
    expires_at = float(data['expires_at'])
    if expires_at > 10_000_000_000:
        expires_at /= 1000

    _access_token = token
    _access_token_expires_at = expires_at
    return token


def generate_abbreviation_description(
    abbreviation: str,
    contexts: List[str],
) -> str:
    if not settings.GIGACHAT_CREDENTIALS:
        raise LLMServiceError('GigaChat credentials are not configured')

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
        'model': settings.GIGACHAT_MODEL,
        'temperature': 0.1,
        'max_tokens': 100,
        'messages': [
            {'role': 'user', 'content': prompt},
        ],
        'response_format': {
            'type': 'json_schema',
            'schema': {
                'type': 'object',
                'properties': {
                    'description': {'type': 'string'},
                },
                'required': ['description'],
                'additionalProperties': False,
            },
            'strict': True,
        },
    }

    try:
        access_token = _get_access_token()
        response = requests.post(
            GIGACHAT_CHAT_URL,
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
            json=payload,
            timeout=GIGACHAT_TIMEOUT_SECONDS,
            verify=settings.GIGACHAT_CA_BUNDLE or True,
        )
        response.raise_for_status()
        content = response.json()['choices'][0]['message']['content']
        description = json.loads(content)['description'].strip()
    except (
        requests.RequestException,
        IndexError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise LLMServiceError('AI service is unavailable') from exc

    if not description:
        raise LLMServiceError('AI service returned an empty response')

    return description
