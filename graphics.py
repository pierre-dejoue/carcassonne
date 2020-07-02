import os.path
import pygame
import sys
from collections import defaultdict


TILE_COLORS = {
    'F': pygame.Color(153, 187,  25),       # Field
    'T': pygame.Color(167, 122,  71),       # Town
    'P': pygame.Color(234, 234, 209),       # Path
    'R': pygame.Color(0,   0,   200),       # River
}
UNKNOWN_DESC_COLOR = pygame.Color(255, 0, 0)


def init():
    pygame.init()


def is_init():
    return pygame.get_init()


def quit():
    pygame.quit()


class Image:
    def __init__(self, img):
        assert img is not None
        self.img = img
        self.converted = False


    def converted_img(self):
        if not self.converted:
            self.img = self.img.convert()
            self.converted = True
        return self.img


    def height(self):
        return self.img.get_height()


    def width(self):
        return self.img.get_width()


def load_image(img_path):
    """Load an image file. This function might throw."""
    assert is_init()
    if img_path:
        return Image(pygame.image.load(img_path))
    else:
        return None


def path_polygon(x0, y0, x1, y1, xc, yc, width_percent):
    alpha = width_percent / 200
    return [
        ((0.5 + alpha) * x0  + (0.5 - alpha) * x1, (0.5 + alpha) * y0 + (0.5 - alpha) * y1),
        (xc + 2 * alpha * (x0 - xc), yc + 2 * alpha * (y0 - yc)),
        (xc, yc),
        (xc + 2 * alpha * (x1 - xc), yc + 2 * alpha * (y1 - yc)),
        ((0.5 - alpha) * x0  + (0.5 + alpha) * x1, (0.5 - alpha) * y0 + (0.5 + alpha) * y1)
    ]


def draw_uniform_tile(color, size):
    (r, g, b) = color
    assert is_init()
    tile = pygame.Surface((size, size))
    tile.fill(pygame.Color(r, g, b))
    return Image(tile)


def draw_game_tile(desc, size):
    """
    Draw a simplified tile surface based on the tile description.
    For instance : 'FPTP' means Fied, Path, Town and Path sides, rotating counter-clockwise
    """
    assert is_init()
    assert len(desc) == 4               # A tile has four sides
    tile = pygame.Surface((size, size))
    rect = tile.get_rect()
    tile.fill(TILE_COLORS['F'])
    corners = [rect.bottomleft, rect.bottomright, rect.topright, rect.topleft]
    idx = 0
    for quarter_desc in desc:
        x0, y0 = corners[idx % 4]
        x1, y1 = corners[(idx + 1) % 4]
        xc, yc = rect.center
        if quarter_desc == 'T' or quarter_desc not in TILE_COLORS.keys():
            polygon = [
                (x0, y0),
                (xc, yc),
                (x1, y1)
            ]
        elif quarter_desc == 'P':
            polygon = path_polygon(x0, y0, x1, y1, xc, yc, 5)
        elif quarter_desc == 'R':
            polygon = path_polygon(x0, y0, x1, y1, xc, yc, 15)
        else:
            polygon = []
        color = TILE_COLORS[quarter_desc] if quarter_desc in TILE_COLORS.keys() else UNKNOWN_DESC_COLOR
        if len(polygon) > 0:
            pygame.draw.polygon(tile, color, polygon)
        idx = idx + 1
    return Image(tile)


class MustQuit(Exception):
    """Raised when the user exits the graphics window"""


def format_32bit_flag(i):
    return '0x{:08X}'.format(i & 0xFFFFFFFF)


class GridDisplay:
    def __init__(self, w, h, tile_size):
        if not is_init():
            raise RuntimeError('Call graphics.init() prior to instantiating the grid display')
        if (w, h) == (0, 0):
            self.screen = pygame.display.set_mode((0, 0), flags = pygame.FULLSCREEN | pygame.HWSURFACE | pygame.DOUBLEBUF)
        else:
            self.screen = pygame.display.set_mode((w, h))
        assert tile_size > 0
        self.tile_size = tile_size
        self.current_zoom = 0.0
        self.tiles = {}
        self.center = self.screen.get_rect().center
        self.dbg_counters = defaultdict(int)
        self.dbg_info = {}
        self.dbg_info['display_flags'] = format_32bit_flag(self.screen.get_flags())
        self.dbg_info['display_bitsize'] = self.screen.get_bitsize()
        self.dbg_info['display_height'] = self.screen.get_height()
        self.dbg_info['display_width'] = self.screen.get_width()
        self.dbg_info['tile_size'] = self.tile_size
        self.dbg_info['current_zoom'] = self.current_zoom


    def __blit(self, rotated_img, i, j):
        self.dbg_counters['calls_to___blit'] += 1
        target_size = round(self.tile_size * self.current_zoom)
        scaled_img = pygame.transform.smoothscale(rotated_img, (target_size, target_size))
        pos = scaled_img.get_rect().move(self.center).move((i - 0.5) * target_size, (-0.5 - j) * target_size)
        self.screen.blit(scaled_img, pos)


    def set_tile(self, image, i, j, r = 0):
        self.dbg_counters['calls_to_set_tile'] += 1
        self.dbg_info['last_set_tile'] = repr((i, j, r))
        assert image.height() == self.tile_size
        assert image.width() == self.tile_size
        rotated_img = pygame.transform.rotate(image.converted_img(), r * 90)
        self.tiles[(i, j)] = rotated_img
        self.__blit(rotated_img, i, j)


    def reset_tile(self, i, j):
        self.dbg_counters['calls_to_reset_tile'] += 1
        self.dbg_info['last_reset_tile'] = repr((i, j, r))
        del tiles[(i, j)]
        black_tile = pygame.Surface((self.tile_size, self.tile_size))
        black_tile.fill(pygame.Color(0, 0, 0))
        self.__blit(black_tile, i, j)


    def check_event_queue(self, wait_ms = 0):
        self.dbg_counters['calls_to_check_event_queue'] += 1
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                raise MustQuit()
            elif event.type == pygame.KEYUP and event.key == pygame.K_ESCAPE:
                raise MustQuit()
            else:
                pass
        if wait_ms > 0:
            pygame.time.wait(wait_ms)


    def update(self, zoom = 1.0, wait_ms = 0):
        self.dbg_counters['calls_to_update'] += 1
        assert zoom > 0.0
        if zoom != self.current_zoom:
            self.screen.fill(pygame.Color(0, 0, 0))
            self.current_zoom = zoom
            self.dbg_info['current_zoom'] = self.current_zoom
            for coord, img in self.tiles.items():
                self.__blit(img, coord[0], coord[1])
        pygame.display.flip()
        sys.stdout.flush()
        self.check_event_queue(wait_ms)


    def get_debug_info(self):
        dbg = { 'library_name': 'pygame', 'library_version': pygame.version.ver }
        for k, v in self.dbg_info.items():
            dbg[k] = v
        for k, v in self.dbg_counters.items():
            dbg[k] = v
        return sorted(dbg.items())

    def take_screenshot(self, img_path = 'screenshot.jpg'):
        pygame.image.save(self.screen, img_path)
