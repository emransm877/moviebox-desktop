"""Proportional poster layout and title-specific HD hero artwork."""
import json
from pathlib import Path

def _verified_banners():
    try:
        return json.loads((Path(__file__).parent / 'assets' / 'verified-banners.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []

VERIFIED_BANNERS = _verified_banners()

def prepare_artwork(data, index):
    """Join the service's explicit banner/image relation by exact subject ID.

    The home feed's banner title is editorial copy, not an identity key. Only
    its nested subject, with the same ID and type, can establish the relation.
    """
    if isinstance(data, dict):
        for section in data.get('operatingList') or []:
            for item in (section.get('banner') or {}).get('items') or []:
                subject = item.get('subject') or {}
                identity = str(item.get('subjectId') or '')
                if (not identity or identity != str(subject.get('subjectId'))
                        or item.get('subjectType') != subject.get('subjectType')
                        or not subject.get('title') or not subject.get('releaseDate')):
                    continue
                candidate = dict(item.get('image') or {}, subjectId=identity)
                if banner_artwork({'subjectId': identity, 'banner': candidate})[0]:
                    index[identity] = (subject['title'], subject['releaseDate'], subject['subjectType'], candidate)
        while len(index)>512: del index[next(iter(index))]
    def attach(node):
        if isinstance(node, dict):
            match = index.get(str(node.get('subjectId')))
            if match and (node.get('title'),node.get('releaseDate'),node.get('subjectType')) == match[:3]:
                node['banner'] = dict(match[3])
            for value in list(node.values()): attach(value)
        elif isinstance(node, list):
            for value in node: attach(value)
    attach(data)
    return data
def fit_rect(width, height, x, y, available_width, available_height):
    if min(width, height, available_width, available_height) <= 0:
        return (x, y, 0.0, 0.0)
    scale = min(available_width / width, available_height / height)
    target_width, target_height = width * scale, height * scale
    return (x + (available_width - target_width) / 2,
            y + (available_height - target_height) / 2,
            target_width, target_height)

def banner_artwork(subject):
    """Only explicit HD backdrops or reviewed, exact-identity promotional assets.

    Trailer frames, covers, fuzzy title matches and unknown dimensions are not
    evidence of a usable banner. Missing artwork stays missing.
    """
    for record in VERIFIED_BANNERS:
        if (str(subject.get('subjectId')) in record['subjectIds']
                and str(subject.get('releaseDate', ''))[:4] == record['year']
                and str(subject.get('subjectType')) == str(record['subjectType'])
                and subject.get('title') in record['titles']):
            return record['url'], 'verified-official'
    for name,value in [('stills',subject.get('stills')),('banner',subject.get('banner')),('backdrop',subject.get('backdrop'))]:
        for candidate in value if isinstance(value,list) else [value]:
            record={'url':candidate} if isinstance(candidate,str) else candidate or {}
            if not isinstance(record,dict) or not record.get('url'):continue
            width,height=record.get('width') or 0,record.get('height') or 0
            try: width,height=float(width),float(height)
            except (TypeError,ValueError): continue
            if width<1280 or height<600 or not 1.45<=width/height<=3.2:continue
            if record.get('subjectId') is not None and str(record['subjectId']) != str(subject.get('subjectId')):continue
            return record['url'],name
    return '',None

def banner_source_rect(width,height,target_width,target_height):
    """Full-bleed landscape framing, biased above centre to protect faces."""
    if min(width,height,target_width,target_height)<=0:return (0,0,0,0)
    scale=max(target_width/width,target_height/height)
    sw,sh=target_width/scale,target_height/scale
    return (max(0,min(width-sw,width*.5-sw/2)),max(0,min(height-sh,height*.22-sh/2)),sw,sh)
