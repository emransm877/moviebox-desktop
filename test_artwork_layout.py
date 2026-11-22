import unittest
from artwork_layout import fit_rect,banner_artwork,banner_source_rect,prepare_artwork

class FullArtworkTests(unittest.TestCase):
    def test_home_promotional_banners_join_by_exact_identity_not_editorial_title(self):
        subject={'subjectId':'one','title':'Actual title [Hindi]','releaseDate':'2026-01-01','subjectType':1}
        image={'url':'hd-banner','width':1920,'height':1080}
        index={}
        prepare_artwork({'operatingList':[{'banner':{'items':[{'title':'Editorial text','subjectId':'one','subjectType':1,'subject':dict(subject),'image':image}]}}]},index)
        later=prepare_artwork({'items':[dict(subject),dict(subject,subjectId='two'),dict(subject,releaseDate='2025-01-01')]},index)['items']
        self.assertEqual(banner_artwork(later[0]),('hd-banner','banner'))
        self.assertEqual(banner_artwork(later[1]),('',None));self.assertEqual(banner_artwork(later[2]),('',None))
        bad={}
        prepare_artwork({'operatingList':[{'banner':{'items':[{'subjectId':'wrong','subjectType':1,'subject':subject,'image':image}]}}]},bad)
        self.assertFalse(bad)
    def test_banner_only_uses_the_selected_titles_actual_wide_assets(self):
        portrait={'url':'portrait','width':600,'height':900}
        self.assertEqual(banner_artwork({'cover':portrait}),('',None))
        self.assertEqual(banner_artwork({'cover':portrait,'stills':{'url':'actual-backdrop','width':1920,'height':1080}}),('actual-backdrop','stills'))
        self.assertEqual(banner_artwork({'cover':portrait,'trailer':{'cover':{'url':'actual-trailer-frame','width':854,'height':480}}}),('',None))
    def test_unknown_low_resolution_and_other_title_images_are_rejected(self):
        for record in [{'url':'unknown'}, {'url':'tiny','width':639,'height':319}, {'url':'other','width':1920,'height':1080,'subjectId':'other'}, {'url':'poster','width':1500,'height':2222}]:
            self.assertEqual(banner_artwork({'subjectId':'selected','stills':record}),('',None))
    def test_native_banner_container_joins_exact_subject_and_skips_promotions(self):
        item={'subjectId':'native-one','subjectType':2,'title':'Exact native title','releaseDate':'2026-01-01'}
        row={'subjectId':'native-one','subject':dict(item),'image':{'url':'native-wide','width':3840,'height':2160}}
        index={}
        prepare_artwork({'items':[{'banner':{'banners':[row,dict(row,subjectId='0'),dict(row,subjectId='wrong')]}}]},index)
        self.assertEqual(set(index),{'native-one'})
        joined=prepare_artwork(dict(item),index)
        self.assertEqual(banner_artwork(joined),('native-wide','banner'))
        for field,value in [('title','Other title'),('releaseDate','2025-01-01'),('subjectType',1),('subjectId','other')]:
            self.assertEqual(banner_artwork(prepare_artwork(dict(item,**{field:value}),index)),('',None))
    def test_genuine_920_by_518_banner_is_usable_without_hd_upscaling_claim(self):
        self.assertEqual(banner_artwork({'subjectId':'campus','banner':{'url':'actual-wide','width':920,'height':518}}),('actual-wide','banner'))
    def test_native_year_and_web_full_date_join_but_missing_or_conflicting_years_do_not(self):
        native={'subjectId':'5705878031781299520','subjectType':2,'title':'Percy Jackson et Les Olympiens [Version fran\u00e7aise]','releaseDate':'2023'}
        index={};prepare_artwork({'items':[{'banner':{'banners':[{'subjectId':native['subjectId'],'subject':dict(native),'image':{'url':'actual-native-banner','width':3840,'height':2160}}]}}]},index)
        self.assertEqual(banner_artwork(prepare_artwork(dict(native,releaseDate='2023-12-20'),index)),('actual-native-banner','banner'))
        for value in ['2024-12-20','','unknown','2023-99-99','0000']:
            self.assertEqual(banner_artwork(prepare_artwork(dict(native,releaseDate=value),index)),('',None))
    def test_official_mapping_requires_exact_id_title_year_and_type(self):
        subject={'subjectId':'542588344010695272','title':'Murder in Galicia','releaseDate':'2026-11-13','subjectType':2}
        url,source=banner_artwork(subject)
        self.assertIn('nflxso.net/',url);self.assertEqual(source,'verified-official')
        for key,value in [('subjectId','wrong'),('title','Unprotected: Murder in Galicia'),('releaseDate','2025-11-13'),('subjectType',1)]:
            self.assertEqual(banner_artwork(dict(subject,**{key:value})),('',None))
    def test_banner_is_full_bleed_without_stretching(self):
        for w,h in [(1920,1080),(2560,1080),(3840,720)]:
            x,y,sw,sh=banner_source_rect(w,h,1280,248)
            self.assertAlmostEqual(sw/sh,1280/248);self.assertGreaterEqual(x,0);self.assertGreaterEqual(y,0);self.assertLessEqual(x+sw,w+1e-6);self.assertLessEqual(y+sh,h+1e-6)
    def test_portrait_landscape_square_and_ultrawide_fit_without_losing_edges(self):
        for width, height in [(600,900),(1920,1080),(1000,1000),(3200,700)]:
            for bounds in [(0,0,170,255),(560,12,416,180),(0,0,255,382)]:
                with self.subTest(image=(width,height),bounds=bounds):
                    x,y,w,h = fit_rect(width,height,*bounds)
                    bx,by,bw,bh = bounds
                    self.assertGreaterEqual(x,bx); self.assertGreaterEqual(y,by)
                    self.assertLessEqual(x+w,bx+bw+1e-6); self.assertLessEqual(y+h,by+bh+1e-6)
                    self.assertAlmostEqual(w/h,width/height)
                    self.assertTrue(abs(w-bw)<1e-6 or abs(h-bh)<1e-6)
