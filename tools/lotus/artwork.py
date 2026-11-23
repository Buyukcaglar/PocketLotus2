#!/usr/bin/env python3
"""Analogue Pocket artwork: convert between the Pocket's image files and PNG.

The Pocket shows a platform image (Platforms/_images/<platform>.bin, 521x165)
and a core icon (Cores/<core>/icon.bin, 36x36). Both are headerless, two bytes
a pixel (the first is the grey level, the second zero), stored rotated a
quarter turn anticlockwise.

  artwork.py topng  FILE.bin W H OUT.png           decode a Pocket image
  artwork.py tobin  IMAGE.png|.ppm OUT.bin W H [--top N] [--height N]
                                                    make a Pocket image from a
                                                    picture: scaled to width W,
                                                    a band from line --top
  artwork.py preview IMAGE.png|.ppm OUT.png W H [--top N] [--height N]
                                                    the same, as a PNG to view
  --whole (tobin, preview): instead of a band, the picture's whole non-black
  content, scaled with its aspect kept to fit W x H, centred on black
Only the standard library is used. Pictures made from game screens are game
content: keep them out of published files. The exception is the platform art
(docs/images), published by the author's decision.
"""
import struct
import sys
import zlib


# ---- PNG and PPM, minimal ------------------------------------------------------

def write_png(path, w, h, pixels, channels=1):
    """pixels: bytes, rows top to bottom, 1 (grey) or 3 (RGB) bytes a pixel."""
    stride = w * channels
    raw = b"".join(b"\0" + pixels[y * stride:(y + 1) * stride] for y in range(h))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))
    colour = 0 if channels == 1 else 2
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, colour, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def read_ppm(path):
    data = open(path, "rb").read()
    parts, i = [], 0
    while len(parts) < 4:
        while data[i:i + 1].isspace():
            i += 1
        if data[i:i + 1] == b"#":
            i = data.index(b"\n", i)
            continue
        j = i
        while not data[j:j + 1].isspace():
            j += 1
        parts.append(data[i:j])
        i = j
    if parts[0] != b"P6":
        raise SystemExit(f"{path}: not a binary PPM")
    w, h = int(parts[1]), int(parts[2])
    return w, h, data[i + 1:i + 1 + w * h * 3]


def read_png(path):
    data = open(path, "rb").read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise SystemExit(f"{path}: not a PNG")
    pos, idat, w = 8, b"", 0
    while pos < len(data):
        n, t = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        if t == b"IHDR":
            w, h, depth, colour, _, _, interlace = struct.unpack(">IIBBBBB", body)
            if depth != 8 or colour not in (0, 2, 6) or interlace:
                raise SystemExit(f"{path}: only 8-bit grey, RGB or RGBA PNGs without interlace")
            ch = {0: 1, 2: 3, 6: 4}[colour]
        elif t == b"IDAT":
            idat += body
        pos += 12 + n
    raw, stride, out, prev = zlib.decompress(idat), w * ch, bytearray(), bytearray(w * ch)
    for y in range(h):
        ft, line = raw[y * (stride + 1)], bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for x in range(stride):
            a = line[x - ch] if x >= ch else 0
            b, c = prev[x], prev[x - ch] if x >= ch else 0
            if ft == 1: line[x] = (line[x] + a) & 255
            elif ft == 2: line[x] = (line[x] + b) & 255
            elif ft == 3: line[x] = (line[x] + (a + b) // 2) & 255
            elif ft == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        out += line
        prev = line
    rgb = bytearray()
    for i in range(w * h):
        px = out[i * ch:(i + 1) * ch]
        rgb += bytes(px[:3]) if ch >= 3 else bytes([px[0]] * 3)
    return w, h, bytes(rgb)


def read_picture(path):
    return read_ppm(path) if path.lower().endswith(".ppm") else read_png(path)


# ---- Pocket format ---------------------------------------------------------------

def pocket_decode(path, w, h):
    """Return the grey image (w x h, upright) of a Pocket .bin."""
    d = open(path, "rb").read()
    if len(d) != w * h * 2:
        raise SystemExit(f"{path}: {len(d)} bytes, expected {w * h * 2} for {w}x{h}")
    sw = h                                           # stored rotated: w rows of h pixels
    out = bytearray(w * h)
    for y in range(h):
        for x in range(w):
            out[y * w + x] = d[((w - 1 - x) * sw + y) * 2]     # stored row w-1-x, column y
    return bytes(out)


def pocket_encode(grey, w, h):
    sw = h
    out = bytearray(w * h * 2)
    for y in range(h):
        for x in range(w):
            out[((w - 1 - x) * sw + y) * 2] = grey[y * w + x]
    return bytes(out)


def fit(rgb_w, rgb_h, rgb, w, h, top=None, height=None):
    """Grey band of the picture: scaled to width w, `height` source lines from `top`."""
    if height is None:
        height = max(1, round(h * rgb_w / w))
    if top is None:
        top = max(0, (rgb_h - height) // 2)
    grey = bytearray(w * h)
    for y in range(h):
        sy0 = top + y * height / h
        sy1 = top + (y + 1) * height / h
        for x in range(w):
            sx0, sx1 = x * rgb_w / w, (x + 1) * rgb_w / w
            total = n = 0
            yy = int(sy0)
            while yy < sy1 and yy < rgb_h:
                xx = int(sx0)
                while xx < sx1 and xx < rgb_w:
                    i = (yy * rgb_w + xx) * 3
                    total += 0.299 * rgb[i] + 0.587 * rgb[i + 1] + 0.114 * rgb[i + 2]
                    n += 1
                    xx += 1
                yy += 1
            grey[y * w + x] = int(total / n) if n else 0
    return bytes(grey)


def fit_whole(rgb_w, rgb_h, rgb, w, h, margin=4, threshold=24):
    """Grey image: the picture's non-black content, scaled with its aspect kept
    to fill w x h less `margin`, centred on black."""
    def lum(i):
        return 0.299 * rgb[i] + 0.587 * rgb[i + 1] + 0.114 * rgb[i + 2]
    xs = [x for x in range(rgb_w) if any(lum((y * rgb_w + x) * 3) > threshold for y in range(rgb_h))]
    ys = [y for y in range(rgb_h) if any(lum((y * rgb_w + x) * 3) > threshold for x in range(rgb_w))]
    if not xs:
        return bytes(w * h)
    x0, x1, y0, y1 = xs[0], xs[-1] + 1, ys[0], ys[-1] + 1
    cw, ch = x1 - x0, y1 - y0
    scale = min((w - 2 * margin) / cw, (h - 2 * margin) / ch)
    ow, oh = max(1, round(cw * scale)), max(1, round(ch * scale))
    ox, oy = (w - ow) // 2, (h - oh) // 2
    grey = bytearray(w * h)
    for y in range(oh):
        sy0, sy1 = y0 + y * ch / oh, y0 + (y + 1) * ch / oh
        for x in range(ow):
            sx0, sx1 = x0 + x * cw / ow, x0 + (x + 1) * cw / ow
            # area-weighted average of the source pixels the target pixel covers
            total = area = 0.0
            yy = int(sy0)
            while yy < sy1:
                fy = min(sy1, yy + 1) - max(sy0, yy)
                xx = int(sx0)
                while xx < sx1:
                    fx = min(sx1, xx + 1) - max(sx0, xx)
                    total += lum((yy * rgb_w + xx) * 3) * fx * fy
                    area += fx * fy
                    xx += 1
                yy += 1
            grey[(oy + y) * w + ox + x] = min(255, round(total / area))
    return bytes(grey)


def option(args, name):
    if name in args:
        i = args.index(name)
        value = int(args[i + 1])
        del args[i:i + 2]
        return value
    return None


def main():
    a = sys.argv[1:]
    if not a:
        raise SystemExit(__doc__)
    cmd = a.pop(0)
    whole = "--whole" in a
    if whole:
        a.remove("--whole")
    top, height = option(a, "--top"), option(a, "--height")
    if cmd == "topng" and len(a) == 4:
        w, h = int(a[1]), int(a[2])
        write_png(a[3], w, h, pocket_decode(a[0], w, h))
    elif cmd in ("tobin", "preview") and len(a) == 4:
        pw, ph, rgb = read_picture(a[0])
        w, h = int(a[2]), int(a[3])
        grey = fit_whole(pw, ph, rgb, w, h) if whole else fit(pw, ph, rgb, w, h, top, height)
        if cmd == "tobin":
            open(a[1], "wb").write(pocket_encode(grey, w, h))
        else:
            write_png(a[1], w, h, grey)
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
