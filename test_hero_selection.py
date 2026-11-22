import copy,random,unittest
from types import SimpleNamespace
from hero_feed import unique_spotlights,visual_keys,latest_titles


def item(identity,title=None,year='2026',kind=1,url=None):
    return {'subjectId':identity,'title':title or identity,'releaseDate':year,'subjectType':kind,'cover':{'url':url or 'https://images.example.test/'+identity+'.jpg'}}


class HeroSelectionTests(unittest.TestCase):
    def test_cover_host_case_path_ignores_query_and_fragment_without_rewriting_url(self):
        first=item('a','Alpha',url='https://CDN.example.test/art.jpg?w=300#one')
        second=item('b','Beta',url='https://cdn.example.test/art.jpg?w=900#two')
        self.assertEqual(unique_spotlights([first,second]),[first])
        self.assertEqual(first['cover']['url'],'https://CDN.example.test/art.jpg?w=300#one')

    def test_hosts_are_not_cross_normalized(self):
        a=item('a','Alpha',url='https://cdn.example.test/art.jpg');b=item('b','Beta',url='https://other.example.test/art.jpg')
        self.assertEqual(len(unique_spotlights([a,b])),2)

    def test_known_language_editions_and_unsuffixed_same_title_year_type_group(self):
        records=[item('base','Dead-End Job'),item('hi','Dead-End Job [Hindi]'),item('ta','Dead-End Job [Tamil][English]')]
        self.assertEqual(unique_spotlights(records),[records[0]])
        self.assertEqual(unique_spotlights([item('x','  SAME   title '),item('y','same title')])[0]['subjectId'],'x')

    def test_unknown_brackets_unicode_year_and_type_distinctions_are_preserved(self):
        records=[item('base','Story'),item('rec','Story [REC]'),item('unicode','Story [\u65e5\u672c\u8a9e]'),item('year','Story',year='2025'),item('type','Story',kind=2)]
        self.assertEqual(len(unique_spotlights(records)),5)
        self.assertEqual(len(unique_spotlights([item('u','\u09ac\u09be\u0982\u09b2\u09be'),item('h','\u09ac\u09be\u0982\u09b2\u09be [Hindi]')])),1)

    def test_missing_or_invalid_year_does_not_merge_unrelated_title_rows(self):
        self.assertEqual(len(unique_spotlights([item('one','Same',year=''),item('two','Same',year='bad')])),2)

    def test_dedupe_precedes_cap_and_never_changes_catalogue_editions(self):
        records=[item(str(i),'Edition '+str(i),url='https://same.example.test/shared.jpg') for i in range(100)]+[item('last','Unique')]
        original=copy.deepcopy(records);selected=unique_spotlights(records,2)
        self.assertEqual([r['subjectId'] for r in selected],['0','last']);self.assertEqual(records,original)
        self.assertEqual(unique_spotlights(records,0),[])

    def test_retained_metadata_backfills_without_detail_home_or_image_requests(self):
        class API:
            def __init__(self):self.calls=[];self.native=SimpleNamespace(home_data={'items':[item('native-retained','Native retained',kind=2)]})
            def request(self,path,body):
                self.calls.append(body)
                kind=body['channelId'];base=item('base-'+str(kind),'Story '+str(kind),kind=kind)
                return {'items':[base,item('dub-'+str(kind),base['title']+' [Hindi]',kind=kind)],'pager':{'hasMore':False}}
        api=API();retained=[item('retained','Retained movie')]
        result=latest_titles(api,rng=random.Random(1),retained=retained)
        self.assertEqual(len(result),4);self.assertEqual(len(api.calls),2)
        self.assertEqual({r['subjectId'] for r in result},{'base-1','base-2','retained','native-retained'})


if __name__=='__main__':unittest.main()
