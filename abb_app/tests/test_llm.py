import json

from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase, override_settings

from abb_app.services import llm
from abb_app.services.llm import generate_abbreviation_description


class GenerateDescriptionViewTests(TestCase):
    def setUp(self):
        session = self.client.session
        session['doc_abbs'] = [{
            'abbreviation': 'T4',
            'contexts': [
                'Первый фрагмент T4.',
                'Второй фрагмент T4.',
                'Третий фрагмент T4.',
                'Четвёртый фрагмент T4.',
            ],
        }]
        session.save()

    @patch('abb_app.views.generate_abbreviation_description')
    def test_uses_only_contexts_stored_in_session(self, generate):
        generate.return_value = 'тироксин'

        response = self.client.post(
            '/generate_description/',
            data=json.dumps({
                'abbreviation': 'T4',
                'confirmed': True,
                'context_limit': 3,
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        generate.assert_called_once_with(
            abbreviation='T4',
            contexts=[
                'Первый фрагмент T4.',
                'Второй фрагмент T4.',
                'Третий фрагмент T4.',
            ],
        )

    @patch('abb_app.views.generate_abbreviation_description')
    def test_rejects_untrusted_or_unconfirmed_requests(self, generate):
        payloads = [
            {
                'abbreviation': 'T4',
                'confirmed': True,
                'context': 'Этот текст не должен быть принят.',
            },
            {'abbreviation': 'T4'},
        ]

        for payload in payloads:
            with self.subTest(payload=payload):
                response = self.client.post(
                    '/generate_description/',
                    data=json.dumps(payload),
                    content_type='application/json',
                )
                self.assertEqual(response.status_code, 400)

        generate.assert_not_called()


class GigaChatServiceTests(SimpleTestCase):
    def setUp(self):
        llm._access_token = None
        llm._access_token_expires_at = 0.0

    @override_settings(
        GIGACHAT_CREDENTIALS='test-key',
        GIGACHAT_MODEL='GigaChat-3-Ultra',
        GIGACHAT_SCOPE='GIGACHAT_API_PERS',
        GIGACHAT_CA_BUNDLE='/tmp/gigachat-ca.pem',
    )
    @patch('abb_app.services.llm.requests.post')
    def test_sends_context_and_reuses_access_token(self, post):
        token_response = Mock()
        token_response.raise_for_status.return_value = None
        token_response.json.return_value = {
            'access_token': 'access-token',
            'expires_at': 4_000_000_000_000,
        }

        chat_response = Mock()
        chat_response.raise_for_status.return_value = None
        chat_response.json.return_value = {
            'choices': [{
                'message': {
                    'content': '{"description":"тироксин"}',
                },
            }],
        }
        post.side_effect = [token_response, chat_response, chat_response]

        contexts = [
            'Первый фрагмент T4.',
            'Второй фрагмент T4.',
        ]
        first = generate_abbreviation_description('T4', contexts)
        second = generate_abbreviation_description('T4', ['Другой T4.'])

        self.assertEqual(first, 'тироксин')
        self.assertEqual(second, 'тироксин')
        self.assertEqual(post.call_count, 3)

        auth_call, first_chat_call, second_chat_call = post.call_args_list
        self.assertEqual(auth_call.args[0], llm.GIGACHAT_AUTH_URL)
        self.assertEqual(
            auth_call.kwargs['headers']['Authorization'],
            'Basic test-key',
        )
        self.assertEqual(
            auth_call.kwargs['data']['scope'],
            'GIGACHAT_API_PERS',
        )
        self.assertEqual(
            auth_call.kwargs['verify'],
            '/tmp/gigachat-ca.pem',
        )

        self.assertEqual(first_chat_call.args[0], llm.GIGACHAT_CHAT_URL)
        self.assertEqual(second_chat_call.args[0], llm.GIGACHAT_CHAT_URL)
        self.assertEqual(
            first_chat_call.kwargs['headers']['Authorization'],
            'Bearer access-token',
        )
        payload = first_chat_call.kwargs['json']
        prompt = payload['messages'][0]['content']
        self.assertIn(json.dumps(contexts, ensure_ascii=False), prompt)
        self.assertEqual(payload['model'], 'GigaChat-3-Ultra')
        self.assertTrue(payload['response_format']['strict'])
        self.assertEqual(
            payload['response_format']['type'],
            'json_schema',
        )
