#!/usr/bin/env python


import argparse
import boundary
import graphics
import json
import os.path
from boundary import Boundary
from collections import deque


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
        self.max_nb = json_obj['cardinality'] if 'cardinality' in json_obj.keys() else 1
        self.remaining = self.max_nb
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


    def rotate(self, r):
        self.r = r
        self.desc = deque(self.tile.desc)
        self.desc.rotate(r) # right rotate


    def draw(self, display):
        assert self.tile.img is not None
        display.set_tile(self.tile.img, self.pos[0], self.pos[1], self.r)


    def get_boundary(self):
        return boundary.get_tile(self.pos[0], self.pos[1], self.desc)


def main():
    parser = argparse.ArgumentParser(description='Display a randomized Carcassonne map')
    parser.add_argument('files', metavar='FILE', nargs='*', help='Tile description file (JSON format)')
    parser.add_argument('-n', metavar='N', dest='max_tiles', default = 0, help='Number of tiles to display (Default: The whole tileset)')
    parser.add_argument('-z', '--zoom-factor', metavar='Z', type=float, dest='zoom_factor', default = 1.0, help='Initial zoom factor (Default: 1.0)')
    args = parser.parse_args()

    # Load tileset (JSON files)
    tileset = []
    start_tile_idx = -1
    for json_file in args.files:
        try:
            fp = open(json_file, 'r')
            tileset_json = json.load(fp)
            assert 'tiles' in tileset_json.keys()
            for tile_json in tileset_json['tiles']:
                tileset.append(Tile(tile_json, os.path.dirname(json_file)))
                if 'start' in tileset[-1].tags:
                    start_tile_idx = len(tileset) - 1
        finally:
            fp.close()

    # Display
    try:
        display = graphics.GridDisplay(1024, 720)

        # Load tiles, draw missing ones
        tile_size = 0
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
        if start_tile_idx >= 0:
            start_tile = PlacedTile(tileset[start_tile_idx], 0, 0, 0)
            border.merge(start_tile.get_boundary())
            start_tile.draw(display)
            display.update(z, 100)
        print(border)

        input("Press Enter to exit...")

    finally:
        graphics.GridDisplay.quit()

    return 0


if __name__ == "__main__":
    main()
