"""Bounded UTF-8 API JSON, with explicitly advertised gzip responses only."""
import json
import zlib

ENCODED_LIMIT = 8 * 1024 * 1024
DECODED_LIMIT = 16 * 1024 * 1024


def read_json(response, *, encoded_limit=ENCODED_LIMIT, decoded_limit=DECODED_LIMIT):
    raw = response.read(encoded_limit + 1)
    if len(raw) > encoded_limit:
        raise ValueError('API JSON exceeds the encoded size limit')
    encoding = (response.headers.get('Content-Encoding') or '').strip().lower()
    if encoding == 'gzip':
        decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
        try:
            raw = decoder.decompress(raw, decoded_limit + 1)
        except zlib.error as error:
            raise ValueError('Invalid gzip API JSON') from error
        if len(raw) > decoded_limit or decoder.unconsumed_tail:
            raise ValueError('API JSON exceeds the decoded size limit')
        if not decoder.eof or decoder.unused_data:
            raise ValueError('Incomplete or trailing gzip API JSON')
    elif encoding not in ('', 'identity'):
        raise ValueError('Unsupported API JSON content encoding: ' + encoding)
    if len(raw) > decoded_limit:
        raise ValueError('API JSON exceeds the decoded size limit')
    # JSON's wire encoding is UTF-8 regardless of a stale HTTP charset label.
    return json.loads(raw.decode('utf-8-sig'))
