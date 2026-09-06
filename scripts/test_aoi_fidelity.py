"""Independent count-auditor regressions; synthetic DOM and temporary CSV only."""
from __future__ import annotations
import contextlib
import csv
import io
from pathlib import Path
import tempfile
import unittest

from playwright.sync_api import sync_playwright
from aoi_fidelity import JS, cellsplit_inventory, compare_cells, cell_summary, report

STYLE='''<style>html,body{margin:0;padding:0}.commercial-unit-desktop-top{position:absolute;left:100px;top:100px;width:600px;height:180px;overflow:hidden}.track{position:relative;width:1200px;height:180px}.pla-unit{position:absolute;top:0;width:200px;height:180px}.image{display:block;width:90px;height:60px}</style>'''

def strip(name='top', ids=(0,1,2,3,4), style='', card_style='', extra=''):
    cards=''.join(f'<div class="pla-unit" style="left:{n*200}px;{card_style}"><a id="vplaurlg{i}" class="image"></a></div>' for n,i in enumerate(ids))
    return f'<div id="{name}" class="commercial-unit-desktop-top" style="{style}"><div class="track">{cards}{extra}</div></div>'


def dom_parent(index=0, count=3, x=100,y=100,w=600,h=180,issues=None):
    return dict(dom_parent_index=index,count=count,rect=dict(x=x,y=y,w=w,h=h),issues=issues or [])


def dom(*parents, unscoped=0):
    return dict(cell_parents=list(parents),cell_unscoped_links=unscoped)


def exported(*entries):
    parents={str(rank):dict(count=count,rect=dict(x=x,y=y,w=600,h=180)) for rank,count,x,y in entries}
    return dict(count=sum(p['count'] for p in parents.values()),parents=parents,issues=[])


class BrowserCountTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw=sync_playwright().start()
        cls.browser=cls.pw.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close();cls.pw.stop()

    def setUp(self):
        self.context=self.browser.new_context(viewport={'width':1389,'height':1024})
        self.context.route('http://**/*',lambda route: route.abort())
        self.context.route('https://**/*',lambda route: route.abort())
        self.page=self.context.new_page();self.addCleanup(self.context.close)

    def extract(self,html=None,setup=None):
        self.page.set_content(STYLE+(strip() if html is None else html))
        if setup:self.page.evaluate(setup)
        return self.page.evaluate(JS,dict(cards={},mainMaxX=850,clickXpath=None))

    def test_complete_card_count_includes_partial_card_with_hidden_image(self):
        result=self.extract(strip(style='width:650px'),"document.getElementById('top').scrollLeft=150")
        # Card0 has50px left visible though its90px image has completely left the strip.
        self.assertEqual(result['cell_parents'][0]['count'],4)
        self.assertEqual(result['cell_parents'][0]['issues'],[])

    def test_fully_left_clipped_card_not_counted(self):
        result=self.extract(setup="document.getElementById('top').scrollLeft=200")
        self.assertEqual(result['cell_parents'][0]['count'],3)

    def test_nested_clip_intersection_counts_trailing_fragment(self):
        html='<div style="position:absolute;left:100px;top:100px;width:450px;height:180px;overflow:hidden">'+strip(style='left:0;top:0;width:650px')+'</div>'
        self.assertEqual(self.extract(html)['cell_parents'][0]['count'],3)

    def test_hidden_parent_is_observed_zero(self):
        result=self.extract(strip(style='visibility:hidden'))
        self.assertEqual(result['cell_parents'][0]['count'],0)
        self.assertEqual(result['cell_parents'][0]['issues'],[])

    def test_repeated_ids_are_independent_between_parents(self):
        result=self.extract(strip(ids=(0,1))+strip('second',ids=(0,1,2),style='top:400px'))
        self.assertEqual([p['count'] for p in result['cell_parents']],[2,3])
        self.assertTrue(all(not p['issues'] for p in result['cell_parents']))

    def test_same_id_different_cards_is_ambiguous(self):
        result=self.extract(strip(ids=(0,0)))
        self.assertIn('duplicate_card_identity',result['cell_parents'][0]['issues'])

    def test_mixed_unsupported_card_is_reported(self):
        extra='<div style="position:absolute;left:400px"><a id="vplaurlg8">Unknown card</a></div>'
        result=self.extract(strip(ids=(0,1),extra=extra))
        self.assertIn('unsupported_card_container',result['cell_parents'][0]['issues'])

    def test_clip_path_is_unresolved(self):
        result=self.extract(strip(style='clip-path:circle(50%)'))
        self.assertIn('unsupported_clip_path',result['cell_parents'][0]['issues'])

    def test_below_fold_is_not_a_vertical_visibility_gate(self):
        result=self.extract(strip(style='top:1400px'))
        self.assertEqual(result['cell_parents'][0]['count'],3)

    def test_comparison_directory_does_not_add_a_product(self):
        extra='<div class="pla-unit" style="left:600px"><div class="CAdYob">Comparison service</div></div>'
        result=self.extract(strip(ids=(0,1,2),style='width:800px',extra=extra))
        self.assertEqual(result['cell_parents'][0]['count'],3)
        self.assertEqual(result['cell_parents'][0]['issues'],[])


    def test_known_right_rail_links_do_not_change_top_counts_or_status(self):
        for wrapper in ['class="commercial-unit-desktop-rhs"','id="rhs"']:
            with self.subTest(wrapper=wrapper):
                rhs=f'<aside {wrapper}><a id="vplaurlg0">Right card</a></aside>'
                result=self.extract(rhs+strip())
                self.assertEqual(result['cell_parents'][0]['count'],3)
                self.assertEqual(result['cell_unscoped_links'],0)
                self.assertEqual(result['cell_offaxis_links'],1)
                self.assertEqual(compare_cells(result,exported((0,3,100,100)),1,1)['cell_status'],'scored')

    def test_right_rail_only_page_is_absent_from_top_carousel_scope(self):
        result=self.extract('<aside id="rhs"><a id="vplaurlg0">Right card</a></aside>')
        self.assertEqual(result['cell_parents'],[])
        self.assertEqual(result['cell_unscoped_links'],0)
        self.assertEqual(compare_cells(result,dict(count=0,parents={},issues=[]),1,1)['cell_status'],'absent')

    def test_unknown_unscoped_link_remains_unresolved(self):
        result=self.extract('<aside><a id="vplaurlg8">Unknown</a></aside>'+strip())
        self.assertEqual(result['cell_unscoped_links'],1)
        self.assertEqual(compare_cells(result,exported((0,3,100,100)),1,1)['cell_status'],'unresolved')



class InventoryTests(unittest.TestCase):
    columns=['trial_id','role','parent_etype','etype','main_axis','parent_rank','cell_index','left_x','right_x','top_y','bottom_y','n_cells']

    def inventory(self,rows):
        with tempfile.TemporaryDirectory(prefix='carousel-count-test-') as tmp:
            p=Path(tmp)/'cells.csv'
            with p.open('w') as f:
                writer=csv.DictWriter(f,fieldnames=self.columns);writer.writeheader();writer.writerows(rows)
            return cellsplit_inventory(p)

    @staticmethod
    def row(role='parent',trial='fixture',parent_type='dd_top',main='True',rank='0',index='',**changes):
        row=dict(trial_id=trial,role=role,parent_etype=parent_type,etype=parent_type if role=='parent' else parent_type+'_cell',main_axis=main,parent_rank=rank,cell_index=index,left_x='100',right_x='700',top_y='100',bottom_y='280',n_cells='0')
        row.update(changes);return row

    def test_only_top_main_cells_count_and_cell_zero_is_valid(self):
        rows=[self.row(),self.row('cell',index='0'),self.row('cell',index='1'),self.row('cell',parent_type='organic',index='0'),self.row('cell',parent_type='dd_right',main='False',index='0')]
        inv=self.inventory(rows)['fixture']
        self.assertEqual(inv['count'],2)
        self.assertEqual(inv['parents']['0']['count'],2)
        self.assertEqual(inv['issues'],[])

    def test_present_zero_and_missing_trial_are_distinct(self):
        inv=self.inventory([self.row(),self.row(trial='right-only',parent_type='dd_right',main='False')])
        self.assertEqual(inv['fixture']['count'],0)
        self.assertEqual(inv['fixture']['parents']['0']['count'],0)
        self.assertEqual(inv['right-only']['parents'],{})
        self.assertNotIn('missing',inv)

    def test_missing_file_does_not_fabricate_known_zero_trials(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(cellsplit_inventory(Path(tmp)/'absent.csv'),{})

    def test_missing_index_is_explicit_instead_of_silently_dropped(self):
        inv=self.inventory([self.row(),self.row('cell')])['fixture']
        self.assertEqual(inv['count'],1)
        self.assertIn('missing_cell_index',inv['issues'])

    def test_duplicate_parent_is_explicit(self):
        inv=self.inventory([self.row(),self.row()])['fixture']
        self.assertIn('duplicate_export_parent',inv['issues'])

    def test_duplicate_cell_index_is_not_normal_count_evidence(self):
        inv=self.inventory([self.row(),self.row('cell',index='0'),self.row('cell',index='0')])['fixture']
        self.assertTrue(inv['issues'],'Repeated per-parent cell_index requires an export issue')
        result=compare_cells(dom(dom_parent(count=2)),inv,1,1)
        self.assertEqual(result['cell_status'],'unresolved')

    def test_nonfinite_or_nonpositive_parent_geometry_is_unresolved(self):
        for changes in [dict(left_x='nan'),dict(right_x='90'),dict(bottom_y='100')]:
            with self.subTest(changes=changes):
                inv=self.inventory([self.row(**changes),self.row('cell',index='0')])['fixture']
                self.assertTrue(inv['issues'],'Malformed parent geometry requires an export issue')
                self.assertEqual(compare_cells(dom(dom_parent()),inv,1,1)['cell_status'],'unresolved')


    def test_malformed_indices_are_unresolved(self):
        for index in ['oops','-1','1.5','nan']:
            with self.subTest(index=index):
                inv=self.inventory([self.row(),self.row('cell',index=index)])['fixture']
                self.assertIn('invalid_cell_index',inv['issues'])
                self.assertEqual(compare_cells(dom(dom_parent(count=1)),inv,1,1)['cell_status'],'unresolved')



class ComparisonLedgerTests(unittest.TestCase):
    def test_observed_zero_is_scored_and_detects_export_overcount(self):
        r=compare_cells(dom(dom_parent(count=0)),exported((0,3,100,100)),1,1)
        self.assertEqual(r['cell_status'],'scored')
        self.assertFalse(r['cell_count_agree'])
        self.assertEqual(r['cell_parent_comparisons'][0]['dom_cells'],0)

    def test_missing_export_is_scored_short_and_retained(self):
        r=compare_cells(dom(dom_parent(count=3)),None,1,1)
        self.assertEqual(r['cell_status'],'scored')
        self.assertFalse(r['cell_export_present'])
        self.assertEqual(r['export_cells'],0)
        self.assertFalse(r['cell_count_agree'])
        self.assertEqual(r['cell_parent_comparisons'][0]['status'],'missing_export_parent')

    def test_no_carousel_is_absent_not_successful_agreement(self):
        r=compare_cells(dom(),dict(count=0,parents={},issues=[]),1,1)
        self.assertEqual(r['cell_status'],'absent')
        self.assertIsNone(r['cell_count_agree'])

    def test_unrecognized_typed_parent_is_unresolved_not_observed_zero(self):
        r=compare_cells(dom(),None,1,1,typed_top_count=1)
        self.assertEqual(r['cell_status'],'unresolved')
        self.assertIn('unresolved_typed_parent',r['cell_issues'])

    def test_distinct_parents_compare_separately_when_totals_equal(self):
        r=compare_cells(dom(dom_parent(0,2),dom_parent(1,3,y=400)),exported((0,3,100,100),(1,2,100,400)),1,1)
        self.assertEqual(r['dom_cells'],r['export_cells'])
        self.assertEqual(r['cell_status'],'scored')
        self.assertFalse(r['cell_count_agree'])
        self.assertEqual([(p['dom_cells'],p['export_cells']) for p in r['cell_parent_comparisons']],[(2,3),(3,2)])

    def test_two_export_matches_are_unresolved(self):
        r=compare_cells(dom(dom_parent()),exported((0,3,100,100),(1,3,100,100)),1,1)
        self.assertEqual(r['cell_status'],'unresolved')
        self.assertIn('ambiguous_export_parent',r['cell_issues'])

    def test_two_dom_parents_cannot_claim_same_export(self):
        r=compare_cells(dom(dom_parent(),dom_parent(1)),exported((0,3,100,100)),1,1)
        self.assertEqual(r['cell_status'],'unresolved')
        self.assertIn('ambiguous_export_parent',r['cell_issues'])

    def test_export_only_parent_remains_in_comparison_ledger(self):
        r=compare_cells(dom(),exported((0,3,100,100)),1,1)
        self.assertEqual(r['cell_status'],'scored')
        self.assertFalse(r['cell_count_agree'])
        self.assertEqual(r['cell_parent_comparisons'][0]['status'],'export_only_parent')

    def test_report_denominators_include_zero_missing_and_unresolved(self):
        rows=[compare_cells(dom(dom_parent()),exported((0,3,100,100)),1,1),
              compare_cells(dom(dom_parent(count=0)),exported((0,3,100,100)),1,1),
              compare_cells(dom(dom_parent()),None,1,1),
              compare_cells(dom(),dict(count=0,parents={},issues=[]),1,1),
              compare_cells(dom(),None,1,1,typed_top_count=1)]
        summary=cell_summary(rows)
        self.assertEqual(summary['requested_trials'],5)
        self.assertEqual(summary['scored_trials'],3)
        self.assertEqual(summary['agree_trials'],1)
        self.assertEqual(summary['unresolved_trials'],1)
        self.assertEqual(summary['absent_trials'],1)
        self.assertEqual(summary['missing_export_trials'],2)
        self.assertEqual(summary['compared_parents'],3)
        self.assertEqual(summary['short_parents'],1)
        self.assertEqual(summary['over_parents'],1)
        for r in rows:r.update(click_ok=None,aoi_iou_median=None)
        output=io.StringIO()
        with contextlib.redirect_stdout(output):report(rows)
        self.assertIn('not boundary or identity fidelity',output.getvalue())
        self.assertIn('"requested_trials": 5',output.getvalue())


if __name__=='__main__':
    unittest.main()
