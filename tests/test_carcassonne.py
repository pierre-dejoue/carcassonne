from carcassonne import PlacedTile
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


if __name__ == '__main__':
    unittest.main()
