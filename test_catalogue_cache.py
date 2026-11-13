import json,tempfile,time,unittest
from pathlib import Path
from catalogue_cache import CatalogueCache

class CatalogueCacheTests(unittest.TestCase):
    def test_filter_key_is_order_independent_and_ignores_defaults(self):
        self.assertEqual(CatalogueCache.key('movies',{'year':'All','sort':'ForYou','genre':'Action'}),CatalogueCache.key('movies',{'genre':'Action'}))
        self.assertNotEqual(CatalogueCache.key('series',{}),CatalogueCache.key('movies',{}))
    def test_persist_only_bounded_metadata_and_return_independent_copy(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'cache.json';cache=CatalogueCache(path)
            for i in range(10):cache.put(str(i),{'at':time.time(),'items':[{'subjectId':str(n),'title':'Title','subjectType':1,'token':'private','url':'stream'} for n in range(250)]})
            cache.flush();restored=CatalogueCache(path)
            self.assertEqual(len(restored.entries),8);self.assertEqual(len(restored.get('9')['items']),240)
            self.assertNotIn('private',path.read_text());self.assertNotIn('stream',path.read_text())
            value=restored.get('9');value['items'].clear();self.assertEqual(len(restored.get('9')['items']),240)
    def test_corrupt_cache_does_not_affect_library(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'cache.json';path.write_text('{broken');self.assertEqual(CatalogueCache(path).entries,{})
            for value in ('null','[]','"wrong"'):
                path.write_text(value);self.assertEqual(CatalogueCache(path).entries,{})
    def test_expired_and_invalid_entries_are_ignored(self):
        cache=CatalogueCache();cache.entries={'bad':{'items':[None],'at':time.time()},'old':{'items':[],'at':time.time()-8*86400}}
        self.assertIsNone(cache.get('bad'));self.assertIsNone(cache.get('old'))
    def test_cache_budget_keeps_the_first_uncached_page_cursor(self):
        cache=CatalogueCache()
        items=[{'subjectId':str(i),'title':'Title'} for i in range(240)]
        cache.put('movies',{'items':items,'at':time.time(),'page':10,'next_page':11,'has_more':True})
        cache.put('movies',{'items':items+[{'subjectId':'new','title':'New'}],'at':time.time(),'page':11,'next_page':12,'has_more':False})
        self.assertEqual(cache.get('movies')['next_page'],11)
        self.assertTrue(cache.get('movies')['has_more'])
if __name__=='__main__':unittest.main()
