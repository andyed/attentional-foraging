"""Fixture tests for audit_carousel_paging: the audit must be able to see paging.

Run: PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest scripts.test_audit_carousel_paging -v
"""
import sys
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent))
from audit_carousel_paging import classify, resolve  # noqa: E402

CARDS = ''.join(
    f'<div class="mnr-c pla-unit"><a id="vplaurlg{n}"><img id="img{n}"></a>'
    f'<a id="vplaurlt{n}"><span>card {n}</span></a></div>' for n in range(7))
PAGE = f'''<html><body>
<div id="tads"><div class="commercial-unit-desktop-top"><g-scrolling-carousel id="car1">
<div>{CARDS}</div><div></div><div><g-right-button><g-fab><span>next</span></g-fab></g-right-button></div>
</g-scrolling-carousel></div></div>
<div id="rhs"><div class="commercial-unit-desktop-rhs"><div class="pla-unit"><a id="vplaurlg90"></a><a id="vplaurlt90"><span>r</span></a></div></div></div>
<div id="rso"><div><a><h3>organic</h3></a></div></div>
</body></html>'''
# Five visible at load, card 5 partially clipped, card 6 in the hidden tail.
REPORT = {f'vplaurlg{n}': {'dom_order': n, 'visible_fraction': 1 if n < 5 else (0.4 if n == 5 else 0)}
          for n in range(7)}


def soup():
    return BeautifulSoup(PAGE, 'html.parser')


class AuditCarouselPagingTest(unittest.TestCase):
    def test_hidden_card_click_is_flagged(self):
        # The case the coordinate-based 2026-08-30 check could never produce.
        el = resolve(soup(), "//*[@id='vplaurlt6']/span")
        out = classify(el, REPORT)
        assert out['kind'] == 'top_card' and out['dom_order'] == 6
        assert out['visibility'] == 'hidden_at_load'


    def test_visible_and_partial_cards(self):
        s = soup()
        assert classify(resolve(s, "//*[@id='vplaurlt0']/span"), REPORT)['visibility'] == 'visible_at_load'
        assert classify(resolve(s, "//*[@id='vplaurlt5']/span"), REPORT)['visibility'] == 'partial_at_load'


    def test_image_click_resolves_to_its_card(self):
        out = classify(resolve(soup(), "//*[@id='img3']"), REPORT)
        assert out['card_id'] == 'vplaurlg3'


    def test_next_button_is_a_paging_control_on_the_top_unit(self):
        out = classify(resolve(soup(), "//*[@id='car1']/div[3]/g-right-button/g-fab/span"), REPORT)
        assert out == {'kind': 'paging_control', 'direction': 'right', 'in_top_ads_unit': True,
                       'product_cards_in_carousel': 7}


    def test_right_rail_card_is_out_of_scope(self):
        assert classify(resolve(soup(), "//*[@id='vplaurlt90']/span"), REPORT)['kind'] == 'rhs_card'


    def test_organic_click_is_ignored_and_bad_steps_do_not_resolve(self):
        s = soup()
        assert classify(resolve(s, "//*[@id='rso']/div/a/h3"), REPORT) is None
        assert resolve(s, "//*[@id='rso']/div[4]/a") is None


if __name__ == "__main__":
    unittest.main()
