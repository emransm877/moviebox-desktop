"""Bounded metadata cache, separate from user library and playback credentials."""
import copy
import json
import os
from pathlib import Path
import threading
import time
import uuid

FIELDS=('subjectId','subjectType','title','releaseDate','imdbRatingValue','genre','countryName','hasResource','corner')
def compact(subject):
    result={key:subject[key] for key in FIELDS if key in subject}
    cover=subject.get('cover')
    if isinstance(cover,dict):result['cover']={key:cover[key] for key in ('url','width','height','thumbnail') if key in cover}
    return result

class CatalogueCache:
    TTL=300
    def __init__(self,path=None):
        self.path=Path(path) if path else None
        self.entries={}
        self.lock=threading.RLock()
        if self.path:
            try:
                if self.path.stat().st_size<=2_000_000:
                    data=json.loads(self.path.read_text(encoding='utf-8'))
                    if isinstance(data,dict) and data.get('version')==1 and isinstance(data.get('entries'),dict):self.entries=dict(list(data['entries'].items())[-8:])
            except (OSError,ValueError,TypeError):pass

    @staticmethod
    def key(kind,selection):
        return kind+':'+json.dumps({k:v for k,v in selection.items() if v not in ('All','ForYou','',None)},sort_keys=True,separators=(',',':'))

    def get(self,key):
        with self.lock:
            value=self.entries.get(key)
            if not isinstance(value,dict) or not isinstance(value.get('items'),list):return None
            if not all(isinstance(s,dict) and s.get('subjectId') and s.get('title') for s in value['items']):return None
            try:
                if time.time()-float(value.get('at',0))>7*86400:return None
            except (ValueError,TypeError):return None
            value=copy.deepcopy(value)
            try:
                for field in ('page','next_page','first_count','row','scroll'):
                    if field in value:value[field]=max(0,int(value[field]))
            except (ValueError,TypeError,OverflowError):return None
            return value

    def put(self,key,entry):
        value=copy.deepcopy(entry)
        value['items']=[compact(s) for s in value['items'][:240]]
        with self.lock:
            self.entries.pop(key,None);self.entries[key]=value
            while len(self.entries)>8:self.entries.pop(next(iter(self.entries)))

    def flush(self):
        if not self.path:return
        with self.lock:
            payload=json.dumps({'version':1,'entries':self.entries},ensure_ascii=False,separators=(',',':'))
            temporary=self.path.with_name(self.path.name+'.'+uuid.uuid4().hex+'.tmp')
            try:
                self.path.parent.mkdir(parents=True,exist_ok=True)
                temporary.write_text(payload,encoding='utf-8');os.replace(temporary,self.path)
            except OSError:pass
            finally:
                try:temporary.unlink(missing_ok=True)
                except OSError:pass
