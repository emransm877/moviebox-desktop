import unittest
from urllib.parse import parse_qs,urlsplit
from artwork import resized_artwork


class ArtworkTests(unittest.TestCase):
    def test_large_image_is_resized_with_other_parameters_preserved(self):
        result=urlsplit(resized_artwork('https://pbcdn.aoneroom.com/image/huge.jpg?keep=yes#poster',300))
        self.assertEqual(parse_qs(result.query),{'keep':['yes'],'x-oss-process':['image/resize,w_300/format,webp']})
        self.assertEqual(result.fragment,'poster')

    def test_external_hosts_and_unrelated_paths_are_not_rewritten(self):
        for url in ['https://aoneroom.com.evil.example/image/test.jpg','https://other.example/image/test.jpg','https://pbcdn.aoneroom.com/media/video.mp4','http://pbcdn.aoneroom.com/image/cover.jpg']:
            self.assertEqual(resized_artwork(url),url)

    def test_existing_resize_is_replaced_without_stacking_parameters(self):
        url=resized_artwork(resized_artwork('https://pbcdn.aoneroom.com/image/test.jpg',960),360)
        self.assertEqual(parse_qs(urlsplit(url).query)['x-oss-process'],['image/resize,w_360/format,webp'])


if __name__=='__main__':unittest.main()
