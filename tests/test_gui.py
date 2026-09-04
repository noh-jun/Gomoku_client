import unittest

from omok_client.board import BoardGeometry
from omok_client.board_renderer import OthelloBoardGeometry


class BoardGeometryTests(unittest.TestCase):
    def assert_round_trip(self, board_size: int, coordinate: tuple[int, int]) -> None:
        geometry = BoardGeometry.calculate(board_size, 800, 720)
        pixel = geometry.board_to_pixel(*coordinate)
        self.assertEqual(geometry.pixel_to_board(*pixel), coordinate)

    def test_15_board_round_trips(self) -> None:
        for coordinate in ((0, 0), (7, 7), (14, 14)):
            with self.subTest(coordinate=coordinate):
                self.assert_round_trip(15, coordinate)

    def test_19_board_round_trips(self) -> None:
        for coordinate in ((0, 0), (9, 9), (18, 18), (17, 18)):
            with self.subTest(coordinate=coordinate):
                self.assert_round_trip(19, coordinate)

    def test_board_is_square_and_centered_in_rectangular_canvas(self) -> None:
        geometry = BoardGeometry.calculate(19, 900, 700)
        self.assertAlmostEqual(geometry.end_x - geometry.origin_x, geometry.end_y - geometry.origin_y)
        self.assertAlmostEqual((geometry.origin_x + geometry.end_x) / 2, 450)
        self.assertAlmostEqual((geometry.origin_y + geometry.end_y) / 2, 350)

    def test_spacing_and_stones_scale_with_board_size(self) -> None:
        board_15 = BoardGeometry.calculate(15, 800, 800)
        board_19 = BoardGeometry.calculate(19, 800, 800)
        self.assertGreater(board_15.spacing, board_19.spacing)
        self.assertGreater(board_15.stone_radius, board_19.stone_radius)
        self.assertAlmostEqual(board_15.stone_radius / board_15.spacing, 0.42)
        self.assertAlmostEqual(board_19.stone_radius / board_19.spacing, 0.42)

    def test_rejects_click_too_far_from_intersection(self) -> None:
        geometry = BoardGeometry.calculate(15, 800, 800)
        x, y = geometry.board_to_pixel(7, 7)
        self.assertIsNone(
            geometry.pixel_to_board(x + geometry.spacing * 0.49, y + geometry.spacing * 0.49)
        )

    def test_othello_uses_cell_centers_and_cell_hit_testing(self) -> None:
        geometry = OthelloBoardGeometry.calculate(8, 800, 700)
        first_x, first_y = geometry.board_to_pixel(0, 0)
        last_x, last_y = geometry.board_to_pixel(7, 7)
        self.assertEqual(geometry.pixel_to_board(first_x, first_y), (0, 0))
        self.assertEqual(geometry.pixel_to_board(last_x, last_y), (7, 7))
        self.assertAlmostEqual(first_x - geometry.origin_x, geometry.spacing / 2)
        self.assertIsNone(
            geometry.pixel_to_board(geometry.end_x + 0.01, geometry.end_y - 1)
        )


if __name__ == "__main__":
    unittest.main()
