"""Key Claims rows for NB37 (engagement states, continuation, periphery, kernel)
and NB38 (moves between results), computed from the producers' summary JSONs.

Used twice: by ``build_key_claims_notebooks_37_38.py`` to write each notebook's
Key Claims markdown cell, and by the notebooks' final code cell to print the
same table from the same files. The markdown is therefore a copy of executed
output, never hand-typed. Every value carries its source file; ``inputs()``
lists the files with SHA256 so a notebook can assert it reads what it was
built against.
"""
from __future__ import annotations
import hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'scripts/output'

FILES_37 = {
    'census': OUT / 'engagement_state_census/gate_200px/summary.json',
    'census_cm24': OUT / 'engagement_state_census/kernel_boundary_cm_24/summary.json',
    'census_cm43': OUT / 'engagement_state_census/kernel_boundary_cm_43/summary.json',
    'cont': OUT / 'engagement_continuation/gate_200px/summary.json',
    'cont_cm24': OUT / 'engagement_continuation/kernel_boundary_cm_24/summary.json',
    'cont_cm43': OUT / 'engagement_continuation/kernel_boundary_cm_43/summary.json',
    'periph': OUT / 'periphery_navigates/summary.json',
    'periph43': OUT / 'periphery_navigates/summary_px43.json',
    'kernel': OUT / 'pai_kernel_validation/summary.json',
    'probe': OUT / 'pai_deferred_probe/summary_w1000_full.json',
    'probe_cm24': OUT / 'pai_deferred_probe/summary_w1000_full_boundary_cm_24.json',
    'probe_cm43': OUT / 'pai_deferred_probe/summary_w1000_full_boundary_cm_43.json',
    'bold': OUT / 'bold_term_density/summary.json',
}
FILES_38 = {
    'ret_cm24': OUT / 'return_is_memory/summary_boundary_cm_24.json',
    'ret_spec': OUT / 'return_is_memory/summary.json',
    'major': OUT / 'major_saccade_selection/summary.json',
    'next': OUT / 'next_action_by_position/summary.json',
    'survey': OUT / 'survey_above_fold/summary.json',
}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def inputs(files: dict) -> dict:
    return {k: {'path': str(p.relative_to(ROOT)), 'sha256': sha(p)} for k, p in files.items()}


def load(files: dict) -> dict:
    return {k: json.load(open(p)) for k, p in files.items()}


P = lambda x, d=0: f'{x * 100:.{d}f} %'
F = lambda x, d=3: f'{x:.{d}f}'
CI = lambda ci, d=3: f'[{ci[0]:+.{d}f}, {ci[1]:+.{d}f}]'
N = lambda x: f'{int(round(x)):,}'


def rows_37(J: dict) -> list[tuple[str, str, str]]:
    c = J['census']; k = J['cont']; a = J['periph']['A_skip_is_layout']; b = J['periph']['B_survey_map']
    kv = J['kernel']; pr = J['probe']; pr24 = J['probe_cm24']; pr43 = J['probe_cm43']; bd = J['bold']
    sh = c['census_unfix']['ALL']['share']; split = c['never_fixated_onscreen_split_unfix']['ALL']; pt = c['participant_peripheral_share']
    ch = c['chiir_never_fixated_rows']; R = k['continuation']['reach']; C1 = k['continuation']['continuation']['fixation_first_pass']
    cost = k['cost_by_state']; pm = k['position_matched_peripheral_split']; rt = k['relevance_by_state']['tests']
    kern = {x['kernel']: x for x in kv['kernels']}; eq2 = kern['published eq2, ungated']
    ecc = [x for x in kv['kernels'] if x['kernel'] != 'published eq2, ungated']
    pp = pr['paired']['post_M4_7_plus_pai_x500_vs_M4_7']; pp24 = pr24['paired']['post_M4_7_plus_pai_x500_vs_M4_7']; pp43 = pr43['paired']['post_M4_7_plus_pai_x500_vs_M4_7']
    bt = bd['by_census']['within_8deg']['tests']
    b43 = J['periph43']['B_survey_map']
    cm24, cm43 = J['census_cm24']['census_unfix']['ALL'], J['census_cm43']['census_unfix']['ALL']
    pm24, pm43 = J['cont_cm24']['position_matched_peripheral_split'], J['cont_cm43']['position_matched_peripheral_split']
    cs = lambda st: f"{N(cost[st]['gaze_dwell_ms_median'])} [{N(cost[st]['gaze_dwell_ci'][0])}, {N(cost[st]['gaze_dwell_ci'][1])}]"
    return [
        ('K1', 'Population and primary rule (`engagement_state_census.py`, gate_200px)',
         f"{N(c['population']['rows'])} result slots, {N(c['population']['trials'])} trials, {c['population']['participants']} participants; kernel: {c['kernel']}; rule: {c['thresholds']['rule']}"),
        ('K2', 'Five-state census, share of all slots (matched-opportunity rule on unfixated time)',
         f"never on screen {P(sh['never_onscreen'])}, brief {P(sh['brief_onscreen'])}, unsampled {P(sh['unsampled'])}, peripheral {P(sh['peripheral'])}, rejected {P(sh['rejected'])}, deferred {P(sh['deferred'])}, clicked {P(sh['clicked'])}; opportunity unknown {N(c['census_unfix']['ALL']['unknown_opportunity'])} slots ({P(c['census_unfix']['ALL']['unknown_opportunity'] / c['population']['rows'])})"),
        ('K3', 'Peripheral tier among on-screen never-fixated slots; per-participant trait',
         f"{N(split['peripheral'])} of {N(split['never_fixated_onscreen'])} = {P(split['peripheral_share'])}; participant median {F(pt['median'], 2)}, IQR [{F(pt['iqr'][0], 2)}, {F(pt['iqr'][1], 2)}], range {F(pt['min'], 2)}–{F(pt['max'], 2)} (n = {pt['n_participants']} with enough slots)"),
        ('K4', "CHIIR carve's 660 approached-never-fixated rows, by state",
         f"peripheral {ch['unfix']['peripheral']}, unsampled {ch['unfix']['unsampled']}, opportunity unknown {ch['unfix']['unknown_opportunity']}, never on screen {ch['unfix']['never_onscreen']}, brief {ch['unfix']['brief_onscreen']} (n = {ch['n']})"),
        ('K5', 'Reach at result 10, five ways (`engagement_continuation.py`)',
         f"viewport {P(R['viewport'][9])}, periphery (intake within 200 px) {P(R['periphery'][9])}, fixation any time {P(R['fixation'][9])}, fixation first pass {P(R['fixation_first_pass'][9])}, cursor {P(R['cursor'][9])} (opportunity-known trials n = {N(k['population']['trials_opportunity_known'])})"),
        ('K6', 'First-pass continuation C(i), the strict C/W/L version',
         f"{F(C1[0], 2)} at the top declining to {F(min(C1[-2:]), 2)}–{F(max(C1[-2:]), 2)} at the bottom; full vector {[round(x, 2) for x in C1]}"),
        ('K7', 'Examination cost tiers, median gaze dwell ms [95 % CI] by state, and share approached by the cursor',
         f"peripheral {cs('peripheral')} / rejected {cs('rejected')} / deferred {cs('deferred')} / clicked {cs('clicked')}; approached {P(cost['peripheral']['approached_share'])} / {P(cost['rejected']['approached_share'])} / {P(cost['deferred']['approached_share'])} / {P(cost['clicked']['approached_share'])}"),
        ('K8', 'Position-matched peripheral share and skipped-vs-read intake at matched position',
         f"share {P(pm['peripheral_share'], 1)} (n = {N(pm['n'])}); matched AUC skipped vs read {F(pm['matched_auc_skipped_vs_read_weighted'])} (skipped results get less near-peripheral intake)"),
        ('K9', 'Relevance by state (query-text cosine, organic), Mann–Whitney AUC (p)',
         f"peripheral vs unsampled {F(rt['peripheral_vs_unsampled_cos']['auc'])} ({F(rt['peripheral_vs_unsampled_cos']['p'], 2)}); peripheral vs rejected {F(rt['peripheral_vs_rejected_cos']['auc'])} ({F(rt['peripheral_vs_rejected_cos']['p'], 2)}); deferred vs clicked, relevance rank {F(rt['deferred_vs_clicked_rel_rank']['auc'])} ({rt['deferred_vs_clicked_rel_rank']['p']:.1e})"),
        ('K10', 'Skipping is reading order and opportunity (`periphery_navigates.py` A), LOSO AUC',
         f"pool {N(a['pool']['n'])} on-screen non-clicked slots; position only {F(a['all_slots']['position only'])}; layout without residence {F(a['all_slots']['layout without residence (position+height+etype)'])}, paired Δ {a['all_slots']['paired layout-without-residence vs position']['mean_delta']:+.3f} {CI(a['all_slots']['paired layout-without-residence vs position']['ci95'])}; residence only {F(a['all_slots']['residence only'])}; layout + residence {F(a['all_slots']['layout (position+height+residence+etype)'])}; organic subset (n = {N(a['organic_slots']['n'])}): layout {F(a['organic_slots']['layout without residence (position+height)'])}, content {F(a['organic_slots']['content (query cosine + snippet length + bold share)'])}, layout + content {F(a['organic_slots']['layout + content'])} (Δ {a['organic_slots']['paired layout+content vs layout']['mean_delta']:+.3f} {CI(a['organic_slots']['paired layout+content vs layout']['ci95'])})"),
        ('K11', 'The survey leaves a proximity map (`periphery_navigates.py` B), LOSO AUC',
         f"{N(b['candidates'])} candidates, {N(b['later_fixated'])} later fixated; position only {F(b['auc']['position only'])}; survey intake rank {F(b['auc']['survey intake (within-trial rank)'])}; survey gaze-distance rank {F(b['auc']['survey gaze distance (rank)'])}; position + intake {F(b['auc']['position + intake rank'])} (Δ over position {b['paired']['position+intake vs position']['mean_delta']:+.3f} {CI(b['paired']['position+intake vs position']['ci95'])}); position + distance {F(b['auc']['position + distance rank'])}; both {F(b['auc']['position + both ranks'])} (Δ over position + distance {b['paired']['position+both vs position+distance']['mean_delta']:+.3f} {CI(b['paired']['position+both vs position+distance']['ci95'])}); top-intake candidate fixated later {P(b['within_trial_top_vs_bottom_intake_later_fixated']['top'])} vs bottom {P(b['within_trial_top_vs_bottom_intake_later_fixated']['bottom'])} (n = {N(b['within_trial_top_vs_bottom_intake_later_fixated']['n_trials'])} trials)"),
        ('K12', 'Kernel validation on later fixation (`pai_kernel_validation.py`)',
         f"published Eq. 2 ungated: intake alone {F(eq2['intake rank alone'])}, gain over position {eq2['gain over position']['mean_delta']:+.3f} {CI(eq2['gain over position']['ci95'])}, gain over position + distance {eq2['gain over position + distance']['mean_delta']:+.3f} {CI(eq2['gain over position + distance']['ci95'])}; every eccentricity-aware kernel ({len(ecc)} variants: gated Eq. 2, boundary falloff at 1/2/4°, hard gates): intake alone {F(min(x['intake rank alone'] for x in ecc))}–{F(max(x['intake rank alone'] for x in ecc))}, gain over position + distance {min(x['gain over position + distance']['mean_delta'] for x in ecc):+.3f} to {max(x['gain over position + distance']['mean_delta'] for x in ecc):+.3f}"),
        ('K13', 'PAI on the deferred split (`pai_deferred_probe.py`, 1 s post window, full windows only)',
         f"gate: carve M4-7 reproduced at {F(pr['gate']['reproduced'], 4)} (Δ {pr['gate']['delta']:.4f}, n = {N(pr['gate']['n_records'])}); M4-7 pooled {F(pr['scores']['post']['M4_7_cursor']['pooled_auc'])} on {N(pr['scores']['post']['M4_7_cursor']['n_records'])} rows; paired M4-7 + PAI vs M4-7: published kernel {pp['mean_delta']:+.4f} {CI(pp['bootstrap_ci95'], 4)} (p {pp['wilcoxon_two_sided_p']:.3f}); boundary kernel 24 px/° {pp24['mean_delta']:+.4f} {CI(pp24['bootstrap_ci95'], 4)}; 43 px/° {pp43['mean_delta']:+.4f} {CI(pp43['bootstrap_ci95'], 4)}"),
        ('K14', 'Bold query-term density by state, NULL (`bold_term_density.py`)',
         f"{N(bd['corpus']['snapshots'])} snapshots, {N(bd['corpus']['results'])} results, bold share median {F(bd['corpus']['bold_share_median'], 2)}, em in titles {P(bd['corpus']['em_in_title_share'])}; AUC (p): peripheral vs unsampled {F(bt['peripheral_vs_unsampled_bold_share']['auc'])} ({F(bt['peripheral_vs_unsampled_bold_share']['p'], 2)}), fixated vs on-screen unfixated {F(bt['fixated_vs_onscreen_unfixated_bold_share']['auc'])} ({F(bt['fixated_vs_onscreen_unfixated_bold_share']['p'], 2)}), rejected vs deferred {F(bt['rejected_vs_deferred_bold_share']['auc'])} ({F(bt['rejected_vs_deferred_bold_share']['p'], 2)}), deferred vs clicked {F(bt['deferred_vs_clicked_bold_share']['auc'])} ({F(bt['deferred_vs_clicked_bold_share']['p'], 2)})"),
        ('K15', 'Soft-falloff kernel at 24 vs 43 px/° (2026-09-15 rerun)',
         f"survey map, position + intake: {F(b['auc']['position + intake rank'])} vs {F(b43['auc']['position + intake rank'])}; soft-variant census peripheral slots {N(cm24['peripheral'])} vs {N(cm43['peripheral'])}; position-matched share {P(pm24['peripheral_share'], 1)} vs {P(pm43['peripheral_share'], 1)}, matched AUC {F(pm24['matched_auc_skipped_vs_read_weighted'])} vs {F(pm43['matched_auc_skipped_vs_read_weighted'])}; deferred-probe paired Δ {pp24['mean_delta']:+.4f} vs {pp43['mean_delta']:+.4f}. Primary (hard-gate) census does not use the kernel"),
    ]


def rows_38(J: dict) -> list[tuple[str, str, str]]:
    r = J['ret_cm24']; rs = J['ret_spec']; m = J['major']; nx = J['next']; sv = J['survey']
    pe = r['paired_return_minus_entry']; pl = r['paired_return_minus_entry_long_returns']; pop = r['population']
    lo, am, ra = pe['landing_offset_px'], pe['saccade_amp_px'], pe['pai_pre_rate']; rsp = rs['paired_return_minus_entry']['pai_pre_rate']
    adj = r['return_ranks_jumped_hist']['1'] / pop['events']; sp = r['ramp_vs_precision_spearman']
    B = m['bins']; bn = ['minor <100', '100-300', 'major 300-600', 'major >600']; md = m['prev_fix_major_minus_minor']
    A = nx['A_next_fixation']; Bv = nx['B_first_visit_end']; D = nx['D_after_back']
    deep = [Bv[str(p)] for p in range(2, 11)]
    rng = lambda key, d=0: f"{P(min(x[key] for x in deep), d)}–{P(max(x[key] for x in deep), d)}"
    at = sv['ad_topped']; comp = sv['composition_ad_top']; oth = sv['composition_other_top']; ff = sv['first_fixation']; ppr = at['per_participant_rate']
    return [
        ('K1', 'Returns, all (`return_is_memory.py`, boundary kernel 24 px/°; landing and amplitude are kernel-free)',
         f"{N(pop['events'])} return events on {N(pop['deferred_rows_seen'])} deferred slots, {pop['participants']} participants; landing offset return {lo['return_median']} vs entry {lo['entry_median']} px, Δ {lo['diff_median']:+.1f} {CI(lo['diff_median_ci95_cluster'], 1)} (participants with Δ < 0: {lo['participants_with_median_diff_lt_0']}/{lo['n_participants_ge5_rows']}); amplitude Δ {am['diff_median']:+.1f} px {CI(am['diff_median_ci95_cluster'], 1)}; {P(adj)} of returns come from the adjacent result"),
        ('K2', 'Long returns (≥ 2 ranks) land at first-entry precision from 2.4× the distance',
         f"n = {N(pop['long_returns_ge2_ranks'])}; landing Δ {pl['landing_offset_px']['diff_median']:+.1f} px {CI(pl['landing_offset_px']['diff_median_ci95_cluster'], 1)} (p {pl['landing_offset_px']['wilcoxon_p']:.2f}); amplitude {N(pl['saccade_amp_px']['return_median'])} vs {N(pl['saccade_amp_px']['entry_median'])} px; gaze distance in the prior second {N(pl['gaze_dist_pre_px']['return_median'])} vs {N(pl['gaze_dist_pre_px']['entry_median'])} px"),
        ('K3', 'Peripheral ramp before the return, and ramp vs precision',
         f"all returns, boundary kernel: Δ {ra['diff_median']:+.1f} mass/s {CI(ra['diff_median_ci95_cluster'], 1)}; published kernel: Δ {rsp['diff_median']:+.1f} {CI(rsp['diff_median_ci95_cluster'], 1)}; long returns, boundary kernel: Δ {pl['pai_pre_rate']['diff_median']:+.1f} {CI(pl['pai_pre_rate']['diff_median_ci95_cluster'], 1)} (weaker ramp); Spearman ramp vs landing offset: entry {sp['entry']['spearman_rho']:+.3f} (p {sp['entry']['p']:.2f}), return {sp['return']['spearman_rho']:+.3f} (p {sp['return']['p']:.2f})"),
        ('K4', 'Ambient timing before a long jump (`major_saccade_selection.py`): fixation before a first-entry move, median ms by amplitude',
         f"{N(m['first_entry_moves'])} moves, {m['participants']} participants; " + ', '.join(f"{n} {N(B[n]['prev_fix_ms_median'])}" for n in bn) + f"; per-participant major − minor {md['median_ms']:+.0f} ms, negative in {md['negative']}/{md['n_participants']}"),
        ('K5', 'Landing precision by amplitude, and prior intake vs offset',
         ', '.join(f"{n} {B[n]['offset_px_median']} px ({F(B[n]['offset_norm_median'], 2)} of band height)" for n in bn) + f"; Spearman(prior 1 s intake, offset) major 300–600 {B['major 300-600']['rho_intake_offset']:+.3f} (p {B['major 300-600']['rho_p']:.3f}), > 600 {B['major >600']['rho_intake_offset']:+.3f} (p {B['major >600']['rho_p']:.2f})"),
        ('K6', 'Target selection: landed result = nearest to the preceding fixation / top intake (1 s) / closest to any fixation (1 s), ≥ 3 candidates',
         '; '.join(f"{n} {F(B[n]['P_nearest_prev'])} / {F(B[n]['P_top_intake_1s'])} / {F(B[n]['P_top_prox_1s'])} (chance {F(B[n]['chance'], 2)}, n {N(B[n]['n_selection'])})" for n in bn) + '; major ≥ 300 px by window: ' + ', '.join(f"{w} ms {F(v['top_intake'])} / {F(v['top_prox'])}" for w, v in m['major_windows'].items())),
        ('K7', 'After the first fixation on position p, the next fixation (`next_action_by_position.py` A)',
         f"read on: position 1 {P(A['1']['read on'])}, 2 {P(A['2']['read on'])}, 10 {P(A['10']['read on'])}; immediate move back, positions 2–10: {P(min(A[str(p)]['back'] for p in range(2, 11)))}–{P(max(A[str(p)]['back'] for p in range(2, 11)))}"),
        ('K8', 'Where the first visit to p ends (B): positions 2–10 ranges, and position 1',
         f"back {rng('back')} (lands on a seen result {rng('P_back_to_seen')}), forward 1 {rng('forward 1')}, forward 2+ {rng('forward 2+')}; position 1 (n = {N(Bv['1']['n'])}): forward 1 {P(Bv['1']['forward 1'])}, forward 2+ {P(Bv['1']['forward 2+'])}, page top {P(Bv['1']['off results'])}, median visit {N(Bv['1']['fix_per_visit_median'])} fixations / {N(Bv['1']['ms_per_visit_median'])} ms vs {N(Bv['2']['fix_per_visit_median'])} / {N(Bv['2']['ms_per_visit_median'])} at position 2; P(clicked) position 1 {F(Bv['1']['P_clicked'], 2)}, 2 {F(Bv['2']['P_clicked'], 2)}, 10 {F(Bv['10']['P_clicked'], 2)}"),
        ('K9', 'What a back excursion resolves to (D), position 2 vs 10',
         f"returns to p {P(D['2']['returns to p'])} vs {P(D['10']['returns to p'])}; new result p+1 {P(D['2']['new: p+1'])} vs {P(D['10']['new: p+1'])}; new result above p {P(D['2']['new: above p'])} vs {P(D['10']['new: above p'])}; trial ends {P(D['2']['trial ends'])} vs {P(D['10']['trial ends'])} (n = {N(D['2']['n'])} / {N(D['10']['n'])})"),
        ('K10', 'The survey vs the ad block (`survey_above_fold.py`; ad = native_ad + dd_top; survey = first 5 fixations)',
         f"{N(sv['trials'])} trials, ad-topped {N(at['n'])} (block height median {N(at['ad_block_h_median'])} px); survey fixations on ad-topped pages: page top {P(comp['page top']['fix_share'])}, ad {P(comp['ad']['fix_share'])} (area share {P(comp['ad']['area_share'])}, ratio {F(comp['ad']['ratio'], 2)}), widget {P(comp['widget']['fix_share'])}, organic {P(comp['organic']['fix_share'])} (ratio {F(comp['organic']['ratio'], 2)}); first band fixated is the ad {P(at['P_first_band_is_ad'])}, skip over to an organic {P(at['P_skip_to_organic'])}; ad fixations in the survey mean {F(at['ad_fix_in_survey_mean'], 1)} of 5; block fixated ever {P(at['P_ad_ever'], 1)}, of which in the survey {P(at['P_in_survey_given_ever'])}; share of ad dwell in the survey {P(at['ad_dwell_share_in_survey_median'])}; return to the block after the survey {P(at['P_return_to_ad_after_survey_given_ever'])}; per participant median {F(ppr['median'], 2)}, IQR [{F(ppr['q25'], 2)}, {F(ppr['q75'], 2)}], min {F(ppr['min'], 2)} (n = {ppr['n']})" + (f"; surveys reaching below the fold {P(sv['survey_reach_fold_share'], 1)}" if 'survey_reach_fold_share' in sv else '')),
        ('K11', 'Survey on pages not topped by an ad, and the first fixation of the trial',
         f"not ad-topped (n = {N(sv['trials'] - at['n'])}): page top {P(oth['page top']['fix_share'])}, widget {P(oth['widget']['fix_share'])} (ratio {F(oth['widget']['ratio'], 2)}), organic {P(oth['organic']['fix_share'])} (ratio {F(oth['organic']['ratio'], 2)}); first fixation of the trial: page top {P(ff.get('page top', 0))}, ad {P(ff.get('ad', 0))}, organic {P(ff.get('organic', 0))}, widget {P(ff.get('widget', 0))}"),
    ]


def render(rows, header=True) -> str:
    out = ['| ID | Claim | Value |', '|---|---|---|'] if header else []
    for k, claim, val in rows:
        out.append(f'| **{k}** | {claim} | {val} |')
    return '\n'.join(out)


if __name__ == '__main__':
    import sys
    which = sys.argv[1] if len(sys.argv) > 1 else '37'
    files = FILES_37 if which == '37' else FILES_38
    print(render(rows_37(load(files)) if which == '37' else rows_38(load(files))))
