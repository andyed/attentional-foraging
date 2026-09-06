import copy,unittest
from summarize_carousel_corpus import reconcile


def fixture():
    inputs={k:{'path':k,'sha256':'same'} for k in ['html','screenshot','metadata','typed']}
    box={'x':10,'y':10,'w':200,'h':100}
    cells=[{'aligned_visible_rect_screenshot':box,'visible_rect_screenshot':box,'visible_fraction':1} for _ in range(2)]
    candidate={'manifest':{'trial_ids':['trial-a'],'exclusions_sha256':'same'},'trials':[{
        'trial_id':'trial-a','status':'scored','registration_status':'accepted','analysis_eligible':True,'diagnostic_outcome':'accepted','inputs':inputs,
        'parents':[{'cells':cells,'issues':[],'screenshot_registration':{'dy':0,'reason':None}}]}]}
    reference={'manifest':{'trial_ids':['trial-a'],'exclusions_sha256':'same'},'trials':[{
        'tid':'trial-a','analysis_eligible':True,'inputs':inputs,'ratio_x':1,'ratio_y':1,'typed_top_count':1,
        'cell_status':'scored','dom_cells':2,'export_cells':1,'cell_count_agree':False,
        'measurement':{'cell_parents':[{'dom_parent_index':0,'rect':box,'count':2,'issues':[]}],'cell_unscoped_links':0}}]}
    inventory={'trial-a':{'count':2,'issues':[],'parents':{'0':{'rect':box,'count':2}}}}
    return candidate,reference,inventory

class CorpusSummaryTests(unittest.TestCase):
    def test_matched_comparison_keeps_legacy_shortfall(self):
        out=reconcile(*fixture())['summary']['eligible_top']
        self.assertEqual((out['trials'],out['legacy_match'],out['legacy_short'],out['candidate_match']),(1,0,1,1))

    def test_rejected_candidate_stays_in_fixed_denominator(self):
        c,r,i=fixture();c['trials'][0].update(diagnostic_outcome='rejected',registration_status='rejected')
        i['trial-a']['count']=0;i['trial-a']['parents']['0']['count']=0
        out=reconcile(c,r,i)['summary']['eligible_top']
        self.assertEqual((out['trials'],out['candidate_match'],out['candidate_cards']),(1,0,0))

    def test_missing_row_does_not_shrink_denominator(self):
        c,r,i=fixture();c['trials']=[]
        with self.assertRaisesRegex(ValueError,'incomplete'):reconcile(c,r,i)

    def test_excluded_candidate_cannot_leak_into_csv(self):
        c,r,i=fixture();c['trials'][0]['analysis_eligible']=False;r['trials'][0]['analysis_eligible']=False
        with self.assertRaisesRegex(ValueError,'excluded trial leaked'):reconcile(c,r,i)
        out=reconcile(c,r,{})['summary']
        self.assertEqual((out['excluded_trials'],out['eligible_top']['trials'],out['excluded_top']['candidate_cards']),(1,0,0))

    def test_changed_sources_cannot_be_compared(self):
        c,r,i=fixture();r=copy.deepcopy(r);r['trials'][0]['inputs']['html']['sha256']='different'
        with self.assertRaisesRegex(ValueError,'different or missing html'):reconcile(c,r,i)

    def test_duplicate_measurement_is_refused(self):
        c,r,i=fixture();c['trials']*=2
        with self.assertRaisesRegex(ValueError,'duplicate measured'):reconcile(c,r,i)

    def test_accepted_csv_cannot_disagree_with_geometry(self):
        c,r,i=fixture();c['trials'][0]['parents'][0]['cells'].pop()
        with self.assertRaisesRegex(ValueError,'CSV and accepted geometry differ'):reconcile(c,r,i)

    def test_changed_parent_grain_is_refused(self):
        c,r,i=fixture();r['trials'][0]['typed_top_count']=2
        with self.assertRaisesRegex(ValueError,'multiple-parent grain'):reconcile(c,r,i)

    def test_true_absence_is_not_a_card_success(self):
        c,r,i=fixture();c['trials'][0].update(diagnostic_outcome='absent',registration_status='not_applicable',parents=[])
        r['trials'][0].update(typed_top_count=0,dom_cells=0,export_cells=0,cell_status='absent',cell_count_agree=None)
        r['trials'][0]['measurement']['cell_parents']=[]
        out=reconcile(c,r,{})['summary']
        self.assertEqual((out['eligible_without_top'],out['eligible_top']['trials'],out['eligible_top']['candidate_match']),(1,0,0))

    def test_shared_missing_provenance_is_not_a_match(self):
        c,r,i=fixture();del c['trials'][0]['inputs']['metadata']
        with self.assertRaisesRegex(ValueError,'missing metadata provenance'):reconcile(c,r,i)

    def test_rejected_export_cells_are_not_silently_hidden(self):
        c,r,i=fixture();c['trials'][0].update(diagnostic_outcome='rejected',registration_status='rejected')
        with self.assertRaisesRegex(ValueError,'non-admitted cells leaked'):reconcile(c,r,i)

    def test_unknown_product_links_are_not_confirmed_absence(self):
        c,r,i=fixture();c['trials'][0].update(status='unresolved',diagnostic_outcome='unresolved',registration_status='not_attempted',parents=[])
        r['trials'][0].update(typed_top_count=0,dom_cells=0,export_cells=0,cell_status='unresolved',cell_count_agree=None)
        r['trials'][0]['measurement'].update(cell_parents=[],cell_unscoped_links=1)
        out=reconcile(c,r,{})['summary']
        self.assertEqual((out['eligible_without_top'],out['eligible_unresolved_top_presence']),(0,1))

if __name__=='__main__':unittest.main()
