#!/usr/bin/env python


import argparse
import boundary
import graphics
import itertools
import json
import os.path
import random
from boundary import Boundary
from boundary import Domain
from boundary import Orientation
from collections import deque
from operator import itemgetter


DEFAULT_TILE_SIZE = 100


def warn(msg):
    print("Warning: " + msg)


def error(msg):
    print("Error: " + msg)
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
        self.img = graphics.load_image(self.img_path)


    def draw_image(self, size):
        assert self.img is None
        self.img = graphics.draw_tile(self.desc, size)
        assert self.get_size() == size


    def get_size(self):
        if self.img is not None:
            assert self.img.get_height() == self.img.get_width()
            return self.img.get_width()
        else:
            return 0


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
    if False:
        # Debug printout
        print("Tile: " + tile.desc)
        print("Candidates:")
        for (placed_tile, L) in candidate_placements:
            print('nb_contact_segments={}, pos=({}, {}), r={}'.format(L, placed_tile.pos[0], placed_tile.pos[1], placed_tile.r))
    return candidate_placements[0][0]


def find_placement(tile, border):
    candidate_placements = []
    tagged = set()
    for idx in range(len(border)):
        point = border.points[idx]
        edge = border.get_edge(idx)
        tile_boundary = boundary.from_edge(point, edge, Orientation.COUNTERCLOCKWISE, Domain.EXTERIOR)
        (i, j) = tile_boundary.bottomleft()
        if (i, j) not in tagged:
            tagged.add((i, j))
            common_segments = border.common_segments(boundary.get_tile(i, j))
            if len(common_segments) == 1:
                (border_idx, tile_idx, L) = common_segments[0]
                border_labels = border.slice(border_idx, border_idx + L).labels
                border_labels.reverse()
                for r in range(4):
                    placed_tile = PlacedTile(tile, i, j, r)
                    tile_labels = placed_tile.get_boundary().slice(tile_idx, tile_idx + L).labels
                    if tile_labels == border_labels:
                        candidate_placements.append((placed_tile, L))
    if len(candidate_placements) > 0:
        return select_tile_placement(candidate_placements)
    else:
        warn('Could not placed tile')
        return None


def shuffle_tileset(tileset):
    tiles = list(itertools.chain.from_iterable([list(itertools.repeat(tile, tile.remaining_nb)) for tile in tileset]))
    random.shuffle(tiles)
    return tiles


def main():
    parser = argparse.ArgumentParser(description='Display a randomized Carcassonne map')
    parser.add_argument('files', metavar='FILE', nargs='*', help='Tile description file (JSON format)')
    parser.add_argument('-n', metavar='N', type=int, dest='max_tiles', default = 0, help='Number of tiles to display (Default: The whole tileset)')
    parser.add_argument('-z', '--zoom-factor', metavar='Z', type=float, dest='zoom_factor', default = 1.0, help='Initial zoom factor (Default: 1.0)')
    parser.add_argument('-d', '--draw-all', dest='draw_all', action='store_true', help='Draw all tiles')
    args = parser.parse_args()

    # Load tileset (JSON files)
    tileset = []
    start_tile_idx = -1
    for json_file in args.files:
        try:
            fp = open(json_file, 'r')
            tileset_json = json.load(fp)
            assert 'tiles' in tileset_json.keys()
            cumul = 0
            for tile_json in tileset_json['tiles']:
                tileset.append(Tile(tile_json, os.path.dirname(json_file)))
                cumul += tileset[-1].remaining_nb
                if tileset[-1].remaining_nb == 0:
                    del tileset[-1:]
                elif 'start' in tileset[-1].tags:
                    start_tile_idx = len(tileset) - 1
        finally:
            print('Loaded {} tiles from file {}.'.format(cumul, json_file))
            fp.close()

    try:
        # Open display
        display = graphics.GridDisplay(1500, 1000)

        # Load tiles, draw missing ones
        tile_size = 0
        if not args.draw_all:
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
        display.set_tile_size(tile_size)

        # Place start tile, initialize boundary
        border = Boundary()
        z = args.zoom_factor
        if start_tile_idx < 0:
            start_tile_idx = random.randrange(len(tileset))
        assert tileset[start_tile_idx].remaining_nb > 0
        start_tile = PlacedTile(tileset[start_tile_idx], 0, 0, 0)
        border.merge(start_tile.get_boundary())
        start_tile.draw(display)
        tileset[start_tile_idx].remaining_nb -= 1
        display.update(z, 100)

        # Place random tiles. The map must grow!
        total_nb_tiles_placed = nb_tiles_placed = 1
        first_tileset = True
        while (args.max_tiles == 0 and first_tileset) or total_nb_tiles_placed < args.max_tiles:
            first_tileset = False
            tiles_to_place = shuffle_tileset(tileset)
            while len(tiles_to_place) > 0 and nb_tiles_placed > 0 and (args.max_tiles == 0 or total_nb_tiles_placed < args.max_tiles):
                nb_tiles_placed = 0
                tiles_not_placed = []
                for tile in tiles_to_place:
                    if args.max_tiles > 0 and total_nb_tiles_placed + nb_tiles_placed >= args.max_tiles:
                        break
                    placed_tile = find_placement(tile, border)
                    if placed_tile is not None:
                        border.merge(placed_tile.get_boundary())
                        placed_tile.draw(display)
                        nb_tiles_placed += 1
                    else:
                        tiles_not_placed.append(tile)
                total_nb_tiles_placed += nb_tiles_placed
                print('total_nb_tiles_placed: {} (+{})'.format(total_nb_tiles_placed, nb_tiles_placed))
                display.update(z, 100)
                tiles_to_place = tiles_not_placed

        input("Press Enter to exit...")

    finally:
        display.quit()

    return 0


if __name__ == "__main__":
    main()
