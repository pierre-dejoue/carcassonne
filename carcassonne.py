#!/usr/bin/env python
"""
This script displays a randomized Carcassonne map
"""
import argparse
import functools
import itertools
import json
import logging
import operator
import os.path
import random
import re
import secrets
import sys
import traceback
from collections import deque
from enum import Enum, auto
from typing import Any, List

import boundary
import graphics
from boundary import Boundary, Domain, Orientation, Vect

logger = logging.getLogger(__name__)


EXTRA_DEBUG_PRINTOUT = False
DEFAUT_DISPLAY_W = 1280
DEFAUT_DISPLAY_H = 720
DEFAULT_TILE_SIZE = 100
SCREENSHOT_PATH = './screenshot.jpg'
DUMP_PATH = './dump.bmp'


class RiverPlacement(Enum):
    """Flags to control the placement of the river tiles"""
    USE_T = auto()
    EXCLUDE_T = auto()
    SHORT_RIVER = auto()
    LONG_RIVER = auto()


RIVER_PLACEMENT_DEFAULT_T_POLICY = RiverPlacement.USE_T
RIVER_PLACEMENT_DEFAULT_LENGTH_POLICY = RiverPlacement.SHORT_RIVER


def override(f):
    # Eye-candy decorator
    return f


def handle_assertion_error():
    _, _, tb = sys.exc_info()
    tb_info = traceback.extract_tb(tb)
    filename, line, _, text = tb_info[-1]
    logger.error('An error occurred in file %s line %d in statement "%s"', filename, line, text)


class Tile:
    """
    A tile (usually a game tile) defined by the description of its four sides (desc),
    its cardinality (max_nb) and optionally a graphical representation (img)
    """

    def __init__(self, desc = None, max_nb = 1, img_path = '', tags = None):
        self.desc = desc if desc is not None else [None, None, None, None]
        self.max_nb = max_nb
        self.img_path = img_path
        self.img = None
        self.tags = tags if tags is not None else []


    def __repr__(self):
        return f'Tile({self.desc})'


    @classmethod
    def from_json_description(cls, json_obj, basedir):
        assert 'description' in json_obj.keys()
        desc = json_obj['description']
        max_nb = json_obj['cardinality'] if 'cardinality' in json_obj.keys() else 1
        img_path = os.path.join(basedir, json_obj['img']) if 'img' in json_obj.keys() and json_obj['img'] else ''
        tags = []
        for id in range(10):
            key = 'tag' + str(id)
            if key in json_obj.keys():
                tags.append(json_obj[key])
        return cls(desc, max_nb, img_path, tags)


    @classmethod
    def from_uniform_color(cls, color, size, tag = ''):
        tile = cls()
        tile.img = graphics.draw_uniform_tile(color, size)
        tile.tags.append(tag)
        assert tile.get_size() == size
        return tile


    def load_image(self):
        try:
            self.img = graphics.load_image(self.img_path)
        except Exception as e:
            logger.warning('Could not load image: %s (message: %s)', self.img_path, e)
            self.img = None


    def draw_image(self, size):
        assert self.img is None
        self.img = graphics.draw_game_tile(self.desc, size)
        assert self.get_size() == size


    def get_size(self):
        if self.img is None:
            return 0
        assert self.img.height() == self.img.width()
        return self.img.width()


def parse_tileset_description_file(json_file):
    fp = None
    cumul = 0
    try:
        with open(json_file, 'r', encoding='ascii') as fp:
            tileset_json = json.load(fp)
            assert 'tiles' in tileset_json.keys()
            for tile_json in tileset_json['tiles']:
                tile = Tile.from_json_description(tile_json, os.path.dirname(json_file))
                assert tile.max_nb >= 0
                if tile.max_nb > 0:
                    if 'start' in tile.tags:
                        assert tile.max_nb == 1
                    cumul += tile.max_nb
                    yield tile
    except FileNotFoundError:
        logger.warning('Could not load file %s', json_file)
    except AssertionError:
        handle_assertion_error()
    except Exception:
        logger.warning('Error parsing file %s', json_file)
        raise
    finally:
        if fp is not None:
            fp.close()
    if cumul > 0:
        logger.info('Loaded %d tiles from file %s', cumul, json_file)


def load_or_draw_tile_images(tileset, draw_all = False):
    assert graphics.is_init()
    tile_size = 0
    if not draw_all:
        for tile in tileset:
            tile.load_image()
            if tile.get_size() != 0:
                if tile_size == 0:
                    tile_size = tile.get_size()
                elif tile.get_size() != tile_size:
                    logger.critical('Image size of file %s (%d) does not match the previous size (%d)',
                                    tile.img_path, tile.get_size(), tile_size)
                    sys.exit(-1)
    if tile_size == 0:
        tile_size = DEFAULT_TILE_SIZE
    for tile in tileset:
        if tile.img is None:
            tile.draw_image(tile_size)
            assert tile.img is not None
    return tile_size


class PositionedTile:
    """Declare a position on the grid where a tile could be placed"""

    def __init__(self, pos: Vect, segments: List[Any] | None = None):
        if segments is None:
            segments = []
        self.pos = pos
        if len(segments) == 1:
            self.segment = segments[0]  # Common segment between the current map boundary and this tile
        else:
            self.segment = None         # Use None if unknown, or to indicate a forbidden position


    @classmethod
    def from_boundary_edge(cls, border: Boundary, point: Vect, edge: Vect, domain: Domain = Domain.EXTERIOR):
        tile_border = boundary.from_edge(point, edge, Orientation.COUNTERCLOCKWISE, domain)
        pos = tile_border.bottom_left()
        tile_border.rotate_to_start_with(pos)
        return cls(pos, border.common_segments(tile_border))


    def __repr__(self):
        return f'PositionedTile(pos = {self.pos}, segment = {self.segment})'


    def get_l1_distance(self):
        return self.pos.l1_distance()


    def get_segment(self):
        return self.segment if self.segment is not None else (0, 0, 0)


    def get_segment_length(self):
        (_, _, s) = self.get_segment()
        return s


    def iter_segment(self):
        (_, j, s) = self.get_segment()
        return self.get_boundary().iter_slice(j, j + s)


    def iter_complement_segment(self):
        (_, j, s) = self.get_segment()
        tile_border = self.get_boundary()
        if s == 0:
            return tile_border.iter_all(j)
        return tile_border.iter_slice(j + s, j)


    def get_boundary(self, desc = None):
        return boundary.get_tile(self.pos, desc)


class PlacedTile(PositionedTile):
    """Declares a Tile placed on the grid, with its position and orientation (r)"""

    def __init__(self, tile: Tile, pos: Vect, r: int, segment = None):
        PositionedTile.__init__(self, pos, [] if segment is None else [segment])
        self.tile = tile
        self.r = r


    @override
    def __repr__(self):
        return f'PlacedTile(pos = {self.pos}, r = {self.r}, segment = {self.segment}, tile = {self.tile})'


    @classmethod
    def from_positioned_tile(cls, pos_tile: PositionedTile, tile: Tile, r: int):
        return cls(tile, pos_tile.pos, r, pos_tile.segment)


    def draw(self, display: graphics.GridDisplay):
        assert self.tile.img is not None
        display.set_tile(self.tile.img, self.pos.x, self.pos.y, self.r)


    @override
    def get_boundary(self):
        desc = deque(self.tile.desc)
        desc.rotate(self.r)
        return PositionedTile.get_boundary(self, desc)


class CompositeTile:
    """A super-tile made of several unit tiles (e.g. the city of Carcasonne)"""

    class Elt:
        """A unit element of a composite tile"""

        def __init__(self, tile: Tile, offset: Vect):
            self.tile = tile
            self.offset = offset


    vect_re = re.compile(r'[Vv]ect_(\d+)_(\d+)')


    def __init__(self):
        self.elts = []


    def append(self, tile):
        offset = None
        for tag in tile.tags:
            result = self.vect_re.match(tag)
            if result:
                offset = Vect(int(result.group(1)), int(result.group(2)))
        if offset:
            self.elts.append(CompositeTile.Elt(tile, offset))
        else:
            logger.warning('Could not find the offset pattern in the tags for tile %s. Tags = %s.', tile, str(tile.tags))


    def __reduce(self, fun, initializer = None):
        self.elts.sort(key=operator.attrgetter('offset'))
        return functools.reduce(fun, self.elts, initializer)


    def draw(self, display: graphics.GridDisplay, pos: Vect, r: int = 0):

        def draw_elt(_, elt: CompositeTile.Elt) -> None:
            PlacedTile(elt.tile, pos + elt.offset.rotate(r), r).draw(display)

        self.__reduce(draw_elt)


    def get_boundary(self, pos: Vect, r: int = 0):

        def merge_boundary(border: Boundary, elt: CompositeTile.Elt) -> Boundary:
            border.merge(PlacedTile(elt.tile, pos + elt.offset.rotate(r), r).get_boundary())
            return border

        return self.__reduce(merge_boundary, Boundary())


class TileSubset:
    """Define a subset of a Tile set"""

    def __init__(self, predicate, shuffle = True, output_n = -1):
        self.predicate = predicate
        self.shuffle = shuffle      # Shuffle result
        self.output_n = output_n    # If < 0, output all


    def partition_iter(self, tileset_iter):
        it0, it1 = itertools.tee(tileset_iter)
        selection = list(filter(self.predicate, it0))
        if self.shuffle:
            selection = random.sample(selection, len(selection))
        if self.output_n >= 0:
            selection = selection[:self.output_n]
        return selection, itertools.filterfalse(self.predicate, it1)


    def partition(self, tileset_iter):
        part1, part2_iter = self.partition_iter(tileset_iter)
        return part1, list(part2_iter)


    @staticmethod
    def regular_start():
        def pred_regular_start(tile):
            return 'start' in tile.tags and 'river' not in tile.tags
        return TileSubset(pred_regular_start, output_n = 1)


    @staticmethod
    def carcassonne_city():
        def pred_city(tile):
            return 'carcassonne_city' in tile.tags
        return TileSubset(pred_city, shuffle = False)


    @staticmethod
    def river():
        def pred_river(tile):
            return 'river' in tile.tags
        return TileSubset(pred_river, shuffle = False)


    @staticmethod
    def river_source(n = -1):
        def pred_river_source(tile):
            return 'river' in tile.tags and 'source' in tile.tags
        return TileSubset(pred_river_source, output_n = n)


    @staticmethod
    def river_exclude_t_shaped():
        def pred_river_t_shaped(tile):
            return 'river' in tile.tags and list(tile.desc).count('R') == 3
        return TileSubset(pred_river_t_shaped, output_n = 0)


    @staticmethod
    def river_not_source_nor_sink():
        def pred_river_others(tile):
            return 'river' in tile.tags and 'source' not in tile.tags and 'lake' not in tile.tags
        return TileSubset(pred_river_others)


    @staticmethod
    def river_sink(n = -1):
        def pred_river_sink(tile):
            return 'river' in tile.tags and 'lake' in tile.tags
        return TileSubset(pred_river_sink, output_n = n)


    @staticmethod
    def shuffle_remaining():
        return TileSubset(lambda _: True)


    @staticmethod
    def exclude_remaining(warn_on_excluded = True):
        def pred_exclude_remaining(tile):
            if warn_on_excluded:
                logger.warning('Excluded tile: %s', tile)
            return True
        return TileSubset(pred_exclude_remaining, output_n = 0)


def iterate_tile_predicates(tile_predicates, tileset_iter):
    remaining = tileset_iter
    for predicate in tile_predicates:
        tile_subset, remaining = predicate.partition_iter(remaining)
        yield tile_subset
    TileSubset.exclude_remaining().partition_iter(remaining)


def iterate_tilesets(river_tileset, regular_tileset, river_tileset_period = 0, infinite = False):
    river_flag = len(river_tileset) > 0
    first = True
    while True:
        if river_flag:
            if river_tileset_period == 0:
                # Single use of the river tileset
                if first:
                    yield river_tileset
            else:
                # Reuse the river tileset periodically
                yield river_tileset
            for _ in range(max(1, river_tileset_period)):
                yield regular_tileset
        else:
            yield regular_tileset
        if not infinite:
            break
        first = False


def shuffle_tileset(tileset, first_tileset_flag: bool, river_placement_policies = None):
    if river_placement_policies is None:
        river_placement_policies = []
    river_flag = any('river' in tile.tags for tile in tileset)
    all_tiles = itertools.chain.from_iterable(itertools.repeat(tile, tile.max_nb) for tile in tileset)
    if river_flag:
        river_long = RiverPlacement.LONG_RIVER in river_placement_policies
        river_exclude_t_shaped = RiverPlacement.EXCLUDE_T in river_placement_policies
        # River sources
        if river_long and not first_tileset_flag:
            nb_of_sources = 0
        else:
            nb_of_sources = 1
        # River sinks
        if river_exclude_t_shaped:
            nb_of_sinks = 1
        else:
            nb_of_sinks = 2
        if river_long:
            nb_of_sinks = nb_of_sinks - 1
        # Predicates
        tile_predicates = [
            TileSubset.river_source(nb_of_sources)
        ]
        if river_exclude_t_shaped:
            tile_predicates += [
                TileSubset.river_exclude_t_shaped()
            ]
        tile_predicates += [
            TileSubset.river_not_source_nor_sink(),
            TileSubset.river_sink(nb_of_sinks),
        ]
    elif first_tileset_flag:
        tile_predicates = [
            TileSubset.regular_start(),
            TileSubset.shuffle_remaining()
        ]
    else:
        tile_predicates = [
            TileSubset.shuffle_remaining()
        ]
    return iterate_tile_predicates(tile_predicates, all_tiles)


class CandidateTiles:
    """Class defining a set of candidate Tiles"""

    def __init__(self, on_update = None, on_delete = None):
        assert not on_update or callable(on_update)
        assert not on_delete or callable(on_delete)
        self.sorted_positions = []          # List of positions
        self.tiles = {}                     # Dict of position -> PositionedTile
        self.nb_to_be_deleted = 0
        self.on_update = on_update
        self.on_delete = on_delete


    def __len__(self):
        return len(self.tiles)


    def allocated(self):
        return len(self.sorted_positions)


    @staticmethod
    def to_be_deleted(pos_tile):
        # Ad hoc criteria to identify a tile to be deleted
        return pos_tile.get_segment_length() == 0


    def iterate(self):
        for pos in self.sorted_positions:
            if pos in self.tiles:
                yield self.tiles[pos]


    def update(self, pos_tile: PositionedTile):
        if self.on_update:
            self.on_update(pos_tile)
        if self.to_be_deleted(pos_tile):
            self.delete(pos_tile.pos)
        else:
            if pos_tile.pos not in self.tiles:
                if pos_tile.pos not in self.sorted_positions:
                    self.sorted_positions.append(pos_tile.pos)
                else:
                    # We are restoring a deleted entry
                    assert self.nb_to_be_deleted > 0
                    self.nb_to_be_deleted -= 1
            self.tiles[pos_tile.pos] = pos_tile


    def delete(self, pos: Vect):
        if self.on_delete:
            self.on_delete(pos)
        if pos in self.tiles:
            self.nb_to_be_deleted += 1
            del self.tiles[pos]


    def __resize(self):
        assert self.allocated() == len(self) + self.nb_to_be_deleted
        assert all(self.sorted_positions[idx] not in self.tiles for idx in range(len(self), self.allocated()))
        del self.sorted_positions[len(self):]
        self.nb_to_be_deleted = 0
        assert self.allocated() == len(self) + self.nb_to_be_deleted


    def force_resize(self):
        self.sorted_positions.sort(key = lambda pos: 0 if pos in self.tiles else 1)
        self.__resize()


    def __sort_key(self, key_on_positioned_tile, reverse, pos):
        if pos not in self.tiles:
            return -sys.maxsize if reverse else sys.maxsize
        return key_on_positioned_tile(self.tiles[pos])


    def __sort(self, key_on_positioned_tile, reverse: bool):
        self.sorted_positions.sort(key = lambda pos: self.__sort_key(key_on_positioned_tile, reverse, pos),
                                   reverse = reverse)


    def sort(self, key, reverse = False):
        self.__sort(key, reverse)
        # Resize if the nb of tiles marked for deletion is passed a certain threshold
        if len(self) > 0 and (self.allocated() / len(self)) > 1.333:
            self.__resize()


    def extra_debug_printout(self):
        logger.debug('Candidates: (used/total: %d/%d)', len(self.tiles), len(self.sorted_positions))
        for pos in self.sorted_positions:
            if pos in self.tiles:
                logger.debug('nb_contact_sides=%d, pos=%s', self.tiles[pos].get_segment_length(), repr(pos))
            else:
                logger.debug('to_be_deleted, pos=%s', repr(pos))


def validate_tile_placement(placed_tile, border):
    # Trivial except for river tiles
    if 'R' in Boundary.label_getter(placed_tile.iter_segment()):
        test_border = border.copy()
        test_border.merge(placed_tile.get_boundary())
        for (point, edge, label) in placed_tile.iter_complement_segment():
            if label == 'R':
                test_tile_border = boundary.from_edge(point, edge, Orientation.COUNTERCLOCKWISE, Domain.EXTERIOR)
                common_segments = test_border.common_segments(test_tile_border)
                if len(common_segments) != 1:
                    return False
                (_, _, s) = common_segments[0]
                if s != 1:
                    return False
    return True


def update_border_and_candidate_tiles(placed_tile: PlacedTile,
                                      border: Boundary,
                                      candidate_tiles: CandidateTiles) -> PlacedTile:
    """
    This function updates the map boundary and the candidate tile placements

    Arguments:
        placed_tile     The tile being added to the map boundary
        border          The current map boundary
        candidate_tiles The list of candidate tiles along the map boundary

    Notes:
    A candidate tile placement is an unoccupied tile adjacent to the map boundary.
    In order to prioritize a tile placement among other candidates, the following parameters are used:
     - The length of the segment in contact with the map boundary
     - The L1 distance of the tile to the center of the map
    """
    # Merge the newly placed tile to the map boundary
    border.merge(placed_tile.get_boundary())

    # Account for the change in the map boundary in candidate_tiles
    candidate_tiles.delete(placed_tile.pos)
    neighbor_edges = [(point, edge) for (point, edge, _) in placed_tile.iter_complement_segment()]
    neighbor_edges.extend([(point + edge, edge) for (point, edge) in neighbor_edges[:-1]])
    tiles_to_update = [PositionedTile.from_boundary_edge(border, point, edge) for (point, edge) in neighbor_edges]
    for pos_tile in tiles_to_update:
        candidate_tiles.update(pos_tile)

    # Sort the updated list of candidates
    candidate_tiles.sort(key=PlacedTile.get_l1_distance)
    candidate_tiles.sort(key=PlacedTile.get_segment_length, reverse=True)
    if EXTRA_DEBUG_PRINTOUT:
        candidate_tiles.extra_debug_printout()
    return placed_tile


def select_tile_placement(candidate_placements: List[PlacedTile]):
    assert len(candidate_placements) > 0
    return candidate_placements[0]              # Nothing fancy


def find_candidate_placements(tile: Tile, border: Boundary, candidate_tiles: CandidateTiles,
                              max_candidates: int = -1, force_edge_label: str | None = None) -> List[PlacedTile]:
    assert len(border) > 0
    assert len(candidate_tiles) > 0
    candidate_placements = []
    for pos_tile in candidate_tiles.iterate():
        (i0, j0, s0) = pos_tile.get_segment()
        assert s0 > 0
        tile_border = pos_tile.get_boundary(list(tile.desc))
        # Recompute PositionedTile because the common segment's 'i' index will not match
        pos_tile = PositionedTile(pos_tile.pos, border.common_segments(tile_border))
        (i1, j1, s1) = pos_tile.get_segment()
        if (j0, s0) != (j1, s1):
            logger.warning('Incoherent common segments for tile at %d in candidate_tiles: %s and computed against the current border: %s',
                           repr(pos_tile.pos), repr((i0, j0, s0)), repr((i1, j1, s1)))
            continue
        if force_edge_label and force_edge_label not in Boundary.label_getter(border.iter_slice(i1, i1 + s1)):
            continue
        for r in border.find_matching_rotations(tile_border, pos_tile.get_segment()):
            placed_tile = PlacedTile.from_positioned_tile(pos_tile, tile, r)
            if validate_tile_placement(placed_tile, border):
                candidate_placements.append(placed_tile)
        if max_candidates > 0 and len(candidate_placements) >= max_candidates:
            break
    return candidate_placements


CARCASSONNE_CITY_NB_OF_TILES = 12


def place_carcassonne_city(tileset: List[Any], candidate_tiles: CandidateTiles,
                           display: graphics.GridDisplay, z: float, pos: Vect, r: int = 0) -> tuple[Boundary, int]:
    assert len(tileset) > 0
    if len(tileset) != CARCASSONNE_CITY_NB_OF_TILES:
        logger.warning('Expected %d tiles for the city of Carcassonne', CARCASSONNE_CITY_NB_OF_TILES)
    composite_tile = CompositeTile()
    for tile in tileset:
        assert 'carcassonne_city' in tile.tags
        composite_tile.append(tile)
    composite_tile.draw(display, pos, r)
    display.update(z)
    border = composite_tile.get_boundary(pos, r)
    neighbor_tiles = [PositionedTile.from_boundary_edge(border, point, edge) for (point, edge, _) in border.iter_all()]
    for pos_tile in neighbor_tiles:
        candidate_tiles.update(pos_tile)
    return border, len(tileset)


def parse_river_placement_policies(policies):
    result = []
    # Policy: T-shaped tile
    if RiverPlacement.USE_T in policies:
        result.append(RiverPlacement.USE_T)
    elif RiverPlacement.EXCLUDE_T in policies:
        result.append(RiverPlacement.EXCLUDE_T)
    else:
        result.append(RIVER_PLACEMENT_DEFAULT_T_POLICY)
    # Policy: River length
    if RiverPlacement.SHORT_RIVER in policies:
        result.append(RiverPlacement.SHORT_RIVER)
    elif RiverPlacement.LONG_RIVER in policies:
        result.append(RiverPlacement.LONG_RIVER)
    else:
        result.append(RIVER_PLACEMENT_DEFAULT_LENGTH_POLICY)
    assert len(result) == 2
    return result


def generate_map(args):
    # Set random seed
    rng_seed = args.seed if args.seed != 0 else secrets.randbits(64)
    logger.info('Random seed: %s', str(rng_seed))
    random.seed(rng_seed)

    # Load tileset (JSON files)
    tileset = list(itertools.chain.from_iterable(parse_tileset_description_file(json_file) for json_file in args.files))
    if len(tileset) == 0:
        logger.critical('No tiles loaded')
        sys.exit(-1)

    # River tiles placement policy and period
    river_placement_policies = parse_river_placement_policies([RiverPlacement[policy] for policy in args.river_policy])
    river_tileset_period = args.river_period if args.river_period >= 0 else 0
    if any('river' in tile.tags for tile in tileset):
        logger.debug('river_placement_policies: %s', str([policy.name for policy in river_placement_policies]))
        logger.debug('river_tileset_period: %d', river_tileset_period)

    try:
        # Load tile images, and draw missing ones
        graphics.init()
        tile_size = load_or_draw_tile_images(tileset, args.draw_all)
        carcassonne_city_tileset, tileset = TileSubset.carcassonne_city().partition_iter(tileset)
        city_start_flag = len(carcassonne_city_tileset) > 0
        river_tileset, regular_tileset = TileSubset.river().partition(tileset)
        del tileset

        # Non-game tiles
        forbidden_tile = Tile.from_uniform_color((100,  20,  20), tile_size, 'forbidden')
        #riverside_tile = Tile.from_uniform_color((217, 236, 255), tile_size, 'riverside')
        segment_length_tiles = {
            0: forbidden_tile,
            1: Tile.from_uniform_color((10,  60, 10), tile_size, 'one_side'),
            2: Tile.from_uniform_color((40, 120, 40), tile_size, 'two_sides'),
            3: Tile.from_uniform_color((70, 180, 70), tile_size, 'three_sides')
        }

        # Open display
        w, h = DEFAUT_DISPLAY_W, DEFAUT_DISPLAY_H
        display = graphics.GridDisplay(w, h, args.fullscreen, tile_size)
        logger.info("Press 'F11' or 'F'' to toggle fullscreen")
        logger.info("Press 'ESCAPE' in the graphics window to quit")

        # Place random tiles. The map must grow!
        candidate_tiles = CandidateTiles(
            on_update = lambda pos_tile: display.set_tile(segment_length_tiles[pos_tile.get_segment_length()].img,
                                                          pos_tile.pos.x, pos_tile.pos.y) if args.debug_mode else None,
            on_delete = None)
        z = args.zoom_factor
        border = Boundary()
        total_nb_tiles_placed = 0
        total_nb_tiles_not_placed = 0

        # Place the composite tile first
        if city_start_flag:
            border, total_nb_tiles_placed = place_carcassonne_city(carcassonne_city_tileset, candidate_tiles, display, z, Vect(-2, -1))
            logger.debug('total_nb_tiles_placed: %d', total_nb_tiles_placed)

        first_tileset_flag = not city_start_flag
        all_done_flag = False
        infinite_iterations = args.max_tiles > 0 and len(regular_tileset) > 0
        for tileset in iterate_tilesets(river_tileset, regular_tileset, river_tileset_period, infinite=infinite_iterations):
            for tiles_to_place in shuffle_tileset(tileset, first_tileset_flag, river_placement_policies):
                local_nb_tiles_placed = 0
                while len(tiles_to_place) > 0:
                    tiles_not_placed = []
                    for tile in tiles_to_place:
                        if args.max_tiles > 0 and total_nb_tiles_placed >= args.max_tiles:
                            all_done_flag = True
                            break
                        if len(border) == 0:
                            # The first tile of the map is placed at the center
                            placed_tile = PlacedTile(tile, Vect(0, 0), r = 0)
                        else:
                            forced_segment = 'R' if 'river' in tile.tags and 'source' not in tile.tags else ''
                            max_candidates = 1
                            candidate_placements = find_candidate_placements(tile, border, candidate_tiles, max_candidates, forced_segment)
                            placed_tile = select_tile_placement(candidate_placements) if len(candidate_placements) > 0 else None
                        if placed_tile:
                            update_border_and_candidate_tiles(placed_tile, border, candidate_tiles)
                            placed_tile.draw(display)
                            total_nb_tiles_placed += 1
                            local_nb_tiles_placed += 1
                            # z = 0.995 * z
                            # display.update(z, 100)
                        else:
                            tiles_not_placed.append(tile)
                    if all_done_flag:
                        break
                    if len(tiles_not_placed) == len(tiles_to_place):
                        # making no progress, stop there
                        total_nb_tiles_not_placed += len(tiles_not_placed)
                        for tile in tiles_not_placed:
                            logger.debug('Could not place tile: %s', tile)
                        break
                    assert len(tiles_not_placed) < len(tiles_to_place)
                    #logger.debug('len(tiles_not_placed): %d; len(tiles_to_place): %d', len(tiles_not_placed), len(tiles_to_place))
                    tiles_to_place = tiles_not_placed

                # Done with the current tiles subset
                logger.debug('total_nb_tiles_placed: %d (+%d)', total_nb_tiles_placed, local_nb_tiles_placed)
                if all_done_flag:
                    break

            # Done with the current tileset
            if all_done_flag:
                break
            first_tileset_flag = False
            display.update(z)

        # Completely done!
        display.update(z)
        logger.info('Done!')
        logger.info('total_nb_tiles_not_placed: %d', total_nb_tiles_not_placed)
        logger.info('total_nb_tiles_placed: %d', total_nb_tiles_placed)

        # Wait until the user quits
        while True:
            display.check_event_queue(200)

    except graphics.MustQuit:
        pass

    finally:
        if 'display' in locals():
            logger.debug('Display: %s', str(display.get_debug_info()))
            if args.take_screenshot or args.debug_mode:
                display.take_screenshot(SCREENSHOT_PATH)
                logger.info('Screenshot saved in %s', SCREENSHOT_PATH)
            if args.dump_to_img:
                display.dump_to_img(DUMP_PATH, args.zoom_factor)
                logger.info('Dump grid to %s', DUMP_PATH)
        graphics.quit_window()

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Display a randomized Carcassonne map')
    parser.add_argument('files', metavar='FILE', nargs='*',
                        help='Tile description file (JSON format)')
    parser.add_argument('-d', '--debug', dest='debug_mode', action='store_true',
                        help='Display non-game tiles, debug log level, etc.')
    parser.add_argument('-n', metavar='N', type=int, dest='max_tiles', default = 0,
                        help='Number of tiles to display (Default: The whole tileset)')
    parser.add_argument('-z', '--zoom-factor', metavar='Z', type=float, dest='zoom_factor', default = 1.0,
                        help='Initial zoom factor (Default: 1.0)')
    parser.add_argument('--draw-all', dest='draw_all', action='store_true',
                        help='Draw a simplified representation of the tiles')
    parser.add_argument('-f', '--full-screen', dest='fullscreen', action='store_true',
                        help='Full screen')
    parser.add_argument('-s', '--screenshot', dest='take_screenshot', action='store_true',
                        help='Take a screenshot of the final display')
    parser.add_argument('--dump', dest='dump_to_img', action='store_true',
                        help='Dump the final grid to an image')
    parser.add_argument('--river-policy', type=str, dest='river_policy',
                        choices=[policy.name for policy in RiverPlacement], action='append', default=[],
                        help='Placement policies for the river tileset. This option can be used multiple times.')
    parser.add_argument('--river-period', metavar='P', type=int, dest='river_period', default=1,
                        help='Period of repetition of the river tileset. Set to zero for a single use of the river tileset')
    parser.add_argument('--seed', metavar='INT', type=int, dest='seed', default = 0,
                        help='A seed for the random generator (Default: Use a system generated seed)')
    cmd_line_args = parser.parse_args()

    debug_log_lvl = cmd_line_args.debug_mode or EXTRA_DEBUG_PRINTOUT
    logging.basicConfig(level=logging.DEBUG if debug_log_lvl else logging.INFO,
                        format='%(levelname)s: %(message)s')

    generate_map(cmd_line_args)
