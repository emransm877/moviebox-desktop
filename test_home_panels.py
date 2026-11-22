import unittest
from home_panels import recent_history,clock


def record(identity,position=10000,duration=40000,updated=1,**values):
    return {'subject':{'subjectId':identity,'title':identity},'position':position,'duration':duration,'updated':updated,**values}


class ContinueHistoryTests(unittest.TestCase):
    def test_actual_recent_unfinished_unique_subjects_only(self):
        history={'one:1:1':record('one',updated=1),'one:2:3':record('one',position=12000,updated=4),
                 'two:0:0':record('two',updated=3),'three:0:0':record('three',updated=2),
                 'finished:0:0':record('finished',updated=9,completed=True),'zero:0:0':record('zero',position=0,updated=10),
                 'unknown:0:0':record('unknown',duration=0,updated=11)}
        self.assertEqual([key for key,_ in recent_history(history)],['one:2:3','two:0:0','three:0:0'])

    def test_legacy_string_times_normalize_without_mutating_library(self):
        history={'one:0:0':record('one',position='12000',duration='40000',updated='5')}
        key,value=recent_history(history)[0]
        self.assertEqual(value['position'],12000);self.assertEqual(value['duration'],40000)
        self.assertEqual(history[key]['position'],'12000')

    def test_malformed_incomplete_and_almost_finished_records_are_ignored(self):
        values={'bad':record('bad'),'bad:season:episode':record('bad'),'null:0:0':None,'subject:0:0':{'subject':'bad'},
                'time:0:0':record('time',position='invalid'),'end:0:0':record('end',position=39999),'okay:0:0':record('okay')}
        self.assertEqual([key for key,_ in recent_history(values)],['okay:0:0'])
        self.assertEqual(recent_history(values,0),[])

    def test_clock_uses_real_milliseconds(self):
        self.assertEqual(clock(12000),'0:12');self.assertEqual(clock(3723000),'1:02:03');self.assertEqual(clock(-1),'0:00')


if __name__=='__main__':unittest.main()
