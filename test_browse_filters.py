import unittest
from browse_filters import BrowseCatalogue


class FakeAPI:
    def __init__(self):
        self.calls = []
        self.response = {'items': [], 'pager': {'hasMore': False}}

    def request(self, path, body):
        self.calls.append((path, body))
        return self.response


class CatalogueTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeAPI()
        self.catalogue = BrowseCatalogue(self.api)

    def test_movies_and_shows_request_their_own_live_channels(self):
        self.catalogue.page('movies')
        self.catalogue.page('series')
        self.assertEqual([call[0] for call in self.api.calls], ['/subject/filter'] * 2)
        self.assertEqual([call[1]['channelId'] for call in self.api.calls], [1, 2])

    def test_action_country_year_language_sort_and_rating_reach_backend(self):
        query = {'genre': 'Action', 'country': 'India', 'year': '2024',
                 'classify': 'Hindi dub', 'sort': 'Rating', 'rate': '8'}
        self.catalogue.page('movies', query, 3)
        body = self.api.calls[0][1]
        self.assertEqual({key: body[key] for key in query if key != 'rate'},
                         {key: value for key, value in query.items() if key != 'rate'})
        self.assertEqual(body['rate'], ['8', '10'])
        self.assertEqual(body['page'], 3)

    def test_service_next_page_and_has_more_are_used_not_placeholder_total(self):
        self.api.response = {'items': [], 'pager': {'hasMore': True, 'nextPage': '4', 'totalCount': 1000000}}
        result = self.catalogue.page('series', page=3)
        self.assertTrue(result['has_more'])
        self.assertEqual(result['next_page'], 4)
        self.api.response['pager']['hasMore'] = False
        self.assertFalse(self.catalogue.page('series', page=3)['has_more'])

    def test_channels_never_render_other_content_type_or_duplicate_ids(self):
        self.api.response = {'items': [
            {'subjectId': 'movie', 'subjectType': 1, 'title': 'Movie'},
            {'subjectId': 'tv', 'subjectType': 2, 'title': 'Show'},
            {'subjectId': 'tv', 'subjectType': 2, 'title': 'Duplicate'},
            {'subjectType': 2, 'title': 'Missing identity'}], 'pager': {}}
        self.assertEqual([item['subjectId'] for item in self.catalogue.page('series')['items']], ['tv'])

    def test_filter_values_come_from_verified_service_schema(self):
        choices = self.catalogue.options('movies')
        self.assertIn('Action', [item['value'] for item in choices['genre']])
        self.assertIn('2024', [item['value'] for item in choices['year']])
        choices['genre'].clear()
        self.assertTrue(self.catalogue.options('movies')['genre'])

    def test_all_filters_can_be_reset_without_sending_literal_all(self):
        values = {field: choices[0]['value'] for field, choices in self.catalogue.options('movies').items()}
        body = self.catalogue.body('movies', values)
        self.assertNotIn('All', body.values())
        self.assertEqual(body['sort'], 'ForYou')

    def test_invalid_selection_is_not_silently_treated_as_a_real_filter(self):
        for selection in ({'country': 'Unknown invented country'}, {'bad': 'Action'}, {'rate': '99'}):
            with self.assertRaises(ValueError):
                self.catalogue.page('movies', selection)
        self.assertFalse(self.api.calls)

    def test_invalid_channel_page_and_response_fail_clearly(self):
        with self.assertRaises(ValueError):
            self.catalogue.body('other')
        with self.assertRaises(ValueError):
            self.catalogue.body('movies', page=0)
        self.api.response = {'message': 'Not a catalogue'}
        with self.assertRaisesRegex(ValueError, 'invalid catalogue'):
            self.catalogue.page('movies')


if __name__ == '__main__':
    unittest.main()
