import json

from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase, override_settings

from abb_app.services.llm import generate_abbreviation_description


class GenerateDescriptionViewTests(TestCase):
    def setUp(self):
        session = self.client.session
        session['doc_abbs'] = [
            {
                'abbreviation': 'T4',
                'contexts': [
                    'Первый фрагмент T4.',
                    'Второй фрагмент T4.',
                ],
            },
        ]
        session.save()

    @patch('abb_app.views.generate_abbreviation_description')
    def test_uses_only_contexts_stored_in_session(self, generate):
        generate.return_value = 'тироксин'

        response = self.client.post(
            '/generate_description/',
            data=json.dumps({
                'abbreviation': 'T4',
                'confirmed': True,
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        generate.assert_called_once_with(
            abbreviation='T4',
            contexts=[
                'Первый фрагмент T4.',
                'Второй фрагмент T4.',
            ],
        )

    @patch('abb_app.views.generate_abbreviation_description')
    def test_rejects_context_sent_by_browser(self, generate):
        response = self.client.post(
            '/generate_description/',
            data=json.dumps({
                'abbreviation': 'T4',
                'confirmed': True,
                'context': 'Этот текст не должен быть принят.',
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        generate.assert_not_called()

    @patch('abb_app.views.generate_abbreviation_description')
    def test_requires_explicit_confirmation(self, generate):
        response = self.client.post(
            '/generate_description/',
            data=json.dumps({'abbreviation': 'T4'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        generate.assert_not_called()


class GroqServiceTests(SimpleTestCase):
    @override_settings(
        GROQ_API_KEY='test-key',
        GROQ_MODEL='openai/gpt-oss-120b',
    )
    @patch('abb_app.services.llm.requests.post')
    def test_sends_exact_context_strings_to_groq(self, post):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            'choices': [
                {
                    'message': {
                        'content': '{"description":"тироксин"}',
                    },
                },
            ],
        }
        post.return_value = response

        contexts = [
            'Первый фрагмент T4.',
            'Второй фрагмент T4.',
        ]
        result = generate_abbreviation_description('T4', contexts)

        self.assertEqual(result, 'тироксин')
        payload = post.call_args.kwargs['json']
        prompt = payload['messages'][0]['content']
        self.assertIn(
            json.dumps(contexts, ensure_ascii=False),
            prompt,
        )
        self.assertNotIn('filename', prompt.lower())
        self.assertEqual(
            payload['model'],
            'openai/gpt-oss-120b',
        )
        self.assertTrue(
            payload['response_format']['json_schema']['strict']
        )
