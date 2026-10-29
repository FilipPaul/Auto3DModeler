"""The app's icon (an isometric cube, the tray icon's too: auto3d/launcher.py) -> an .ico with the Windows sizes.

usage:  py tools/build/icon.py build/stage/auto3d.ico      (needs Pillow; tools/build/build.py runs it)
"""
import sys

from PIL import Image, ImageDraw


def cube(size=256):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    g = ImageDraw.Draw(img)
    s = size / 64
    pts = lambda *p: [(x * s, y * s) for x, y in p]
    g.polygon(pts((32, 4), (60, 18), (32, 32), (4, 18)), fill=(96, 165, 250))
    g.polygon(pts((4, 18), (32, 32), (32, 60), (4, 46)), fill=(37, 99, 235))
    g.polygon(pts((60, 18), (32, 32), (32, 60), (60, 46)), fill=(29, 78, 216))
    return img


if __name__ == "__main__":
    cube().save(sys.argv[1], sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
