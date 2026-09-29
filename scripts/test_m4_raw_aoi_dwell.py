import unittest
from m4_raw_aoi_dwell import integrate_dwell

CARDS = [dict(position=0, x=0, y=0, width=100, height=100),
         dict(position=1, x=0, y=200, width=100, height=100)]


class DwellTest(unittest.TestCase):
    def test_total_across_visits_without_margin_or_threshold(self):
        e = [(0,'mousemove',50,50), (50,'mousemove',101,50),
             (150,'mousemove',50,50), (250,'mousemove',500,500)]
        self.assertEqual(integrate_dwell(e, CARDS, 500), {0:150,1:0})

    def test_scroll_moves_document_under_stationary_cursor(self):
        e = [(0,'mousemove',50,50), (100,'scroll',0,200), (300,'mousemove',50,250)]
        self.assertEqual(integrate_dwell(e, CARDS, 500), {0:100,1:200})
        self.assertEqual(integrate_dwell(e, CARDS, 500,adjust_scroll=False), {0:300,1:0})

    def test_initial_scroll_and_strict_cutoff(self):
        e = [(-100,'scroll',0,200), (0,'mousemove',50,250),
             (100,'mousemove',50,250), (200,'mousemove',50,50)]
        self.assertEqual(integrate_dwell(e, CARDS, 200), {0:0,1:100})
        self.assertEqual(integrate_dwell(e, CARDS, 200,extend_to_cutoff=True), {0:0,1:200})

    def test_no_duration_before_first_known_pointer(self):
        e = [(0,'scroll',0,0), (100,'mousemove',50,50), (200,'mousemove',50,50)]
        self.assertEqual(integrate_dwell(e, CARDS, 300), {0:100,1:0})

    def test_duplicate_times_add_no_duration(self):
        e = [(0,'mousemove',50,50), (0,'mousemove',50,250), (100,'mousemove',50,250)]
        self.assertEqual(integrate_dwell(e, CARDS, 200), {0:0,1:100})


if __name__ == '__main__':
    unittest.main()
