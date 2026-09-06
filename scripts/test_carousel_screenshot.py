"""Independent pixel fixtures for conservative carousel registration.

Images are generated without consulting the detector.  Card coordinates and
translation expectations are the oracle; these tests do not read private data.
"""
import copy
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import carousel_screenshot as subject


STROKE = (218, 220, 224)


def box(x, y=140, w=110, h=180):
    return dict(x=x, y=y, w=w, h=h)


def image_with_cards(boxes, color=STROKE, size=(840, 600)):
    image = Image.new('RGB', size, 'white')
    draw = ImageDraw.Draw(image)
    for b in boxes:
        draw.rounded_rectangle(
            (b['x'], b['y'], b['x'] + b['w'] - 1, b['y'] + b['h'] - 1),
            radius=8, outline=color, width=1,
        )
    return image


def mask_of(image):
    return np.all(np.asarray(image) == STROKE, axis=2)


def parent_of(boxes):
    left = min(b['x'] for b in boxes)
    right = max(b['x'] + b['w'] for b in boxes)
    top = min(b['y'] for b in boxes)
    bottom = max(b['y'] + b['h'] for b in boxes)
    return {
        'issues': [],
        'rendered_visible_rect_screenshot': box(left, top - 35, right - left, bottom - top + 35),
        'cells': [
            {'card_id': f'vplaurlg{i}', 'visible_fraction': 1,
             'raw_rect_screenshot': dict(b), 'visible_rect_screenshot': dict(b)}
            for i, b in enumerate(boxes)
        ],
    }


def register(parent, image):
    mask = mask_of(image)
    return subject.register_parent(parent, mask, subject.detect_outlines(mask))


class ScreenshotRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.cards = [box(x) for x in (20, 160, 300, 440, 580)]

    def assert_rejected(self, result, reason=None):
        self.assertEqual(result['status'], 'rejected', result)
        if reason:
            self.assertEqual(result['reason'], reason, result)

    def test_detects_independent_outline_geometry(self):
        outlines = subject.detect_outlines(mask_of(image_with_cards(self.cards)))
        self.assertEqual([{k: o[k] for k in 'xywh'} for o in outlines], self.cards)

    def test_corrects_minus_39_and_preserves_raw_geometry(self):
        measured = [dict(b, y=b['y'] + 39) for b in self.cards]
        parent = parent_of(measured)
        before = copy.deepcopy(parent)
        result = register(parent, image_with_cards(self.cards))
        self.assertEqual(result['status'], 'accepted', result)
        self.assertEqual(result['dy'], -39)
        for cell, old, expected in zip(parent['cells'], before['cells'], self.cards):
            self.assertEqual(cell['raw_rect_screenshot'], old['raw_rect_screenshot'])
            self.assertEqual(cell['visible_rect_screenshot'], old['visible_rect_screenshot'])
            self.assertEqual(cell['aligned_visible_rect_screenshot'], expected)

    def test_corrects_plus_39(self):
        measured = [dict(b, y=b['y'] - 39) for b in self.cards]
        result = register(parent_of(measured), image_with_cards(self.cards))
        self.assertEqual(result['status'], 'accepted', result)
        self.assertEqual(result['dy'], 39)

    def test_rejects_vertical_shift_outside_protocol(self):
        measured = [dict(b, y=b['y'] + 81) for b in self.cards]
        self.assert_rejected(register(parent_of(measured), image_with_cards(self.cards)),
                             'insufficient_outline_anchors')

    def test_rejects_inconsistent_per_card_shifts(self):
        measured = [dict(b, y=b['y'] + (39 if i < 4 else 46))
                    for i, b in enumerate(self.cards)]
        self.assert_rejected(register(parent_of(measured), image_with_cards(self.cards)),
                             'inconsistent_card_offsets')

    def test_rejects_ambiguous_duplicate_outlines(self):
        # Two fully supported 65px-high candidates are both within +/-80px.
        cards = [box(x, y=50, h=65) for x in (20, 160, 300)]
        duplicate_row = [dict(b, y=140) for b in cards]
        measured = [dict(b, y=95) for b in cards]
        self.assert_rejected(register(parent_of(measured), image_with_cards(cards + duplicate_row)),
                             'ambiguous_outline_match')

    def test_two_dom_cards_cannot_claim_one_outline(self):
        cards = [box(20), box(20), box(300)]
        self.assert_rejected(register(parent_of(cards), image_with_cards([box(20), box(300)])),
                             'ambiguous_outline_match')

    def test_blank_and_unknown_border_style_fail_closed(self):
        for color in ('white', (70, 70, 70)):
            with self.subTest(color=color):
                image = image_with_cards(self.cards, color=color)
                self.assert_rejected(register(parent_of(self.cards), image),
                                     'insufficient_outline_anchors')

    def test_missing_last_card_bottom_is_not_rescued_by_other_anchors(self):
        image = image_with_cards(self.cards)
        b = self.cards[-1]
        ImageDraw.Draw(image).rectangle(
            (b['x'], b['y'] + b['h'] - 3, b['x'] + b['w'], b['y'] + b['h']),
            fill='white',
        )
        self.assert_rejected(register(parent_of(self.cards), image),
                             'visible_card_border_mismatch')

    def test_wrong_last_card_height_is_not_rescued_by_other_anchors(self):
        rendered = [dict(b, h=b['h'] + (12 if i == 4 else 0))
                    for i, b in enumerate(self.cards)]
        self.assert_rejected(register(parent_of(self.cards), image_with_cards(rendered)),
                             'visible_card_border_mismatch')

    def test_moving_last_card_while_other_three_anchor_fails(self):
        rendered = [dict(b, y=b['y'] + (20 if i == 4 else 0),
                         w=b['w'] + (8 if i == 4 else 0))
                    for i, b in enumerate(self.cards)]
        self.assert_rejected(register(parent_of(self.cards), image_with_cards(rendered)),
                             'visible_card_border_mismatch')

    def test_requires_sixty_percent_closed_anchors(self):
        image = image_with_cards(self.cards)
        # Top/bottom plus the left edge remain intact on all cards, but only
        # two have the second vertical edge needed to serve as anchors.
        draw = ImageDraw.Draw(image)
        for b in self.cards[2:]:
            draw.rectangle((b['x'] + b['w'] - 3, b['y'] + 12,
                            b['x'] + b['w'], b['y'] + b['h'] - 12), fill='white')
        self.assert_rejected(register(parent_of(self.cards), image),
                             'insufficient_outline_anchors')

    def test_one_vertical_edge_occlusion_is_allowed_with_enough_anchors(self):
        image = image_with_cards(self.cards)
        b = self.cards[-1]
        ImageDraw.Draw(image).rectangle(
            (b['x'] + b['w'] - 3, b['y'] + 12, b['x'] + b['w'], b['y'] + b['h'] - 12),
            fill='white',
        )
        result = register(parent_of(self.cards), image)
        self.assertEqual(result['status'], 'accepted', result)
        self.assertEqual(len(result['anchors']), 4)

    def test_partial_too_narrow_card_fails_closed(self):
        cards = [*self.cards[:4], box(580, w=25)]
        parent = parent_of(cards)
        parent['cells'][-1]['visible_fraction'] = 25 / 110
        self.assert_rejected(register(parent, image_with_cards(cards)),
                             'visible_card_border_mismatch')

    def test_partial_at_image_boundary_fails_closed(self):
        cards = [box(0), *self.cards[1:]]
        parent = parent_of(cards)
        parent['cells'][0]['visible_fraction'] = .9
        self.assert_rejected(register(parent, image_with_cards(cards)),
                             'visible_card_border_mismatch')

    def test_unresolved_parent_or_single_card_cannot_register(self):
        parent = parent_of(self.cards)
        parent['issues'] = ['duplicate_card_identity']
        self.assert_rejected(register(parent, image_with_cards(self.cards)),
                             'unresolved_parent_or_too_few_cards')
        self.assert_rejected(register(parent_of(self.cards[:1]), image_with_cards(self.cards)),
                             'unresolved_parent_or_too_few_cards')

    def test_extra_interior_outline_is_rejected(self):
        observed = [box(x) for x in (20, 300, 580)]
        screenshot = image_with_cards(observed + [box(160)])
        self.assert_rejected(register(parent_of(observed), screenshot),
                             'unmatched_screenshot_outline')

    def test_extra_trailing_outline_inside_parent_is_rejected(self):
        parent = parent_of(self.cards)
        parent['cells'].pop()
        self.assert_rejected(register(parent, image_with_cards(self.cards)),
                             'unmatched_screenshot_outline')

    def test_extra_leading_outline_inside_parent_is_rejected(self):
        parent = parent_of(self.cards)
        parent['cells'].pop(0)
        self.assert_rejected(register(parent, image_with_cards(self.cards)),
                             'unmatched_screenshot_outline')

    def test_extra_open_sided_trailing_outline_is_rejected(self):
        parent = parent_of(self.cards)
        parent['cells'].pop()
        image = image_with_cards(self.cards)
        b = self.cards[-1]
        ImageDraw.Draw(image).rectangle(
            (b['x'] + b['w'] - 3, b['y'] + 12, b['x'] + b['w'], b['y'] + b['h'] - 12),
            fill='white',
        )
        self.assert_rejected(register(parent, image), 'unmatched_screenshot_outline')

    def test_extra_actually_clipped_trailing_outline_is_rejected(self):
        parent = parent_of(self.cards)
        parent['cells'].pop()
        right = self.cards[-1]['x'] + 70
        parent['rendered_visible_rect_screenshot']['w'] = right - self.cards[0]['x']
        image = image_with_cards(self.cards)
        ImageDraw.Draw(image).rectangle((right, 0, image.width, image.height), fill='white')
        self.assert_rejected(register(parent, image), 'unmatched_screenshot_outline')

    def test_extra_actually_clipped_leading_outline_is_rejected(self):
        parent = parent_of(self.cards)
        parent['cells'].pop(0)
        left = self.cards[0]['x'] + 40
        extent = parent['rendered_visible_rect_screenshot']
        extent['w'] -= left - extent['x']
        extent['x'] = left
        image = image_with_cards(self.cards)
        ImageDraw.Draw(image).rectangle((0, 0, left - 1, image.height), fill='white')
        self.assert_rejected(register(parent, image), 'unmatched_screenshot_outline')

    def test_absent_parent_extent_fails_closed(self):
        parent = parent_of(self.cards)
        del parent['rendered_visible_rect_screenshot']
        self.assert_rejected(register(parent, image_with_cards(self.cards)),
                             'missing_parent_clip_extent')

    def test_rejected_repeat_clears_previous_alignment(self):
        parent = parent_of(self.cards)
        self.assertEqual(register(parent, image_with_cards(self.cards))['status'], 'accepted')
        self.assert_rejected(register(parent, image_with_cards([], color='white')))
        self.assertTrue(all('aligned_visible_rect_screenshot' not in c for c in parent['cells']))

    def test_now_hidden_card_loses_previous_alignment(self):
        parent = parent_of(self.cards)
        self.assertEqual(register(parent, image_with_cards(self.cards))['status'], 'accepted')
        parent['cells'][-1]['visible_rect_screenshot'] = None
        register(parent, image_with_cards(self.cards))
        self.assertNotIn('aligned_visible_rect_screenshot', parent['cells'][-1])

    def test_trial_status_guard_clears_previous_acceptance_and_alignment(self):
        parent = parent_of(self.cards)
        row = {'status': 'scored', 'parents': [parent]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'fixture.png'
            image_with_cards(self.cards).save(path)
            self.assertEqual(subject.register_trial(row, path)['registration_status'], 'accepted')
            row['status'] = 'unresolved'
            self.assertEqual(subject.register_trial(row, path)['registration_status'], 'rejected')
        self.assertTrue(all('aligned_visible_rect_screenshot' not in c for c in parent['cells']))
        self.assertNotEqual(parent.get('screenshot_registration', {}).get('status'), 'accepted')


if __name__ == '__main__':
    unittest.main()
