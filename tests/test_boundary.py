import boundary
import functools
import unittest
from boundary import Boundary
from boundary import Domain
from boundary import Orientation
from boundary import Vect
from collections import defaultdict


class TestVect(unittest.TestCase):
    def test_operations(self):
        self.assertTrue(Vect(1, 0) == Vect(1, 0))
        self.assertFalse(Vect(1, 0) == Vect(1, 1))
        self.assertEqual(Vect(1, 0) + Vect(0, 1), Vect(1, 1))
        self.assertEqual(Vect(1, 2) - Vect(1, 2), Vect(0, 0))
        self.assertEqual(Vect(1, 2).mult(2), Vect(2, 4))
        self.assertEqual(Vect(1, 0).cross_z(Vect(0, 1)), 1)
        self.assertEqual(Vect(0, 1).cross_z(Vect(1, 0)), -1)


def make_border_from_tiles(tiles_args):
    return functools.reduce(lambda border, args: border.merge(boundary.get_tile(*args)), tiles_args, Boundary())


class TestBoundary(unittest.TestCase):
    def setUp(self):
        self.border = Boundary()
        self.border.append(Vect(0, 0), 'F')
        self.border.append(Vect(1, 0), 'F')
        self.border.append(Vect(2, 0), 'T')
        self.border.append(Vect(2, 1), 'P')
        self.border.append(Vect(1, 1), 'F')
        self.border.append(Vect(0, 1), 'P')


    def test_self(self):
        self.assertEqual(len(self.border), 6)
        self.assertEqual(self.border.orientation(), Orientation.COUNTERCLOCKWISE)
        self.assertEqual(self.border.get_point(2), Vect(2, 0))
        self.assertEqual(self.border.get_point(8), self.border.get_point(2))
        self.assertEqual(self.border.get_point(-4), self.border.get_point(2))
        self.assertEqual(self.border.get_label(2), 'T')
        self.assertEqual(self.border.get_label(8), self.border.get_label(2))
        self.assertEqual(self.border.get_label(-4), self.border.get_label(2))
        self.assertEqual(self.border.get_edge(0), Vect(1, 0))
        self.assertEqual(self.border.get_edge(-1), Vect(0, -1))
        self.assertEqual(self.border.bottom_left(), Vect(0, 0))


    def test_common_segments_1(self):
        tile1 = boundary.get_tile(2, 1, 'FFFF')
        self.assertEqual(self.border.common_segments(tile1), [(3, 0, 0)])
        tile2 = boundary.get_tile(1, 1, 'FFFF')
        self.assertEqual(self.border.common_segments(tile2), [(3, 0, 1)])
        self.assertEqual(tile1.common_segments(tile2), [(3, 1, 1)])
        self.assertEqual(tile2.common_segments(tile1), [(1, 3, 1)])
        tile3 = Boundary()
        tile3.append(Vect(2, 2), 'F')
        tile3.append(Vect(1, 2), 'F')
        tile3.append(Vect(1, 1), 'F')
        tile3.append(Vect(2, 1), 'F')
        self.assertEqual(tile1.common_segments(tile3), [(3, 3, 1)])
        self.assertEqual(tile3.common_segments(tile1), [(3, 3, 1)])


    def test_common_segments_2(self):
        tiles_args = [ (0, 0), (1, 0), (1, 1), (0, 1) ]
        for single_idx in range(4):
            single_tile = boundary.get_tile(*tiles_args[single_idx])
            three_other_tiles = tiles_args[single_idx+1:] + tiles_args[:single_idx]
            border = make_border_from_tiles(three_other_tiles)
            self.assertEqual(len(border), 8)
            border.rotate_to_start_with(Vect(1, 1))
            for ii in range(len(border)):
                segments = border.common_segments(single_tile)
                self.assertEqual(len(segments), 1)
                (i, j, L) = segments[0]
                self.assertEqual(L, 2)
                self.assertEqual(j, (single_idx + 1) % 4)
                self.assertEqual(i, 7 - ii)
                border.rotate_to_start_with(border.points[1])


    def test_merge(self):
        border = Boundary()

        border.merge(boundary.get_tile(0, 0, 'FFFF'))
        self.assertEqual(len(border), 4)
        self.assertEqual(border.labels, list('FFFF'))

        border.merge(boundary.get_tile(1, 0, 'FFFF'))
        self.assertEqual(len(border), 6)
        self.assertEqual(border.labels, list('FFFFFF'))


    def test_corner_case_1(self):
        tiles_args = [
            (1, 0, 'FFFF'),
            (2, 0, 'FFFF'),
            (2, 1, 'FFFF'),
            (2, 2, 'FFFF'),
            (1, 2, 'FFFF'),
            (0, 2, 'FFFF')]
        border = make_border_from_tiles(tiles_args)
        self.assertEqual(len(border), 14)
        tile = boundary.get_tile(0, 1, 'FFFF')
        segments = border.common_segments(tile)
        self.assertEqual(len(segments), 2)


    def test_corner_case_2(self):
        tiles_args = [
            (2, 0, 'FFFF'),
            (2, 1, 'FFFF'),
            (2, 2, 'FFFF'),
            (1, 2, 'FFFF'),
            (0, 2, 'FFFF'),
            (0, 1, 'FFFF'),
            (0, 0, 'FFFF')]
        border = make_border_from_tiles(tiles_args)
        self.assertEqual(len(border), 16)
        tile = boundary.get_tile(1, 0, 'FFFF')
        segments = border.common_segments(tile)
        self.assertEqual(len(segments), 2)


    def test_rotate_to_start_with(self):
        border = self.border.copy()

        border.rotate_to_start_with(Vect(2, 0))
        self.assertEqual(len(border), len(self.border))
        self.assertEqual(border.points[0], Vect(2, 0))
        self.assertEqual(border.labels, list('TPFPFF'))

        border.rotate_to_start_with(Vect(2, 1))
        self.assertEqual(len(border), len(self.border))
        self.assertEqual(border.points[0], Vect(2, 1))
        self.assertEqual(border.labels, list('PFPFFT'))

        with self.assertRaises(ValueError):
            border.rotate_to_start_with(Vect(99, 99))


    def test_find_matching_rotations(self):
        tiles_args = [
            (0, 0, 'FFFF'),
            (0, 1, 'FFFF'),
            (1, 1, 'TFFF')]
        border = make_border_from_tiles(tiles_args)
        border.rotate_to_start_with(Vect(0, 0))
        self.assertEqual(len(border), 8)
        self.assertEqual(border.labels, list('FFTFFFFF'))
        tile = boundary.get_tile(1, 0, 'TFFF')
        self.assertEqual(border.common_segments(tile), [(1, 2, 2)])
        self.assertEqual(list(border.find_matching_rotations(tile, (1, 2, 2))), [2])


    def tearDown(self):
        pass


class TestFromEdge(unittest.TestCase):
    def test_from_edge(self):
        bottom_lefts = defaultdict(int)
        for orientation in [Orientation.CLOCKWISE, Orientation.COUNTERCLOCKWISE]:
            for domain in [Domain.INTERIOR, Domain.EXTERIOR]:
                border = boundary.from_edge(Vect(3, 5), Vect(1, 0), orientation, domain)
                self.assertEqual(len(border),4)
                self.assertEqual(border.orientation(), orientation)
                bottom_lefts[border.bottom_left()] += 1
        self.assertEqual(bottom_lefts, { Vect(3, 5): 2, Vect(3, 4): 2 })


class TestGetTile(unittest.TestCase):
    def test_get_tile(self):
        tile = boundary.get_tile(5, 7, 'FFFF')
        self.assertEqual(len(tile), 4)
        self.assertEqual(tile.orientation(), Orientation.COUNTERCLOCKWISE)
        self.assertEqual(tile.points[0], Vect(5, 7))
        self.assertEqual(tile.get_edge(0), Vect(1, 0))
        self.assertEqual(tile.get_edge(1), Vect(0, 1))
        self.assertEqual(tile.get_edge(2), Vect(-1, 0))
        self.assertEqual(tile.get_edge(3), Vect(0, -1))
        self.assertEqual(tile.bottom_left(), Vect(5, 7))


if __name__ == '__main__':
    unittest.main()
