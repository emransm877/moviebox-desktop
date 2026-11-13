"""Load metadata only for a bounded, shuffled latest movies/TV carousel."""
import random
from browse_filters import BrowseCatalogue

def latest_titles(api, limit=100, rng=None):
    backend = BrowseCatalogue(api)
    items, seen = [], set()
    for kind in ('movies', 'series'):
        page, count = 1, 0
        quota = (limit + 1) // 2 if kind == 'movies' else limit // 2
        for _ in range(5):
            try:
                result = backend.page(kind, {'sort': 'Latest'}, page)
            except Exception:
                break
            added = 0
            for subject in result['items']:
                identity = str(subject['subjectId'])
                if identity not in seen:
                    seen.add(identity); items.append(subject); count += 1; added += 1
                if count >= quota:
                    break
            if count >= quota or not added or not result['has_more']:
                break
            page = result['next_page']
    (rng or random.SystemRandom()).shuffle(items)
    return items[:limit]
