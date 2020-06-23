import os.path
import pygame
import sys


TILE_COLORS = {
    'F': pygame.Color(153, 187,  25),       # Field
    'T': pygame.Color(167, 122,  71),       # Town
    'P': pygame.Color(234, 234, 209),       # Path
    'R': pygame.Color(0,   0,   200),       # River
}
UNKNOWN_DESC_COLOR = pygame.Color(255, 0,   200)


def warn(msg):
    print("Warning: " + msg)


def error(msg):
    print("Error: " + msg)
    exit(-1)


def path_polygon(x0, y0, x1, y1, xc, yc, width_percent):
    alpha = width_percent / 200
    return [
        ((0.5 + alpha) * x0  + (0.5 - alpha) * x1, (0.5 + alpha) * y0 + (0.5 - alpha) * y1),
        (xc + 2 * alpha * (x0 - xc), yc + 2 * alpha * (y0 - yc)),
        (xc, yc),
        (xc + 2 * alpha * (x1 - xc), yc + 2 * alpha * (y1 - yc)),
        ((0.5 - alpha) * x0  + (0.5 + alpha) * x1, (0.5 - alpha) * y0 + (0.5 + alpha) * y1)
    ]


def draw_tile(desc, size):
    """
    Draw a simplified tile surface based on the tile description.
    For instance : 'FPTP' means Fied, Path, Town and Path sides, rotating counter-clockwise
    """
    assert GridDisplay.is_init()
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
    return tile


def load_image(img_path):
    assert GridDisplay.is_init()
    img = None
    if img_path:
        try:
            img = pygame.image.load(img_path).convert()
            assert img.get_height() == img.get_width()
        except:
            warn("Could not load image: " + img_path)
    return img


class MustQuit(Exception):
    """Raised when the user exits the graphics window"""


class GridDisplay:
    def __init__(self, w, h):
        if not pygame.get_init():
            pygame.init()
        if (w, h) == (0, 0):
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.screen = pygame.display.set_mode((w, h))
        self.tile_size = 0
        self.current_zoom = 0.0
        self.tiles = {}
        self.center = self.screen.get_rect().center
        self.dbg_calls_to_set_tile = 0
        self.dbg_calls_to_update = 0


    @staticmethod
    def is_init():
        return pygame.get_init()


    def set_tile_size(self, tile_size):
        self.tile_size = tile_size


    def __blit(self, rotated_img, i, j):
        assert self.tile_size > 0
        target_size = round(self.tile_size * self.current_zoom)
        scaled_img = pygame.transform.smoothscale(rotated_img, (target_size, target_size))
        pos = scaled_img.get_rect().move(self.center).move((i - 0.5) * target_size, (-0.5 - j) * target_size)
        self.screen.blit(scaled_img, pos)


    def set_tile(self, img, i, j, r):
        assert self.tile_size > 0
        assert img.get_height() == self.tile_size
        assert img.get_width() == self.tile_size
        rotated_img = pygame.transform.rotate(img, r * 90)
        self.tiles[(i, j)] = rotated_img
        self.__blit(rotated_img, i, j)
        self.dbg_calls_to_set_tile += 1


    def reset_tile(self, i, j):
        del tiles[(i, j)]
        assert self.tile_size > 0
        black_tile = pygame.Surface((self.tile_size, self.tile_size))
        black_tile.fill(pygame.Color(0, 0, 0))
        self.__blit(black_tile, i, j)


    def check_event_queue(self, wait_ms = 0):
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
        assert zoom > 0.0
        if zoom != self.current_zoom:
            self.screen.fill(pygame.Color(0, 0, 0))
            self.current_zoom = zoom
            for coord, img in self.tiles.items():
                self.__blit(img, coord[0], coord[1])
        pygame.display.flip()
        sys.stdout.flush()
        self.dbg_calls_to_update += 1
        self.check_event_queue(wait_ms)


    def quit(self):
        print('Nb calls to set_tile: {}', format(self.dbg_calls_to_set_tile))
        print('Nb calls to update:   {}', format(self.dbg_calls_to_update))
        pygame.quit()
