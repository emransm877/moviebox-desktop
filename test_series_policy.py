import unittest
from series_policy import episode_numbers,next_episode,next_up_at

class SeriesPolicyTests(unittest.TestCase):
    def test_explicit_episode_gaps_and_duplicates(self):
        self.assertEqual(episode_numbers({'episodeNumbers':[1,3,3,5]}),[1,3,5])
        self.assertEqual(next_episode([{'se':1,'episodeNumbers':[1,3,5]}],1,1),(1,3))
    def test_next_season_and_final_episode(self):
        seasons=[{'se':2,'maxEp':2},{'se':1,'maxEp':2}]
        self.assertEqual(next_episode(seasons,1,2),(2,1))
        self.assertIsNone(next_episode(seasons,2,2))
    def test_empty_and_zero_seasons_have_no_next(self):
        self.assertIsNone(next_episode([],1,1))
        self.assertIsNone(next_episode([{'se':0,'maxEp':1}],0,0))
    def test_episode_csv_and_count(self):
        self.assertEqual(episode_numbers({'allEp':'1,4,8'}),[1,4,8])
        self.assertEqual(episode_numbers({'maxEp':3}),[1,2,3])
    def test_known_credit_marker_and_conservative_fallback(self):
        self.assertEqual(next_up_at(100000,{'creditsStartMs':80000}),80000)
        self.assertEqual(next_up_at(100000,{'creditsStartMs':1000000}),90000)
        self.assertEqual(next_up_at(2400000),2370000)
    def test_unknown_duration_does_not_prompt(self):
        self.assertIsNone(next_up_at(0))

if __name__=='__main__':unittest.main()
