"""Audio editions are distinct from subtitle-only catalog editions."""
LANGUAGES = {'en': 'English', 'hi': 'Hindi', 'bn': 'Bangla', 'ar': 'Arabic',
             'fr': 'French', 'es': 'Spanish', 'esla': 'Spanish (Latin America)',
             'pt': 'Portuguese', 'ptbr': 'Portuguese (Brazil)',
             'ta': 'Tamil', 'te': 'Telugu', 'kn': 'Kannada', 'ml': 'Malayalam',
             'ur': 'Urdu', 'id': 'Indonesian', 'tr': 'Turkish', 'ru': 'Russian',
             'zh': 'Chinese', 'ja': 'Japanese', 'ko': 'Korean'}


def audio_variants(subject):
    result, seen = [], set()
    for item in subject.get('dubs') or []:
        try:
            audio = int(item.get('type', 0)) == 0
        except (ValueError, TypeError):
            audio = False
        identity = str(item.get('subjectId') or '')
        if not audio or not identity or identity in seen:
            continue
        seen.add(identity)
        result.append(dict(item))
    return result


def language_label(item):
    code = str(item.get('lanCode') or '').lower()
    label = LANGUAGES.get(code) or str(item.get('lanName') or 'Original audio')
    if label.lower().endswith(' dub'):
        label = label[:-4]
    return label


def with_audio(subject, variant):
    result = dict(subject)
    result['_audio_base_id'] = str(subject.get('_audio_base_id') or subject['subjectId'])
    result['subjectId'] = str(variant['subjectId'])
    result['_audio_language'] = language_label(variant)
    result['_audio_code'] = variant.get('lanCode') or ''
    return result


def matching_runtime(streams, duration_seconds):
    """Never switch into a truncated file or another cut at the same timestamp."""
    if duration_seconds <= 0:
        return streams
    matching = [stream for stream in streams if abs(float(stream.get('duration') or 0) - duration_seconds) <= 2]
    if not matching:
        raise ValueError('This audio edition has a different runtime. Open that edition separately to play it safely.')
    return matching
