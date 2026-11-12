import unittest
from audio_options import audio_variants, with_audio, matching_runtime, language_label


class AudioOptionsTests(unittest.TestCase):
    def test_subtitle_only_editions_are_not_audio_languages(self):
        subject={'subjectId':'base','dubs':[
            {'subjectId':'en','type':0,'lanCode':'en','original':True},
            {'subjectId':'hi','type':0,'lanCode':'hi'},
            {'subjectId':'arabic-sub','type':1,'lanName':'Arabic sub'},
            {'subjectId':'hi','type':0,'lanCode':'hi'}]}
        choices=audio_variants(subject)
        self.assertEqual([c['subjectId'] for c in choices],['en','hi'])
        selected=with_audio(subject,choices[1])
        self.assertEqual(selected['subjectId'],'hi')
        self.assertEqual(selected['_audio_base_id'],'base')
        self.assertEqual(language_label(choices[1]),'Hindi')

    def test_truncated_got_hd_is_not_used_for_seamless_audio_switch(self):
        streams=[{'resolutions':1080,'duration':1717},{'resolutions':720,'duration':4716},
                 {'resolutions':480,'duration':4716}]
        self.assertEqual([s['resolutions'] for s in matching_runtime(streams,4716.7)],[720,480])
        with self.assertRaises(ValueError):
            matching_runtime(streams[:1],4716)


if __name__=='__main__':
    unittest.main()
