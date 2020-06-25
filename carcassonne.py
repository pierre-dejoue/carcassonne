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
from collections import deque
from operator import itemgetter


DEFAULT_TILE_SIZE = 100
DEBUG_PRINTOUT = False


def warn(msg):
    print("Warning: " + msg)


def error(msg):
    print("Error: " + msg, file = sys.stderr)
    exit(-1)


class Tile:
    def __init__(self, json_obj, basedir):
        assert 'description' in json_obj.keys()
        self.desc = json_obj['description']
        self.remaining_nb = json_obj['cardinality'] if 'cardinality' in json_obj.keys() else 1
        self.img_path = os.path.join(basedir, json_obj['img']) if 'img' in json_obj.keys() and json_obj['img'] else ''
        self.img = None
        self.tags = []
        for ii in range(10):
            key = 'tag' + str(ii)
            if key in json_obj.keys():
                self.tags.append(json_obj[key])


    def load_image(self):
        try:
            self.img = graphics.load_image(self.img_path)
        except Exception as e:
            warn('Could not load image: {} (message: {})'.format(self.img_path, e))
            self.img = None


    def draw_image(self, size):
        assert self.img is None
        self.img = graphics.draw_tile(self.desc, size)
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
            tile = Tile(tile_json, os.path.dirname(json_file))
            assert tile.remaining_nb >= 0
            if tile.remaining_nb > 0:
                if 'start' in tile.tags:
                    assert tile.remaining_nb == 1
                cumul += tile.remaining_nb
                yield tile
    except FileNotFoundError:
        warn('Could not load file {}'.format(json_file))
    except AssertionError:
        _, _, tb = sys.exc_info()
        tb_info = traceback.extract_tb(tb)
        filename, line, func, text = tb_info[-1]
        warn('An error occurred in file {} line {} in statement "{}"'.format(filename, line, text))
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
    def __init__(self, tile, i, j, r):
        self.tile = tile
        self.pos = (i, j)
        self.rotate(r)


    def get_l1_distance(self):
        return abs(self.pos[0]) + abs(self.pos[1])


    def rotate(self, r):
        self.r = r
        self.desc = deque(self.tile.desc)
        self.desc.rotate(r) # right rotate


    def draw(self, display):
        assert self.tile.img is not None
        display.set_tile(self.tile.img, self.pos[0], self.pos[1], self.r)


    def get_boundary(self):
        return boundary.get_tile(self.pos[0], self.pos[1], self.desc)


class TileSubset:
    def __init__(self, predicate, shuffle = True, output_n = -1):
        self.predicate = predicate
        self.shuffle = shuffle      # Shuffle result
        self.output_n = output_n    # if < 0, output all that match the predicate


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
    def river_source():
        def pred_river_source(tile):
            return 'river' in tile.tags and 'source' in tile.tags
        return TileSubset(pred_river_source, output_n = 1)


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


def shuffle_tileset(tileset, river = False):
    all_tiles = itertools.chain.from_iterable([itertools.repeat(tile, tile.remaining_nb) for tile in tileset])
    if river:
        tile_predicates = [
            TileSubset.river_source(),
            TileSubset.river_not_source_nor_sink(),
            TileSubset.river_sink(),
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
     - The number of segments in contact with the boundary
     - The L1 distance of the tile to the center of the map

    candidate_placements: List of tuples (placed_tile, nb_contact_segments)
    """
    assert len(candidate_placements) > 0
    candidate_placements.sort(key=lambda tuple : tuple[0].get_l1_distance())
    candidate_placements.sort(key=itemgetter(1), reverse=True)
    if DEBUG_PRINTOUT:
        print("Candidates:")
        for (placed_tile, L) in candidate_placements:
            print('nb_contact_segments={}, pos=({}, {}), r={}'.format(L, placed_tile.pos[0], placed_tile.pos[1], placed_tile.r))
    return candidate_placements[0][0]


def find_candidate_placements(tile, border, max_candidates = -1, forced_segment = None):
    N = len(border)
    if N == 0:
        return [(PlacedTile(tile, 0, 0, 0), 0)]     # Corner case: The first tile of the map

    candidate_placements = []
    tagged = set()
    start_idx = random.randrange(N)
    for idx in range(start_idx, start_idx + N):
        if idx >= N:
            idx -= N
        point = border.points[idx]
        if forced_segment is not None and forced_segment != border.labels[idx]:
            continue
        edge = border.get_edge(idx)
        tile_boundary = boundary.from_edge(point, edge, Orientation.COUNTERCLOCKWISE, Domain.EXTERIOR)
        (i, j) = tile_boundary.bottomleft()
        if (i, j) in tagged:
            continue
        tagged.add((i, j))
        common_segments = border.common_segments(boundary.get_tile(i, j))
        if len(common_segments) != 1:
            continue
        (border_idx, tile_idx, L) = common_segments[0]
        border_labels = border.slice(border_idx, border_idx + L).labels
        border_labels.reverse()
        for r in range(4):
            placed_tile = PlacedTile(tile, i, j, r)
            tile_labels = placed_tile.get_boundary().slice(tile_idx, tile_idx + L).labels
            if tile_labels == border_labels:
                candidate_placements.append((placed_tile, L))
        if max_candidates > 0 and len(candidate_placements) >= max_candidates:
            break
    return candidate_placements


def main():
    parser = argparse.ArgumentParser(description='Display a randomized Carcassonne map')
    parser.add_argument('files', metavar='FILE', nargs='*', help='Tile description file (JSON format)')
    parser.add_argument('-n', metavar='N', type=int, dest='max_tiles', default = 0, help='Number of tiles to display (Default: The whole tileset)')
    parser.add_argument('-z', '--zoom-factor', metavar='Z', type=float, dest='zoom_factor', default = 1.0, help='Initial zoom factor (Default: 1.0)')
    parser.add_argument('-d', '--draw-all', dest='draw_all', action='store_true', help='Draw all tiles')
    parser.add_argument('-f', '--full-screen', dest='full_screen', action='store_true', help='Full screen')
    args = parser.parse_args()

    # Load tileset (JSON files)
    tileset = list(itertools.chain.from_iterable(parse_tileset_description_file(json_file) for json_file in args.files))
    river_map_flag = any('river' in tile.tags for tile in tileset)

    try:
        # Load tile images, and draw missing ones
        graphics.init()
        tile_size = load_or_draw_tile_images(tileset, args.draw_all)

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
            first_tileset = False
            tile_subsets_to_place = shuffle_tileset(tileset, river_map_flag)
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
                            border.merge(placed_tile.get_boundary())
                            placed_tile.draw(display)
                            #z = 0.995 * z
                            #display.update(z, 100)
                            nb_tiles_placed += 1
                        else:
                            warn('Could not placed tile {}'.format(tile.desc))
                            tiles_not_placed.append(tile)
                    if nb_tiles_placed == 0:
                        break
                    total_nb_tiles_placed += nb_tiles_placed
                    if DEBUG_PRINTOUT:
                        print('total_nb_tiles_placed: {} (+{})'.format(total_nb_tiles_placed, nb_tiles_placed))
                    display.update(z, 100)
                    tiles_to_place = tiles_not_placed

        # Wait until the user quits
        while True:
            display.check_event_queue(200)

    except graphics.MustQuit:
        pass

    finally:
        if DEBUG_PRINTOUT and 'display' in locals():
            print(display.get_debug_info())
        graphics.quit()

    return 0


if __name__ == "__main__":
    main()
