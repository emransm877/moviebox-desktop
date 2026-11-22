"""Stable mixed artwork and bounded independent metadata loading regressions."""
import copy
import io
import json
import threading
import time
import unittest
from unittest.mock import Mock, patch
from service import MovieBoxService


def subject(identity='one', width=1920, height=1080):
    return {'subjectId':identity,'subjectType':2,'title':identity,
            'cover':{'url':'https://example.test/'+identity,'width':width,'height':height}}


class DetailPerformanceTests(unittest.TestCase):
    def setUp(self):
        self.api=MovieBoxService(use_native=False)
        self.addCleanup(self.api.close)
        self.item=subject()
        self.data={'subject':self.item,'resource':{'seasons':[{'se':1,'maxEp':3}]}}

    def test_independent_web_and_native_metadata_start_together(self):
        started=threading.Event()
        def native(_):started.set();return {'seasons':[{'se':1,'maxEp':5}]}
        def web(_):
            self.assertTrue(started.wait(1),'Native metadata was queued behind web detail')
            return copy.deepcopy(self.data)
        self.api.native=Mock();self.api.native.season_info.side_effect=native
        self.api.request=web
        self.assertEqual(self.api.detail(self.item)['episode_count'],5)

    def test_revisit_cache_is_copy_isolated_account_scoped_and_expires(self):
        self.api.request=Mock(side_effect=lambda _:copy.deepcopy(self.data))
        first=self.api.detail(self.item);first['subject']['title']='mutated';first['resource']['seasons'].clear()
        self.assertEqual(self.api.detail(self.item)['subject']['title'],'one')
        self.assertEqual(self.api.request.call_count,1)
        self.api.account_token='synthetic-account'
        self.api.detail(self.item);self.assertEqual(self.api.request.call_count,2)
        with patch('service.time.monotonic',return_value=time.monotonic()+61):self.api.detail(self.item)
        self.assertEqual(self.api.request.call_count,3)

    def test_native_failure_is_retryable_and_does_not_poison_cache(self):
        self.api.request=Mock(side_effect=lambda _:copy.deepcopy(self.data))
        self.api.native=Mock();self.api.native.season_info.side_effect=[RuntimeError('owned outage'),{'seasons':[{'se':1,'maxEp':7}]}]
        self.assertFalse(self.api.detail(self.item)['nativeMetadataAvailable'])
        self.assertEqual(self.api.detail(self.item)['episode_count'],7)
        self.assertEqual(self.api.request.call_count,2)

    def test_cache_size_is_bounded(self):
        self.api.request=lambda _:copy.deepcopy(self.data)
        for i in range(80):self.api.detail(subject(str(i)))
        self.assertEqual(len(self.api.detail_cache),64)

    def test_web_failure_does_not_create_cache_entry(self):
        self.api.request=Mock(side_effect=[RuntimeError('owned network failure'),copy.deepcopy(self.data)])
        with self.assertRaises(RuntimeError):self.api.detail(self.item)
        self.assertFalse(self.api.detail_cache)
        self.assertEqual(self.api.detail(self.item)['subject']['subjectId'],'one')

    def test_existing_native_home_is_reused_without_another_native_request(self):
        image={'url':'owned-native-banner','width':1920,'height':1080}
        self.api.native=Mock()
        self.api.native.home_data={'items':[{'banner':{'banners':[{'subjectId':'one','subject':dict(self.item,releaseDate='2026-01-01'),'image':image}]}}]}
        class Response(io.BytesIO):headers={}
        body={'code':0,'data':{'items':[dict(self.item,releaseDate='2026-01-01')]}}
        with patch('service.urlopen',return_value=Response(json.dumps(body).encode())):
            result=self.api.request('/owned-fixture')
        self.assertEqual(result['items'][0]['banner']['url'],'owned-native-banner')
        self.api.native.home.assert_not_called();self.api.native.request.assert_not_called()


if __name__=='__main__':unittest.main()
