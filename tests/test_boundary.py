from boundary import Boundary
from boundary import Domain
from boundary import Orientation
from boundary import Vect
import boundary
import unittest


class TestVect(unittest.TestCase):
    def setUp(self):
        pass


    def test_basic_operations(self):
        self.assertTrue(Vect(1, 0) == Vect(1, 0))
        self.assertFalse(Vect(1, 0) == Vect(1, 1))
        self.assertEqual(Vect(1, 0) + Vect(0, 1), Vect(1, 1))
        self.assertEqual(Vect(1, 2) - Vect(1, 2), Vect(0, 0))
        self.assertEqual(Vect(1, 2).mult(2), Vect(2, 4))
        self.assertEqual(Vect(1, 0).cross(Vect(0, 1)), 1)


    def tearDown(self):
        pass


class TestBoundary(unittest.TestCase):
    def setUp(self):
        self.border = Boundary()
        self.border.append(Vect(0, 0), 'F')
        self.border.append(Vect(1, 0), 'F')
        self.border.append(Vect(2, 0), 'T')
        self.border.append(Vect(2, 1), 'P')
        self.border.append(Vect(1, 1), 'F')
        self.border.append(Vect(0, 1), 'P')
        #print(self.border)
        self.tile = boundary.get_tile(5, 7, 'FFFF')


    def test_boundary_obj(self):
        self.assertEqual(len(self.border), 6)
        self.assertEqual(self.border.get_edge(0), Vect(1, 0))
        self.assertEqual(self.border.get_edge(-1), Vect(0, -1))
        self.assertEqual(self.border.bottomleft(), (0, 0))


    def test_orientation(self):
        self.assertEqual(self.border.orientation(), Orientation.COUNTERCLOCKWISE)
        self.assertEqual(self.tile.orientation(), Orientation.COUNTERCLOCKWISE)


    def test_boundary_get_tile(self):
        self.assertEqual(len(self.tile), 4)
        self.assertEqual(self.tile.get_edge(0), Vect(1, 0))
        self.assertEqual(self.tile.bottomleft(), (5, 7))


    def test_boundary_from_edge(self):
        for orientation in [Orientation.CLOCKWISE, Orientation.COUNTERCLOCKWISE]:
            for domain in [Domain.INTERIOR, Domain.EXTERIOR]:
                border = boundary.from_edge(Vect(3, 5), Vect(1, 0), orientation, domain)
                self.assertEqual(len(border),4)
                self.assertEqual(border.orientation(), orientation)


    def test_common_segments(self):
        tile1 = boundary.get_tile(2, 1, 'FFFF')
        self.assertEqual(self.border.common_segments(tile1), [(3, 0, 0)])
        tile2 = boundary.get_tile(1, 1, 'FFFF')
        self.assertEqual(self.border.common_segments(tile2), [(3, 0, 1)])
        self.assertEqual(tile1.common_segments(tile2), [(3, 1, 1)])
        self.assertEqual(tile2.common_segments(tile1), [(1, 3, 1)])
        tile3 = Boundary()
        tile3.append(Vect(2,2), 'F')
        tile3.append(Vect(1,2), 'F')
        tile3.append(Vect(1,1), 'F')
        tile3.append(Vect(2,1), 'F')
        self.assertEqual(tile1.common_segments(tile3), [(3, 3, 1)])
        self.assertEqual(tile3.common_segments(tile1), [(3, 3, 1)])


    def test_merge_boundaries(self):
        border = boundary.get_tile(0, 0, 'FFFF')
        border.merge(boundary.get_tile(1, 0, 'FFFF'))
        self.assertEqual(len(border), 6)


    def test_corner_case_1(self):
        border = boundary.get_tile(1, 0, 'FFFF')
        border.merge(boundary.get_tile(2, 0, 'FFFF'))
        border.merge(boundary.get_tile(2, 1, 'FFFF'))
        border.merge(boundary.get_tile(2, 2, 'FFFF'))
        border.merge(boundary.get_tile(1, 2, 'FFFF'))
        border.merge(boundary.get_tile(0, 2, 'FFFF'))
        self.assertEqual(len(border), 14)
        tile = boundary.get_tile(0, 1, 'FFFF')
        segments = border.common_segments(tile)
        self.assertEqual(len(segments), 2)


    def test_corner_case_2(self):
        border = boundary.get_tile(2, 0, 'FFFF')
        border.merge(boundary.get_tile(2, 1, 'FFFF'))
        border.merge(boundary.get_tile(2, 2, 'FFFF'))
        border.merge(boundary.get_tile(1, 2, 'FFFF'))
        border.merge(boundary.get_tile(0, 2, 'FFFF'))
        border.merge(boundary.get_tile(0, 1, 'FFFF'))
        border.merge(boundary.get_tile(0, 0, 'FFFF'))
        self.assertEqual(len(border), 16)
        tile = boundary.get_tile(1, 0, 'FFFF')
        segments = border.common_segments(tile)
        self.assertEqual(len(segments), 2)


    def tearDown(self):
        pass


if __name__ == '__main__':
    unittest.main()
