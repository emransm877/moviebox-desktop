"""Load metadata only for a bounded, shuffled latest movies/TV carousel."""
import random
import re
from urllib.parse import urlsplit
from artwork_layout import release_year
from browse_filters import BrowseCatalogue

LANGUAGES='Hindi|English|Tamil|Telugu|Bengali|Bangla|Kannada|Malayalam|Marathi|Punjabi|Urdu|Arabic|Spanish|French|Portuguese|Japanese|Korean|Chinese|Indonesian|Thai|Vietnamese|Turkish|Russian|German|Italian'
LANGUAGE_SUFFIX=re.compile(r'\s*\[(?:'+LANGUAGES+r')\]\s*$',re.IGNORECASE|re.ASCII)

def visual_keys(subject):
    """Metadata-only hero grouping; never change an ID, URL or catalogue row."""
    cover='';record=subject.get('cover') or {}
    try:
        parsed=urlsplit(record.get('url') or '')
        if parsed.path:cover=(parsed.hostname or '').lower()+'|'+parsed.path
    except (ValueError,TypeError,AttributeError):pass
    title=str(subject.get('title') or '').strip()
    while True:
        trimmed=LANGUAGE_SUFFIX.sub('',title).strip()
        if trimmed==title:break
        title=trimmed
    title=' '.join(title.lower().split());year=release_year(subject.get('releaseDate'))
    try:kind=int(subject.get('subjectType') or 0)
    except (ValueError,TypeError):kind=0
    base=(title,year,kind) if title and year and kind in (1,2) else None
    return cover,base

class HeroSelection:
    def __init__(self):self.ids=set();self.covers=set();self.titles=set()
    def accept(self,subject):
        if not isinstance(subject,dict):return False
        identity=str(subject.get('subjectId') or '')
        if not identity or identity in self.ids:return False
        cover,base=visual_keys(subject)
        if (cover and cover in self.covers) or (base and base in self.titles):return False
        self.ids.add(identity)
        if cover:self.covers.add(cover)
        if base:self.titles.add(base)
        return True

def unique_spotlights(subjects,limit=100):
    if limit<=0:return []
    selection=HeroSelection();items=[]
    for subject in subjects:
        if selection.accept(subject):items.append(subject)
        if len(items)>=limit:break
    return items

def retained_subjects(value):
    if isinstance(value,dict):
        if value.get('subjectId') and value.get('title') and value.get('subjectType') in (1,2):yield value
        for child in list(value.values()):yield from retained_subjects(child)
    elif isinstance(value,list):
        for child in value:yield from retained_subjects(child)

def latest_titles(api, limit=100, rng=None, retained=None):
    backend = BrowseCatalogue(api)
    limit=max(0,min(100,int(limit)))
    if not limit:return []
    items, selection = [], HeroSelection()
    for kind in ('movies', 'series'):
        page, count, page_ids = 1, 0, set()
        quota = (limit + 1) // 2 if kind == 'movies' else limit // 2
        if not quota:continue
        for _ in range(5):
            try:
                result = backend.page(kind, {'sort': 'Latest'}, page)
            except Exception:
                break
            identities={str(subject.get('subjectId')) for subject in result['items'] if subject.get('subjectId')}
            fresh=identities-page_ids;page_ids.update(identities)
            for subject in result['items']:
                if selection.accept(subject):
                    items.append(subject); count += 1
                if count >= quota:
                    break
            if count >= quota or not fresh or not result['has_more']:
                break
            page = result['next_page']
    # Existing public metadata only: no additional image, detail or home request.
    fallback=list(retained or [])
    native=getattr(api,'native',None)
    fallback.extend(retained_subjects(getattr(native,'home_data',None)))
    for subject in fallback:
        if len(items)>=limit:break
        if selection.accept(subject):items.append(subject)
    (rng or random.SystemRandom()).shuffle(items)
    return items[:limit]
