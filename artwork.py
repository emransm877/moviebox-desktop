"""Bounded artwork from the service's verified image CDN resize endpoint."""
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def resized_artwork(url, width=360):
    try:
        value=urlsplit(url)
        if value.scheme!='https' or not (value.hostname=='aoneroom.com' or (value.hostname or '').endswith('.aoneroom.com')) or not value.path.startswith('/image/'):
            return url
        query=dict(parse_qsl(value.query,keep_blank_values=True))
        query['x-oss-process']=f'image/resize,w_{max(120,min(1280,int(width)))}/format,webp'
        return urlunsplit((value.scheme,value.netloc,value.path,urlencode(query),value.fragment))
    except (ValueError,TypeError):
        return url
