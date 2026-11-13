"""Full-catalogue browsing with verified upstream filter values and pagination."""
import copy
from browse_filter_options import FILTER_OPTIONS

CHANNELS = {'movies': (1, 1), 'series': (2, 2)}
PAGE_SIZE = 24


class BrowseCatalogue:
    def __init__(self, api):
        self.api = api

    def options(self, kind):
        if kind not in CHANNELS:
            raise ValueError('Choose Movies or TV Shows')
        result = copy.deepcopy(FILTER_OPTIONS[kind])
        for option in result['sort']:
            if option['value'] == 'ForYou':
                option['label'] = 'For you'
        # The official mobile schema exposes a verified rating range of 0–10.
        result['rate'] = [{'label': 'Any rating', 'value': 'All'}] + [
            {'label': f'{value}+', 'value': str(value)} for value in (6, 7, 8, 9)
        ]
        return result

    def body(self, kind, selection=None, page=1):
        if kind not in CHANNELS:
            raise ValueError('Choose Movies or TV Shows')
        page = int(page)
        if page < 1 or page > 100000:
            raise ValueError('Invalid catalogue page')
        body = {'channelId': CHANNELS[kind][0], 'page': page, 'perPage': PAGE_SIZE}
        options = self.options(kind)
        for field, value in (selection or {}).items():
            if field not in options:
                raise ValueError('Unsupported catalogue filter')
            allowed = {option['value'] for option in options[field]}
            if value not in allowed:
                raise ValueError('Unsupported catalogue filter value')
            if value not in ('All', '', None):
                body[field] = [value, '10'] if field == 'rate' else value
        return body

    def page(self, kind, selection=None, page=1):
        body = self.body(kind, selection, page)
        result = self.api.request('/subject/filter', body)
        if not isinstance(result, dict) or not isinstance(result.get('items'), list):
            raise ValueError('MovieBox returned an invalid catalogue page')
        expected_type = CHANNELS[kind][1]
        items = []
        seen = set()
        for item in result['items']:
            if not isinstance(item, dict) or not item.get('subjectId') or not item.get('title'):
                continue
            try:
                subject_type = int(item.get('subjectType') or 0)
            except (ValueError, TypeError):
                continue
            identity = str(item['subjectId'])
            if subject_type != expected_type or identity in seen:
                continue
            seen.add(identity)
            items.append(item)
        pager = result.get('pager') or {}
        try:
            next_page = int(pager.get('nextPage') or body['page'] + 1)
        except (ValueError, TypeError):
            next_page = body['page'] + 1
        next_page = max(body['page'] + 1, next_page)
        has_more = pager.get('hasMore') in (True, 1, '1', 'true')
        return {'items': items, 'has_more': has_more, 'next_page': next_page}
