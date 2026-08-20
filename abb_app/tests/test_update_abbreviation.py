import json

from django.test import TestCase

from abb_app.models import AbbreviationEntry


class UpdateAbbreviationViewTests(TestCase):
    def setUp(self):
        session = self.client.session
        session['doc_abbs'] = [{
            'abbreviation': 'T4',
            'descriptions': [],
            'selected_description': None,
            'correct_form': None,
            'highlighted': None,
        }]
        session.save()

    def post_json(self, payload):
        return self.client.post(
            '/update_abbreviation/',
            data=json.dumps(payload),
            content_type='application/json',
        )

    def test_invalid_json_returns_400(self):
        response = self.client.post(
            '/update_abbreviation/',
            data='{',
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'Invalid JSON')

    def test_unknown_action_returns_400(self):
        response = self.post_json({
            'abbreviation': 'T4',
            'action': 'unknown',
        })

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'Invalid action')

    def test_repeated_custom_description_is_idempotent(self):
        payload = {
            'abbreviation': 'T4',
            'description': 'Thyroxine',
            'action': 'add',
        }

        first = self.post_json(payload)
        second = self.post_json(payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(
            AbbreviationEntry.objects.filter(
                abbreviation='T4',
                description='Thyroxine',
            ).count(),
            1,
        )
