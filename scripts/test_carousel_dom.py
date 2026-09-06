"""Synthetic regression tests for the candidate DOM extractor.

Run: PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover \
    -s /private/tmp/carousel-repair-20260904/scripts -p test_carousel_dom.py -v
All browser fixtures are synthetic; HTTP(S) requests are blocked. No corpus writes.
"""
from __future__ import annotations
import copy
import unittest

from playwright.sync_api import sync_playwright
from carousel_dom import EXTRACT_JS, bind_parents, check_fixture

CSS = '''<style>
html,body{margin:0;padding:0}body{font:16px sans-serif}
.commercial-unit-desktop-top{position:absolute;left:100px;top:100px;width:600px;height:180px;overflow:hidden}
.strip{position:relative;width:1200px;height:180px}
.pla-unit{position:absolute;top:0;width:200px;height:180px;box-sizing:border-box;border:4px solid white;background:#a8cedf}
.product-image{position:absolute;left:20px;top:15px;width:100px;height:70px;background:#678b9f}
.caption{position:absolute;left:12px;bottom:12px}
</style>'''


def parent(name='main', *, ids=(0,1,2,3,4), style='', card_styles=None, suffix=''):
    card_styles = card_styles or {}
    cards = ''.join(
        f'<div class="pla-unit" style="left:{n*200}px;{card_styles.get(n, "")}">'
        f'<a id="vplaurlg{i}" class="product-image"></a><span class="caption">Card {i}</span></div>'
        for n,i in enumerate(ids))
    return f'<section id="{name}" class="commercial-unit-desktop-top" style="{style}"><div class="strip">{cards}{suffix}</div></section>'


def typed(position=0, x=100, y=100, width=600, height=180, **extra):
    return dict(type='dd_top',position=position,x=x,y=y,width=width,height=height,html_handle=None,**extra)


class DomExtractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.context = self.browser.new_context(viewport={'width':1389,'height':1024})
        self.context.route('http://**/*',lambda route: route.abort())
        self.context.route('https://**/*',lambda route: route.abort())
        self.page = self.context.new_page()
        self.addCleanup(self.context.close)

    def extract(self, html=None, setup=None):
        self.page.set_content(CSS + (parent() if html is None else html))
        if setup:
            self.page.evaluate(setup)
        return self.page.evaluate(EXTRACT_JS)

    @staticmethod
    def visible(result):
        return [c for p in result['parents'] for c in p['cells'] if c['visible_rect']]

    def test_complete_card_box_not_smaller_image_link(self):
        result=self.extract()
        cells=result['parents'][0]['cells']
        self.assertEqual(len(cells),5)
        self.assertEqual([c['card_id'] for c in self.visible(result)],['vplaurlg0','vplaurlg1','vplaurlg2'])
        self.assertEqual(cells[0]['raw_rect'],dict(x=100,y=100,w=200,h=180))
        self.assertEqual(cells[0]['visible_rect'],cells[0]['raw_rect'])
        self.assertEqual(cells[0]['visible_fraction'],1)
        self.assertIsNone(cells[3]['visible_rect'])
        self.assertIsNone(cells[3]['visible_index'])

    def test_right_partial_preserves_raw_and_visible_geometry(self):
        result=self.extract(parent(style='width:650px'))
        cells=self.visible(result)
        self.assertEqual(len(cells),4)
        self.assertEqual(cells[-1]['raw_rect']['w'],200)
        self.assertEqual(cells[-1]['visible_rect'],dict(x=700,y=100,w=50,h=180))
        self.assertEqual(cells[-1]['visible_fraction'],.25)
        self.assertEqual([c['visible_index'] for c in cells],[0,1,2,3])

    def test_left_and_right_partial_after_horizontal_scroll(self):
        result=self.extract(setup="document.getElementById('main').scrollLeft=50")
        cells=self.visible(result)
        self.assertEqual([c['card_id'] for c in cells],['vplaurlg0','vplaurlg1','vplaurlg2','vplaurlg3'])
        self.assertEqual(cells[0]['raw_rect']['x'],50)
        self.assertEqual(cells[0]['visible_rect'],dict(x=100,y=100,w=150,h=180))
        self.assertEqual(cells[0]['visible_fraction'],.75)
        self.assertEqual(cells[-1]['visible_rect']['w'],50)

    def test_fully_left_clipped_card_is_retained_but_not_visible(self):
        result=self.extract(setup="document.getElementById('main').scrollLeft=200")
        self.assertEqual([c['card_id'] for c in self.visible(result)],['vplaurlg1','vplaurlg2','vplaurlg3'])
        self.assertIsNone(result['parents'][0]['cells'][0]['visible_rect'])

    def test_nested_clips_intersect_in_document_space(self):
        html='<div style="position:absolute;left:100px;top:100px;width:450px;height:180px;overflow:hidden">'+parent(style='left:0;top:0;width:650px')+'</div>'
        result=self.extract(html)
        self.assertEqual(result['parents'][0]['visible_rect'],dict(x=100,y=100,w=450,h=180))
        cells=self.visible(result)
        self.assertEqual(len(cells),3)
        self.assertEqual(cells[-1]['visible_rect'],dict(x=500,y=100,w=50,h=180))

    def test_hidden_card_has_no_visible_rectangle(self):
        result=self.extract(parent(card_styles={1:'visibility:hidden'}))
        self.assertEqual([c['card_id'] for c in self.visible(result)],['vplaurlg0','vplaurlg2'])
        self.assertEqual(result['parents'][0]['cells'][1]['raw_rect']['w'],200)
        self.assertIsNone(result['parents'][0]['cells'][1]['visible_rect'])

    def test_hidden_ancestor_has_no_visible_cards(self):
        for style in ['visibility:hidden','opacity:0','display:none']:
            with self.subTest(style=style):
                result=self.extract(parent(style=style))
                self.assertEqual(self.visible(result),[])
                self.assertIsNone(result['parents'][0]['visible_rect'])

    def test_repeated_ids_across_parents_keep_parent_identity(self):
        result=self.extract(parent(ids=(0,1))+parent('second',ids=(0,1),style='top:400px'))
        result=bind_parents(result,[typed(),typed(1,y=400)],1,1)
        self.assertEqual(result['status'],'scored')
        self.assertEqual([p['typed_position'] for p in result['parents']],[0,1])
        self.assertEqual(len(self.visible(result)),4)
        self.assertNotEqual(result['parents'][0]['dom_handle'],result['parents'][1]['dom_handle'])

    def test_duplicate_id_within_parent_is_unresolved(self):
        result=bind_parents(self.extract(parent(ids=(0,0))),[typed()],1,1)
        self.assertEqual(result['status'],'unresolved')
        self.assertIn('duplicate_card_identity',result['parents'][0]['issues'])

    def test_noncontiguous_ids_keep_identity_and_visible_order(self):
        result=self.extract(parent(ids=(3,8,21)))
        cells=self.visible(result)
        self.assertEqual([c['card_id'] for c in cells],['vplaurlg3','vplaurlg8','vplaurlg21'])
        self.assertEqual([c['visible_index'] for c in cells],[0,1,2])

    def test_below_fold_cards_retained_for_fullpage_layout(self):
        result=self.extract(parent(style='top:1400px'))
        self.assertEqual(len(self.visible(result)),3)
        self.assertEqual(self.visible(result)[0]['visible_rect']['y'],1400)

    def test_unsupported_clip_path_is_unresolved(self):
        result=bind_parents(self.extract(parent(style='clip-path:circle(40%)')),[typed()],1,1)
        self.assertEqual(result['status'],'unresolved')
        self.assertIn('unsupported_clip_path',result['parents'][0]['issues'])

    def test_overlap_is_unresolved(self):
        result=bind_parents(self.extract(parent(ids=(0,1),card_styles={1:'left:100px'})),[typed()],1,1)
        self.assertEqual(result['status'],'unresolved')
        self.assertIn('overlapping_visible_cards',result['parents'][0]['issues'])

    def test_mixed_supported_and_unsupported_card_container_is_unresolved(self):
        unsupported='<div style="position:absolute;left:400px;width:200px;height:180px"><a id="vplaurlg9">Unrecognized third card</a></div>'
        result=bind_parents(self.extract(parent(ids=(0,1),suffix=unsupported)),[typed()],1,1)
        self.assertEqual(result['status'],'unresolved', 'A product link outside supported card containers must not disappear silently')
        self.assertTrue(result['parents'][0]['issues'])


    def test_comparison_service_directory_is_separate_from_product_cells(self):
        directory='<div class="pla-unit" style="left:600px"><div class="CAdYob">Compare providers</div></div>'
        result=bind_parents(self.extract(parent(ids=(0,1,2),style='width:800px',suffix=directory)),[typed(width=800)],1,1)
        self.assertEqual(result['status'],'scored')
        self.assertEqual(len(self.visible(result)),3)
        self.assertEqual(len(result['parents'][0]['non_product_units']),1)
        self.assertEqual(result['parents'][0]['non_product_units'][0]['reason'],'comparison_service_directory')
        self.assertEqual(result['parents'][0]['non_product_units'][0]['visible_rect']['w'],200)

    def test_directory_class_does_not_hide_unknown_image_card(self):
        unknown='<div class="pla-unit" style="left:400px"><div class="CAdYob">Unknown</div><img alt="product"></div>'
        result=bind_parents(self.extract(parent(ids=(0,1),suffix=unknown)),[typed()],1,1)
        self.assertEqual(result['status'],'unresolved')
        self.assertIn('missing_or_ambiguous_card_identity',result['parents'][0]['issues'])



    def test_known_right_rail_namespace_does_not_contaminate_top_parents(self):
        for wrapper in ['class="commercial-unit-desktop-rhs"','id="rhs"']:
            with self.subTest(wrapper=wrapper):
                rhs=f'<aside {wrapper}><a id="vplaurlg0">Right card</a></aside>'
                result=bind_parents(self.extract(rhs+parent()),[typed()],1,1)
                self.assertEqual(result['status'],'scored')
                self.assertEqual(result['unscoped_product_links'],0)
                self.assertEqual(len(self.visible(result)),3)

    def test_unknown_unscoped_product_link_remains_unresolved(self):
        result=bind_parents(self.extract('<aside><a id="vplaurlg8">Unknown</a></aside>'+parent()),[typed()],1,1)
        self.assertEqual(result['unscoped_product_links'],1)
        self.assertEqual(result['status'],'unresolved')



class ParentBindingTests(unittest.TestCase):
    @staticmethod
    def result():
        return dict(parents=[dict(dom_handle='parent-a',raw_rect=dict(x=100,y=100,w=600,h=180),visible_rect=dict(x=100,y=100,w=600,h=180),issues=[],cells=[dict(raw_rect=dict(x=100,y=100,w=200,h=180),visible_rect=dict(x=100,y=100,w=200,h=180))])],unscoped_product_links=0)

    def test_unique_anisotropic_coordinate_match_preserves_null_html_identity(self):
        result=bind_parents(self.result(),[typed(x=90,y=80,width=540,height=144)],.9,.8)
        self.assertEqual(result['status'],'scored')
        self.assertEqual(result['parents'][0]['typed_position'],0)
        self.assertIsNone(result['parents'][0]['typed_html_handle'])
        self.assertEqual(result['parents'][0]['cells'][0]['visible_rect_screenshot'],dict(x=90,y=80,w=180,h=144))

    def test_two_typed_matches_are_unresolved(self):
        result=bind_parents(self.result(),[typed(),typed(1)],1,1)
        self.assertEqual(result['status'],'unresolved')
        self.assertIsNone(result['parents'][0]['typed_position'])
        self.assertIn('ambiguous_typed_parent',result['parents'][0]['issues'])

    def test_missing_typed_parent_remains_in_report(self):
        result=bind_parents(self.result(),[],1,1)
        self.assertEqual(result['status'],'unresolved')
        self.assertEqual(len(result['parents']),1)
        self.assertIn('unmatched_typed_parent',result['parents'][0]['issues'])

    def test_two_dom_parents_cannot_claim_one_typed_parent(self):
        result=self.result()
        result['parents'].append(copy.deepcopy(result['parents'][0]))
        result['parents'][1]['dom_handle']='parent-b'
        result=bind_parents(result,[typed()],1,1)
        self.assertEqual(result['status'],'unresolved')
        self.assertTrue(all('duplicate_typed_parent_claim' in p['issues'] for p in result['parents']))

    def test_unmatched_typed_parent_is_not_silently_dropped(self):
        result=bind_parents(self.result(),[typed(),typed(1,y=600)],1,1)
        self.assertEqual(result['status'],'unresolved')
        self.assertEqual(result['unmatched_typed_positions'],[1])

    def test_off_axis_and_other_types_cannot_bind(self):
        other=typed();other['type']='organic'
        result=bind_parents(self.result(),[typed(-1),other],1,1)
        self.assertEqual(result['status'],'unresolved')
        self.assertIsNone(result['parents'][0]['typed_position'])


class ScreenshotFixtureTests(unittest.TestCase):
    @staticmethod
    def fixture():
        cells=[dict(visible_index=i,visible_rect=dict(x=x,y=10,w=10,h=20),visible_rect_screenshot=dict(x=x,y=10,w=10,h=20)) for i,x in enumerate([10,30])]
        row=dict(status='scored',inputs=dict(screenshot=dict(sha256='verified-screenshot')),parents=[dict(cells=cells)])
        case=dict(visible_count=2,rects_screenshot=[[10,10,20,30],[30,10,40,30]],tolerance_px=3,screenshot_sha256='verified-screenshot')
        return row,case

    def test_annotations_follow_visible_index_not_dom_iteration(self):
        row,case=self.fixture();row['parents'][0]['cells'].reverse()
        self.assertEqual(check_fixture(row,case),[])

    def test_count_equal_shift_is_rejected_at_boundaries(self):
        row,case=self.fixture()
        for c in row['parents'][0]['cells']:c['visible_rect_screenshot']['y']+=39
        self.assertEqual(check_fixture(row,case),['card_0_boundary','card_1_boundary'])

    def test_screenshot_hash_mismatch_is_not_a_boundary_only_negative(self):
        row,case=self.fixture();row['inputs']['screenshot']['sha256']='wrong-source'
        row['parents'][0]['cells'][0]['visible_rect_screenshot']['y']+=39
        errors=check_fixture(row,case)
        self.assertIn('screenshot_hash',errors)
        self.assertFalse(all(e.endswith('_boundary') for e in errors))

    def test_missing_card_is_not_a_boundary_only_negative(self):
        row,case=self.fixture();row['parents'][0]['cells'].pop()
        errors=check_fixture(row,case)
        self.assertIn('visible_count',errors);self.assertIn('annotation_count',errors)
        self.assertFalse(all(e.endswith('_boundary') for e in errors))



if __name__=='__main__':
    unittest.main()
