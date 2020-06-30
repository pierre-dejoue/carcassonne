#!/usr/bin/env python


import argparse
import boundary
import graphics
import itertools
import json
import os.path
import random
import sys
import traceback
from boundary import Boundary
from boundary import Domain
from boundary import Orientation
from boundary import Vect
from collections import deque


DEBUG_PRINTOUT = False
DEFAULT_TILE_SIZE = 100
SCREENSHOT_PATH = './screenshot.jpg'


def warn(msg):
    print("Warning: " + msg)


def error(msg):
    print("Error: " + msg, file = sys.stderr)
    exit(-1)


def handle_assertion_error():
    _, _, tb = sys.exc_info()
    tb_info = traceback.extract_tb(tb)
    filename, line, func, text = tb_info[-1]
    warn('An error occurred in file {} line {} in statement "{}"'.format(filename, line, text))


class Tile:
    """A game tile defined by the descrption of each of its four sides"""
    def __init__(self, desc = [None, None, None, None], remaining_nb = 1, img_path = '', tags = []):
        self.desc = desc
        self.remaining_nb = remaining_nb
        self.img_path = img_path
        self.img = None
        self.tags = tags


    @classmethod
    def from_json_description(cls, json_obj, basedir):
        assert 'description' in json_obj.keys()
        desc = json_obj['description']
        remaining_nb = json_obj['cardinality'] if 'cardinality' in json_obj.keys() else 1
        img_path = os.path.join(basedir, json_obj['img']) if 'img' in json_obj.keys() and json_obj['img'] else ''
        tags = []
        for id in range(10):
            key = 'tag' + str(id)
            if key in json_obj.keys():
                tags.append(json_obj[key])
        return cls(desc, remaining_nb, img_path, tags)


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
            warn('Could not load image: {} (message: {})'.format(self.img_path, e))
            self.img = None


    def draw_image(self, size):
        assert self.img is None
        self.img = graphics.draw_game_tile(self.desc, size)
        assert self.get_size() == size


    def get_size(self):
        if self.img is not None:
            assert self.img.height() == self.img.width()
            return self.img.width()
        else:
            return 0


def parse_tileset_description_file(json_file):
    fp = None
    cumul = 0
    try:
        fp = open(json_file, 'r')
        tileset_json = json.load(fp)
        assert 'tiles' in tileset_json.keys()
        for tile_json in tileset_json['tiles']:
            tile = Tile.from_json_description(tile_json, os.path.dirname(json_file))
            assert tile.remaining_nb >= 0
            if tile.remaining_nb > 0:
                if 'start' in tile.tags:
                    assert tile.remaining_nb == 1
                cumul += tile.remaining_nb
                yield tile
    except FileNotFoundError:
        warn('Could not load file {}'.format(json_file))
    except AssertionError:
        handle_assertion_error()
    except Exception:
        warn('Error parsing file {}'.format(json_file))
        raise
    finally:
        if fp is not None:
            fp.close()
    if cumul > 0:
        print('Loaded {} tiles from file {}'.format(cumul, json_file))


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
                    error("Image size of file " + tile.img_path + " (" + str(tile.get_size()) + ") does not match the previous size (" + str(tile_size) + ")")
    if tile_size == 0:
        tile_size = DEFAULT_TILE_SIZE
    for tile in tileset:
        if tile.img is None:
            tile.draw_image(tile_size)
            assert tile.img is not None
    return tile_size


class PlacedTile:
    def __init__(self, tile, pos, r, segment = None):
        self.tile = tile
        self.pos = pos
        self.r = r
        self.segment = segment  # Common segment between the border and this tile


    def get_l1_distance(self):
        return self.pos.l1_distance()


    def get_segment(self):
        return self.segment if self.segment is not None else (0, 0, 0)


    def get_segment_length(self):
        (_, _, L) = self.get_segment()
        return L


    def iter_segment(self):
        (_, j, L) = self.get_segment()
        return self.get_boundary().iter_slice(j, j + L)


    def iter_complement_segment(self):
        (_, j, L) = self.get_segment()
        tile_border = self.get_boundary()
        if L == 0:
            return itertools.chain(tile_border.iter_slice(j, 0), tile_border.iter_slice(0, j))
        else:
            return tile_border.iter_slice(j + L, j)


    def draw(self, display):
        assert self.tile.img is not None
        display.set_tile(self.tile.img, self.pos.x, self.pos.y, self.r)


    def get_boundary(self):
        desc = deque(self.tile.desc)
        desc.rotate(self.r)
        return boundary.get_tile(self.pos, desc)


class TileSubset:
    def __init__(self, predicate, shuffle = True, output_n = -1):
        self.predicate = predicate
        self.shuffle = shuffle      # Shuffle result
        self.output_n = output_n    # If < 0, output all


    def partition(self, tileset_iter):
        it0, it1 = itertools.tee(tileset_iter)
        selection = list(filter(self.predicate, it0))
        if self.shuffle:
            selection = random.sample(selection, len(selection))
        if self.output_n >= 0:
            selection = selection[:self.output_n]
        return (selection, itertools.filterfalse(self.predicate, it1))


    @staticmethod
    def regular_start():
        def pred_regular_start(tile):
            return 'start' in tile.tags and 'river' not in tile.tags
        return TileSubset(pred_regular_start, output_n = 1)


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
        return TileSubset(lambda _: True, shuffle = True)



def apply_tile_predicates(tile_predicates, tileset_iter, append_remaining = True, shuffle_remaining = True):
    def subset_generator(predicates, remaining):
        for predicate in predicates:
            tile_subset, remaining = predicate.partition(remaining)
            yield tile_subset

    return subset_generator(tile_predicates, tileset_iter)


def shuffle_tileset(tileset, river = False, first_tileset = True):
    all_tiles = itertools.chain.from_iterable(itertools.repeat(tile, tile.remaining_nb) for tile in tileset)
    if river:
        tile_predicates = [
            TileSubset.river_source(1 if first_tileset else 0),
            TileSubset.river_exclude_t_shaped(),
            TileSubset.river_not_source_nor_sink(),
            TileSubset.river_sink(0),
            TileSubset.shuffle_remaining()
        ]
    else:
        tile_predicates = [
            TileSubset.regular_start(),
            TileSubset.shuffle_remaining()
        ]
    return list(apply_tile_predicates(tile_predicates, all_tiles))


def select_tile_placement(candidate_placements):
    """
    A candidate tile placement is an unoccupied tile adjacent to the map boundary.
    In order to prioritize a placement among all candidates, the following parameters are used:
     - The length of the segment in contact with the boundary
     - The L1 distance of the tile to the center of the map

    candidate_placements: A list of PlacedTile objects
    """
    assert len(candidate_placements) > 0
    candidate_placements.sort(key=PlacedTile.get_l1_distance)
    candidate_placements.sort(key=PlacedTile.get_segment_length, reverse=True)
    if DEBUG_PRINTOUT:
        print("Candidates in decreasing priority:")
        for placed_tile in candidate_placements:
            print('nb_contact_sides={}, pos=({}, {}), r={}'.format(placed_tile.get_segment_length(), placed_tile.pos[0], placed_tile.pos[1], placed_tile.r))
    return candidate_placements[0]


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
                (_, _, L) = common_segments[0]
                if L != 1:
                    return False
    return True


def find_candidate_placements(tile, border, max_candidates = -1, force_edge_label = None):
    N = len(border)

    if N == 0:
        return [PlacedTile(tile, Vect(0, 0), r = 0)]    # Corner case: The first tile of the map

    candidate_placements = []
    tagged = set()
    start_idx = random.randrange(N)
    for idx in range(start_idx, start_idx + N):
        point = border.get_point(idx)
        label = border.get_label(idx)
        edge = border.get_edge(idx)
        if label is None:
            continue
        if force_edge_label is not None and label != force_edge_label:
            continue
        tile_border = boundary.from_edge(point, edge, Orientation.COUNTERCLOCKWISE, Domain.EXTERIOR)
        pos = tile_border.bottom_left()
        if pos in tagged:
            continue
        tagged.add(pos)
        tile_border.rotate_to_start_with(pos)
        tile_border.set_labels(list(tile.desc))
        common_segments = border.common_segments(tile_border)
        if len(common_segments) != 1:
            continue
        for r in border.find_matching_rotations(tile_border, common_segments[0]):
            placed_tile = PlacedTile(tile, pos, r, common_segments[0])
            if validate_tile_placement(placed_tile, border):
                candidate_placements.append(placed_tile)
        if max_candidates > 0 and len(candidate_placements) >= max_candidates:
            break
    return candidate_placements


def main():
    parser = argparse.ArgumentParser(description='Display a randomized Carcassonne map')
    parser.add_argument('files', metavar='FILE', nargs='*', help='Tile description file (JSON format)')
    parser.add_argument('-d', '--debug', dest='debug_mode', action='store_true', help='Display non-game tiles, etc.')
    parser.add_argument('-n', metavar='N', type=int, dest='max_tiles', default = 0, help='Number of tiles to display (Default: The whole tileset)')
    parser.add_argument('-z', '--zoom-factor', metavar='Z', type=float, dest='zoom_factor', default = 1.0, help='Initial zoom factor (Default: 1.0)')
    parser.add_argument('--draw-all', dest='draw_all', action='store_true', help='Draw all tiles')
    parser.add_argument('-f', '--full-screen', dest='full_screen', action='store_true', help='Full screen')
    parser.add_argument('-s', '--screenshot', dest='take_screenshot', action='store_true', help='Take a screenshot of the final display')
    args = parser.parse_args()

    # Load tileset (JSON files)
    tileset = list(itertools.chain.from_iterable(parse_tileset_description_file(json_file) for json_file in args.files))
    river_map_flag = any('river' in tile.tags for tile in tileset)

    try:
        # Load tile images, and draw missing ones
        graphics.init()
        tile_size = load_or_draw_tile_images(tileset, args.draw_all)

        # Non-game tiles
        riverside_tile = Tile.from_uniform_color((217, 236, 255), tile_size, 'riverside')

        # Open display
        (w, h) = (0, 0) if args.full_screen else (1280, 720)
        display = graphics.GridDisplay(w, h, tile_size)
        print('Press ESCAPE in the graphics window to quit', flush = True)

        # Place random tiles. The map must grow!
        border = Boundary()
        z = args.zoom_factor
        total_nb_tiles_placed = 0
        nb_tiles_placed = 0
        first_tileset = True
        while (args.max_tiles == 0 and first_tileset) or total_nb_tiles_placed < args.max_tiles:
            tile_subsets_to_place = shuffle_tileset(tileset, river_map_flag, first_tileset)
            for tiles_to_place in tile_subsets_to_place:
                while len(tiles_to_place) > 0 and (args.max_tiles == 0 or total_nb_tiles_placed < args.max_tiles):
                    nb_tiles_placed = 0
                    tiles_not_placed = []
                    for tile in tiles_to_place:
                        if args.max_tiles > 0 and total_nb_tiles_placed + nb_tiles_placed >= args.max_tiles:
                            break
                        forced_segment = 'R' if 'river' in tile.tags and 'source' not in tile.tags else None
                        max_candidates = 20
                        candidates = find_candidate_placements(tile, border, max_candidates, forced_segment)
                        if len(candidates) > 0:
                            placed_tile = select_tile_placement(candidates)
                            border.merge(placed_tile.get_boundary(), placed_tile.segment)
                            placed_tile.draw(display)
                            #z = 0.995 * z
                            #display.update(z, 100)
                            nb_tiles_placed += 1
                        else:
                            warn('Could not place tile {}'.format(tile.desc))
                            tiles_not_placed.append(tile)
                    if nb_tiles_placed == 0:
                        break
                    total_nb_tiles_placed += nb_tiles_placed
                    if DEBUG_PRINTOUT:
                        print('total_nb_tiles_placed: {} (+{})'.format(total_nb_tiles_placed, nb_tiles_placed))
                    display.update(z, 100)
                    tiles_to_place = tiles_not_placed
            display.update(z)
            first_tileset = False

        # Wait until the user quits
        while True:
            display.check_event_queue(200)

    except graphics.MustQuit:
        pass

    finally:
        if args.debug_mode and 'display' in locals():
            print(display.get_debug_info())
        if (args.take_screenshot or args.debug_mode) and 'display' in locals():
            display.take_screenshot(SCREENSHOT_PATH)
            print('Screenshot saved in {}'.format(SCREENSHOT_PATH))
        graphics.quit()

    return 0


if __name__ == "__main__":
    main()
