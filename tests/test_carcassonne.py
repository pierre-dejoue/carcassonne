from carcassonne import CandidateTiles
from carcassonne import PlacedTile
from carcassonne import PositionedTile
from carcassonne import Tile
from boundary import Boundary
from boundary import Vect
import unittest


class TestPlacedTile(unittest.TestCase):
    def setUp(self):
        self.test_tile = Tile(desc = 'FPTP', tags = ['this_is_a_test'])


    def test_segment_labels(self):
        placed_tile = PlacedTile(self.test_tile, Vect(2, 1), r = 0, segment = (42, 1, 2))
        self.assertEqual(list(Boundary.label_getter(placed_tile.iter_segment())), list('PT'))
        self.assertEqual(list(Boundary.label_getter(placed_tile.iter_complement_segment())), list('PF'))

        placed_tile = PlacedTile(self.test_tile, Vect(2, 1), r = 1, segment = (42, 1, 2))
        self.assertEqual(list(Boundary.label_getter(placed_tile.iter_segment())), list('FP'))
        self.assertEqual(list(Boundary.label_getter(placed_tile.iter_complement_segment())), list('TP'))

        placed_tile = PlacedTile(self.test_tile, Vect(2, 1), r = 0, segment = (42, 1, 0))
        self.assertEqual(list(Boundary.label_getter(placed_tile.iter_segment())), [])
        self.assertEqual(list(Boundary.label_getter(placed_tile.iter_complement_segment())), list('PTPF'))


    def tearDown(self):
        pass


class TestCandidateTiles(unittest.TestCase):
    def setUp(self):
        self.candidates = CandidateTiles()
        self.candidates.update(PositionedTile(Vect(5, 5), segments = [(0, 0, 1), (1, 1, 1)]))
        self.candidates.update(PositionedTile(Vect(4, 4), segments = [(0, 0, 1)]))
        self.candidates.update(PositionedTile(Vect(3, 3), segments = [(0, 0, 1)]))
        self.candidates.update(PositionedTile(Vect(2, 2), segments = [(0, 0, 2)]))
        self.candidates.update(PositionedTile(Vect(1, 1), segments = [(0, 0, 2)]))
        self.candidates.update(PositionedTile(Vect(0, 0), segments = [(0, 0, 3)]))


    def do_sort(self):
        self.candidates.sort(key=PlacedTile.get_l1_distance)
        self.candidates.sort(key=PlacedTile.get_segment_length, reverse=True)


    def test_sort(self):
        self.assertEqual(len(self.candidates), 5)
        self.do_sort()
        self.assertEqual([tile.pos for tile in self.candidates.iterate()], [Vect(0, 0), Vect(1, 1), Vect(2, 2), Vect(3, 3), Vect(4, 4)])


    def test_update(self):
        self.do_sort()
        self.assertEqual(next(self.candidates.iterate()).pos, Vect(0, 0))
        self.candidates.update(PositionedTile(Vect(0, 0), segments = [(0, 0, 1)]))
        self.do_sort()
        self.assertEqual(next(self.candidates.iterate()).pos, Vect(1, 1))


    def test_delete(self):
        self.do_sort()
        self.assertEqual(len(self.candidates), 5)
        self.assertEqual(self.candidates.nb_to_be_deleted, 0)
        self.candidates.delete(Vect(1, 1))
        self.assertEqual(len(self.candidates), 4)
        self.assertEqual(self.candidates.nb_to_be_deleted, 1)
        self.assertEqual([tile.pos for tile in self.candidates.iterate()], [Vect(0, 0), Vect(2, 2), Vect(3, 3), Vect(4, 4)])


    def test_resize(self):
        self.do_sort()
        self.assertEqual(len(self.candidates), 5)
        self.assertEqual(self.candidates.nb_to_be_deleted, 0)
        self.candidates.delete(Vect(1, 1))
        self.assertEqual(len(self.candidates), 4)
        self.assertEqual(self.candidates.nb_to_be_deleted, 1)
        self.candidates.force_resize()
        self.assertEqual(len(self.candidates), 4)
        self.assertEqual(self.candidates.nb_to_be_deleted, 0)
        self.assertEqual([tile.pos for tile in self.candidates.iterate()], [Vect(0, 0), Vect(2, 2), Vect(3, 3), Vect(4, 4)])


    def tearDown(self):
        pass


if __name__ == '__main__':
    unittest.main()
