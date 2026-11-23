#!/usr/bin/env python3
"""Summarise a WAV written by the host runner: level per second and overall statistics.

Used to check audio output without listening: silence, clipping and whether the
left and right channels differ.
"""
import struct
import sys
import wave


def main():
    with wave.open(sys.argv[1], "rb") as w:
        rate, n = w.getframerate(), w.getnframes()
        data = struct.unpack(f"<{n * 2}h", w.readframes(n))
    left, right = data[0::2], data[1::2]
    print(f"{n} frames, {rate} Hz, {n / rate:.1f} s")
    if not n:
        return
    peak = max(max(map(abs, left)), max(map(abs, right)))
    clipped = sum(1 for v in data if abs(v) >= 32767)
    differ = sum(1 for a, b in zip(left, right) if a != b)
    print(f"peak {peak}, clipped samples {clipped}, frames where left != right {differ}")
    bars = []
    for start in range(0, n, rate):
        chunk = left[start:start + rate]
        rms = (sum(v * v for v in chunk) / len(chunk)) ** 0.5
        crossings = sum(1 for a, b in zip(chunk, chunk[1:]) if (a < 0) != (b < 0))
        bars.append(f"{int(rms):5d}/{crossings * rate // (2 * len(chunk)):5d}")
    print("per second, left RMS / mean frequency by zero crossings (Hz):")
    for i in range(0, len(bars), 8):
        print("  " + "  ".join(bars[i:i + 8]))


if __name__ == "__main__":
    main()
