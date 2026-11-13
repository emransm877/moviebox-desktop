import random
import unittest
from hero_feed import latest_titles
from themes import THEMES, initial_theme, palette

class FeedAPI:
    def __init__(self): self.calls=[]
    def request(self,path,body):
        self.calls.append(body)
        channel,page=body['channelId'],body['page']
        return {'items':[{'subjectId':f'{channel}-{page}-{i}','subjectType':channel,'title':f'Title {i}'} for i in range(24)],'pager':{'hasMore':True,'nextPage':page+1}}

class ThemesAndHeroTests(unittest.TestCase):
    def test_balanced_bounded_latest_mix_shuffles_metadata_only(self):
        api=FeedAPI();items=latest_titles(api,rng=random.Random(42))
        self.assertEqual(len(items),100)
        self.assertEqual(len({s['subjectId'] for s in items}),100)
        self.assertEqual(sum(s['subjectType']==1 for s in items),50)
        self.assertEqual(sum(s['subjectType']==2 for s in items),50)
        self.assertEqual(len(api.calls),6)
        self.assertTrue(all(b['sort']=='Latest' for b in api.calls))
        self.assertTrue(any(s['subjectType']==2 for s in items[:10]))

    def test_failed_channel_preserves_other_channel(self):
        class Partial(FeedAPI):
            def request(self,path,body):
                if body['channelId']==1: raise OSError('Offline')
                return super().request(path,body)
        self.assertEqual(len(latest_titles(Partial())),50)

    def test_duplicate_page_does_not_loop_forever(self):
        class Duplicates(FeedAPI):
            def request(self,path,body):
                return {'items':[{'subjectId':'only','subjectType':body['channelId'],'title':'One'}],'pager':{'hasMore':True,'nextPage':body['page']+1}}
        self.assertEqual(len(latest_titles(Duplicates())),1)

    def test_five_distinct_complete_palettes_and_safe_migration(self):
        self.assertEqual(len(THEMES),5)
        self.assertEqual(len({p['accent'] for p in THEMES.values()}),5)
        self.assertEqual(initial_theme({'appearance':'light'}),'aurora')
        self.assertEqual(initial_theme({'appearance':'system','theme':'eclipse'},False),'aurora')
        self.assertEqual(initial_theme({'theme':'eclipse','appearance':'light'}),'eclipse')
        self.assertEqual(initial_theme({'theme':'unknown'}),'obsidian')
        self.assertEqual(initial_theme({'theme':{'broken':True}}),'obsidian')
        self.assertIs(palette(False),THEMES['aurora'])

if __name__=='__main__': unittest.main()
