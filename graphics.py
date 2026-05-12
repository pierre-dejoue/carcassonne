"""
Display the map on the screen

 - The backend is pygame-ce
"""
# SPDX-License-Identifier: MIT
# Copyright (c) 2020 Pierre DEJOUE
import logging
import os
import sys
from collections import defaultdict

# Silent pygame import
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "True"
import pygame

logger = logging.getLogger(__name__)

GRAPHICS_BACKEND='pygame-ce'
TILE_COLORS = {
    'F': pygame.Color(153, 187,  25),       # Field
    'T': pygame.Color(167, 122,  71),       # Town
    'P': pygame.Color(234, 234, 209),       # Path
    'R': pygame.Color(0,   0,   200),       # River
}
UNKNOWN_DESC_COLOR = pygame.Color(255, 0, 0)
FULLSCREEN_KEYS = [pygame.K_F11, pygame.K_f]
DEFAULT_ZOOM_FACTOR = 1.1
DEFAULT_PAN_STEP = 50.0      # in Pixels


def init() -> None:
    pygame.init()
    logger.debug('Init %s %s (SDL %d.%d.%d, Python %d.%d.%d)',
        GRAPHICS_BACKEND,
        pygame.version.ver,
        *pygame.version.SDL,
        *sys.version_info[0:3]
    )


def is_init() -> bool:
    return pygame.get_init()


def quit_window() -> None:
    pygame.quit()


class Image:
    """A generic image"""

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
    if not img_path:
        return None
    return Image(pygame.image.load(img_path))


def path_polygon(x0, y0, x1, y1, xc, yc, width_percent):
    alpha = width_percent / 200
    return [
        ((0.5 + alpha) * x0 + (0.5 - alpha) * x1, (0.5 + alpha) * y0 + (0.5 - alpha) * y1),
        (xc + 2 * alpha * (x0 - xc), yc + 2 * alpha * (y0 - yc)),
        (xc, yc),
        (xc + 2 * alpha * (x1 - xc), yc + 2 * alpha * (y1 - yc)),
        ((0.5 - alpha) * x0 + (0.5 + alpha) * x1, (0.5 - alpha) * y0 + (0.5 + alpha) * y1)
    ]


def draw_uniform_tile(color: tuple[int, int, int], size: int):
    assert is_init()
    tile = pygame.Surface((size, size))
    tile.fill(pygame.Color(color))
    return Image(tile)


def draw_game_tile(desc: str, size: int) -> Image:
    """
    Draw a simplified tile surface based on the tile description.
    For instance: 'FPTP' means Fied, Path, Town and Path sides, rotating counter-clockwise
    """
    assert is_init()
    assert len(desc) == 4               # A tile has four sides
    tile = pygame.Surface((size, size))
    rect = tile.get_rect()
    tile.fill(TILE_COLORS['F'])
    corners = [rect.bottomleft, rect.bottomright, rect.topright, rect.topleft]
    for idx, quarter_desc in enumerate(desc):
        x0, y0 = corners[idx % 4]
        x1, y1 = corners[(idx + 1) % 4]
        xc, yc = rect.center
        if quarter_desc == 'T' or quarter_desc not in TILE_COLORS:
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
        color = TILE_COLORS[quarter_desc] if quarter_desc in TILE_COLORS else UNKNOWN_DESC_COLOR
        if len(polygon) > 0:
            pygame.draw.polygon(tile, color, polygon)
    return Image(tile)


class MustQuit(Exception):
    """Raised when the user exits the graphics window"""


def format_32bit_flag(i):
    return '0x{:08X}'.format(i & 0xFFFFFFFF)


class GridDisplay:
    """A pygame display used to show a grid-type object"""

    def __init__(self, w: int, h: int, fullscreen: bool, tile_size: int,
                 *, window_caption: str = '',
                    initial_zoom: float = 1.0, zoom_factor: float = DEFAULT_ZOOM_FACTOR,
                    pan_step: float = DEFAULT_PAN_STEP):
        assert tile_size > 0
        if not is_init():
            raise RuntimeError('Call graphics.init() prior to instantiating the grid display')
        self.w = w
        self.h = h
        self.fullscreen = fullscreen
        self.screen: pygame.Surface = self._init_screen()
        if window_caption:
            pygame.display.set_caption(window_caption)
        self.center: tuple[int, int] = self.screen.get_rect().center
        self.tile_size = tile_size
        self.initial_zoom = initial_zoom
        self.current_zoom = initial_zoom
        self.zoom_factor = zoom_factor
        self.pan_offset: tuple[float, float] = (0.0, 0.0)
        self.pan_step = pan_step
        self.tiles: dict[tuple[int, int], pygame.Surface] = {}
        self.bottomleft: tuple[int, int] = (0, 0)
        self.topright: tuple[int, int] = (0, 0)
        self.dbg_counters: defaultdict[str, int] = defaultdict(int)
        self.dbg_info: dict[str, object] = {}
        self.dbg_info['display_flags'] = format_32bit_flag(self.screen.get_flags())
        self.dbg_info['display_bitsize'] = self.screen.get_bitsize()
        self.dbg_info['display_height'] = self.screen.get_height()
        self.dbg_info['display_width'] = self.screen.get_width()
        self.dbg_info['tile_size'] = self.tile_size
        self.dbg_info['current_zoom'] = self.current_zoom


    def _init_screen(self):
        if self.fullscreen:
            flags = pygame.FULLSCREEN | pygame.HWSURFACE | pygame.DOUBLEBUF
            return pygame.display.set_mode((0, 0), flags=flags)
        return pygame.display.set_mode((self.w, self.h))


    def _redraw_screen(self):
        self.dbg_counters['calls_to__redraw_screen'] += 1
        self.screen.fill(pygame.Color(0, 0, 0))
        for coord, img in self.tiles.items():
            self._blit(img, coord[0], coord[1])
        pygame.display.flip()


    def _blit(self, rotated_img, i, j):
        self.dbg_counters['calls_to__blit'] += 1
        target_size = round(self.tile_size * self.current_zoom)
        scaled_img = pygame.transform.smoothscale(rotated_img, (target_size, target_size))
        pos = scaled_img.get_rect().move(self.center).move(self.pan_offset).move((-0.5 + i) * target_size, (-0.5 - j) * target_size).topleft
        self.screen.blit(scaled_img, pos)


    def set_tile(self, image: Image, i: int, j: int, r: int = 0):
        self.dbg_counters['calls_to_set_tile'] += 1
        self.dbg_info['last_set_tile'] = repr((i, j, r))
        assert image.height() == self.tile_size
        assert image.width() == self.tile_size
        rotated_img = pygame.transform.rotate(image.converted_img(), r * 90)
        self.tiles[(i, j)] = rotated_img
        self._blit(rotated_img, i, j)
        if i < self.bottomleft[0]:
            self.bottomleft = (i, self.bottomleft[1])
        elif i > self.topright[0]:
            self.topright = (i, self.topright[1])
        if j < self.bottomleft[1]:
            self.bottomleft = (self.bottomleft[0], j)
        elif j > self.topright[1]:
            self.topright = (self.topright[0], j)


    def reset_tile(self, i, j):
        self.dbg_counters['calls_to_reset_tile'] += 1
        self.dbg_info['last_reset_tile'] = repr((i, j, 0))
        del self.tiles[(i, j)]
        black_tile = pygame.Surface((self.tile_size, self.tile_size))
        black_tile.fill(pygame.Color(0, 0, 0))
        self._blit(black_tile, i, j)


    @staticmethod
    def list_ui_controls():
        return [
            "Press 'F11' or 'F' to toggle fullscreen",
            "Press the arrow keys to pan",
            "Press 'PAGEUP' and 'PAGEDOWN' to zoom in and out",
            "Press 'R' to reset the view to its initial state",
            "Press 'ESCAPE' in the graphics window to quit",
        ]


    def _handle_key_events(self, key) -> bool:
        needs_redraw = False
        if key == pygame.K_ESCAPE:
            raise MustQuit()
        if key in FULLSCREEN_KEYS:
            self.toggle_fullscreen()
        elif key == pygame.K_PAGEUP:
            self.current_zoom *= self.zoom_factor
            self.dbg_info['current_zoom'] = self.current_zoom
            self.pan_offset = (
                self.pan_offset[0] * self.zoom_factor,
                self.pan_offset[1] * self.zoom_factor)
            needs_redraw = True
        elif key == pygame.K_PAGEDOWN:
            self.current_zoom /= self.zoom_factor
            self.dbg_info['current_zoom'] = self.current_zoom
            self.pan_offset = (
                self.pan_offset[0] / self.zoom_factor,
                self.pan_offset[1] / self.zoom_factor)
            needs_redraw = True
        elif key == pygame.K_LEFT:
            self.pan_offset = (self.pan_offset[0] + self.pan_step, self.pan_offset[1])
            needs_redraw = True
        elif key == pygame.K_RIGHT:
            self.pan_offset = (self.pan_offset[0] - self.pan_step, self.pan_offset[1])
            needs_redraw = True
        elif key == pygame.K_UP:
            self.pan_offset = (self.pan_offset[0], self.pan_offset[1] + self.pan_step)
            needs_redraw = True
        elif key == pygame.K_DOWN:
            self.pan_offset = (self.pan_offset[0], self.pan_offset[1] - self.pan_step)
            needs_redraw = True
        elif key == pygame.K_r:
            self.pan_offset = (0.0, 0.0)
            self.current_zoom = self.initial_zoom
            needs_redraw = True
        return needs_redraw


    def check_event_queue(self, needs_redraw: bool = False, wait_ms: int = 0) -> None:
        """Check the event queue, redraw the display if needed"""
        self.dbg_counters['calls_to_check_event_queue'] += 1
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                raise MustQuit()
            if event.type == pygame.KEYDOWN:
                needs_redraw |= self._handle_key_events(event.key)
        if needs_redraw:
            self._redraw_screen()
        if wait_ms > 0:
            pygame.time.wait(wait_ms)


    def update(self, wait_ms: int = 0) -> None:
        """Force redrawing the display, and check the event queue"""
        self.dbg_counters['calls_to_update'] += 1
        self.check_event_queue(needs_redraw=True, wait_ms=wait_ms)


    def toggle_fullscreen(self):
        self.fullscreen = not (self.screen.get_flags() & pygame.FULLSCREEN)
        self.screen = self._init_screen()
        self.center = self.screen.get_rect().center
        self._redraw_screen()


    def get_debug_info(self):
        dbg = {
            'library_name': 'pygame',
            'library_version': pygame.version.ver,
        }
        for k, v in self.dbg_info.items():
            dbg[k] = v
        for k, v in self.dbg_counters.items():
            dbg[k] = v
        return sorted(dbg.items())


    def take_screenshot(self, img_path = 'screenshot.jpg'):
        """Screenshot of the display"""
        pygame.image.save(self.screen, img_path)


    def dump_to_img(self, img_path = 'dump.bmp', scale = 1.0):
        """Dump the grid to an image"""
        width = 1 + self.topright[0] - self.bottomleft[0]
        height = 1 + self.topright[1] - self.bottomleft[1]
        target_tile_size = round(scale * self.tile_size)
        dump_surf = pygame.Surface((width * target_tile_size, height * target_tile_size))
        dump_surf.fill(pygame.Color(0, 0, 0))
        for coord, img in self.tiles.items():
            topleft = (target_tile_size * (coord[0] - self.bottomleft[0]), target_tile_size * (self.topright[1] - coord[1]))
            scaled_img = pygame.transform.smoothscale(img, (target_tile_size, target_tile_size))
            dump_surf.blit(scaled_img, topleft)
        pygame.image.save(dump_surf, img_path)
