import unittest

import ui_check

JOIST = {"id": "joist@a", "system": "joists", "material": "spf", "x_mm": 100, "y_mm": 200, "width_mm": 1000, "depth_mm": 40, "elevation_mm": 50, "fields": {"height_mm": 140}}
JOIST_BOX = {"id": "joist@a", "style": "spf", "x_mm": 600, "y_mm": 220, "z_mm": 50, "width_mm": 1000, "depth_mm": 40, "height_mm": 140}
VOLUME = {"boxes": [JOIST_BOX], "details": {"joist@a": {"sections": [{"rows": [{"label": "system", "value": "joists"}]}]}}}


class PieceDifferenceTest(unittest.TestCase):
    def test_a_box_placed_as_the_engine_says_has_no_difference(self):
        self.assertEqual([], ui_check.piece_difference(JOIST, VOLUME, []))

    def test_a_missing_box_is_named(self):
        self.assertEqual(["no box in the spec"], ui_check.piece_difference(JOIST, {"boxes": [], "details": {}}, []))

    def test_a_box_moved_one_centimetre_is_named(self):
        moved = {**VOLUME, "boxes": [{**JOIST_BOX, "x_mm": 610}]}
        self.assertEqual(["x 600 against 610"], ui_check.piece_difference(JOIST, moved, []))

    def test_a_wrong_system_is_named(self):
        wrong = {**VOLUME, "details": {"joist@a": {"sections": [{"rows": [{"label": "system", "value": "walls"}]}]}}}
        self.assertEqual(["system joists against walls"], ui_check.piece_difference(JOIST, wrong, []))


class DrawnGapsTest(unittest.TestCase):
    def test_a_box_drawn_but_not_in_the_spec_is_named(self):
        self.assertEqual(["drawn but not in the spec: b"], ui_check.drawn_gaps({"a"}, {"a": (5, 5), "b": (5, 5)}))

    def test_a_box_in_the_spec_but_not_drawn_is_named(self):
        self.assertEqual(["in the spec but not drawn: b"], ui_check.drawn_gaps({"a", "b"}, {"a": (5, 5)}))

    def test_a_box_with_no_area_is_named(self):
        self.assertEqual(["a has no area on screen"], ui_check.blank_gaps({"a": (0, 9)}))


class PlantTest(unittest.TestCase):
    def test_dropping_the_loft_joist_removes_one_box(self):
        spec = {"root": {"id": "root", "type": "stack", "children": [{"id": "volume", "type": "volume", "props": {"boxes": [JOIST_BOX]}}]}}
        ui_check.drop_loft_joist(spec)
        self.assertEqual([], ui_check.find_volume(spec)["boxes"])


if __name__ == "__main__":
    unittest.main()
