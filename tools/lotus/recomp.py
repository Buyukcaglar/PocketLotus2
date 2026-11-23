#!/usr/bin/env python3
"""Static recompiler: translate the expanded Lotus ARM2 program to C.

Inputs (all under build/lotus, produced by the host runner):
  game_image.bin   expanded program, base &8000
  coverage.bin     one byte per word from &8000: bit0 executed, bit1 written at run time
  musmod2.bin      the game's music module as loaded at &1A00000, with coverage_mus.bin
  leaders_extra.txt  optional, one hex address per line: indirect-jump targets found at
                     run time. leaders_seen.txt from a translated run is merged into it.

Output: build/lotus/gen/lotus_gen.c (derived game content, never published).

Model. Every translated instruction mirrors port/core/arm26.c exactly, including
cycle accounting, so that translated code and the interpreter can be compared
state for state. A slice may end only at a block leader. Code is grouped into
4 KiB chunks, one C function each; guest registers and flags live in locals
inside a chunk and are synchronised with the CPU structure at chunk exit and
around interpreter calls. Anything unusual is delegated to the interpreter one
instruction at a time through INTERP().
"""
import argparse
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build/lotus"
BASE = 0x8000
MUS_BASE = 0x01A00000
CHUNK_SHIFT = 12
PC_MASK = 0x03FFFFFC

COND = [
    "fZ", "!fZ", "fC", "!fC", "fN", "!fN", "fV", "!fV",
    "(fC && !fZ)", "(!fC || fZ)", "(fN == fV)", "(fN != fV)",
    "(!fZ && fN == fV)", "(fZ || fN != fV)",
]


class Image:
    def __init__(self, data: bytes, cov: bytes, base: int = BASE):
        self.data = data
        self.cov = cov
        self.base = base
        self.end = base + len(data)

    def word(self, a: int) -> int:
        return struct.unpack_from("<I", self.data, a - self.base)[0]

    def inside(self, a: int) -> bool:
        return self.base <= a < self.end - 3

    def executed(self, a: int) -> bool:
        i = (a - self.base) >> 2
        return i < len(self.cov) and bool(self.cov[i] & 1)

    def dynamic(self, a: int) -> bool:
        """Word that was both written and executed at run time: never translate."""
        i = (a - self.base) >> 2
        return i < len(self.cov) and (self.cov[i] & 3) == 3


def is_mul(w):
    return (w & 0x0FC000F0) == 0x00000090


def is_swp(w):
    return (w & 0x0FB00FF0) == 0x01000090


def flow(a, w):
    """Return (falls_through, branch_targets, extra_seeds)."""
    cond = w >> 28
    if cond == 15:
        return True, [], []
    cls = (w >> 25) & 7
    always = cond == 14
    if cls == 5:
        off = w & 0x00FFFFFF
        if off & 0x00800000:
            off -= 0x01000000
        target = (a + 8 + (off << 2)) & PC_MASK
        if w & 0x01000000:
            return True, [target], []
        return not always, [target], []
    if cls in (0, 1):
        if cls == 0 and (is_mul(w) or is_swp(w)):
            return True, [], []
        opc = (w >> 21) & 15
        rd = (w >> 12) & 15
        if rd == 15 and not 8 <= opc <= 11:
            return not always, [], []
        return True, [], []
    if cls in (2, 3):
        if (w & 0x00100000) and ((w >> 12) & 15) == 15:
            return not always, [], []
        return True, [], []
    if cls == 4:
        if w & 0x00100000:
            if w & 0x8000:
                return not always, [], []
            return True, [], []
        if w & 0x8000:
            return True, [], [a + 12]
        return True, [], []
    if (w & 0x0F000000) == 0x0F000000:
        return True, [], []
    return False, [], []        # coprocessor / undefined


def discover(img: Image, extra):
    code = set()
    work = [a for a in range(img.base, img.end - 3, 4) if img.executed(a) and not img.dynamic(a)]
    work += [a for a in extra if img.inside(a)]
    leaders = set(a for a in extra if img.inside(a))
    while work:
        a = work.pop()
        if a in code or not img.inside(a) or img.dynamic(a):
            continue
        code.add(a)
        fall, targets, seeds = flow(a, img.word(a))
        for t in targets:
            if img.inside(t):
                leaders.add(t)
                work.append(t)
        for s in seeds:
            leaders.add(s)
            work.append(s)
        if fall:
            work.append(a + 4)
    # leaders implied by structure
    literals = set()
    for a in range(img.base, img.end - 3, 4):
        literals.add(img.word(a) & PC_MASK)
    for a in code:
        w = img.word(a)
        prev = a - 4
        if prev not in code or not flow(prev, img.word(prev))[0]:
            leaders.add(a)
        if a in literals:
            leaders.add(a)
        if a % (1 << CHUNK_SHIFT) == 0:
            leaders.add(a)                          # sequential entry into a chunk
        cond = w >> 28
        if cond != 15:
            cls = (w >> 25) & 7
            if cls == 5 and (w & 0x01000000):
                leaders.add(a + 4)                      # BL return
            if cls == 7 and (w & 0x01000000):
                leaders.add(a + 4)                      # after SWI
    leaders &= code
    return code, leaders


def idle_loop(img, code, leaders, head):
    """Recognise a wait loop that starts at leader `head`.

    A wait loop reads memory and compares until an interrupt handler changes
    something: straight-line unconditional loads and register arithmetic,
    conditional exits that are not taken, and a branch back to `head`. Nothing
    in it is stored, and no register value is carried from one pass to the
    next, so after one pass every further pass is identical. Returns the cycle
    cost of one pass and the address of the closing branch, or None.
    """
    body = []
    a = head
    while len(body) < 16:
        if a not in code or (a != head and a in leaders):
            return None
        w = img.word(a)
        cond, cls = w >> 28, (w >> 25) & 7
        if cls == 5 and not (w & 0x01000000):
            off = w & 0x00FFFFFF
            if off & 0x00800000:
                off -= 0x01000000
            target = (a + 8 + (off << 2)) & PC_MASK
            if target == head:
                body.append((a, w, "back"))
                break
            if cond >= 14:
                return None
            body.append((a, w, "exit"))
        elif cond != 14:
            return None
        elif cls in (0, 1) and not is_mul(w) and not is_swp(w):
            opc, s, rd = (w >> 21) & 15, (w >> 20) & 1, (w >> 12) & 15
            test = 8 <= opc <= 11
            if rd == 15 and not test or (test and not s) or opc in (5, 6, 7):
                return None
            if not (w >> 25) & 1 and ((w & 0x10) or ((w >> 5) & 3) == 3 and not (w >> 7) & 31):
                return None                         # register-specified shift or RRX
            body.append((a, w, "dp"))
        elif cls in (2, 3):
            if not (w & 0x00100000) or not (w & 0x01000000) or (w & 0x00200000) or ((w >> 12) & 15) == 15:
                return None
            body.append((a, w, "load"))
        else:
            return None
        a += 4
    else:
        return None
    written = set()
    for _, w, kind in body:
        if kind == "load" or (kind == "dp" and not 8 <= ((w >> 21) & 15) <= 11):
            written.add((w >> 12) & 15)
    defined, flags, cost = set(), False, 0
    for _, w, kind in body:
        reads = []
        if kind in ("exit", "back"):
            if (w >> 28) != 14 and not flags:
                return None
            cost += 3 if kind == "back" else 1
            continue
        if kind == "dp":
            if ((w >> 21) & 15) not in (13, 15):
                reads.append((w >> 16) & 15)
            if not (w >> 25) & 1:
                reads.append(w & 15)
            cost += 1
        else:
            reads.append((w >> 16) & 15)
            if (w >> 25) & 1:
                reads.append(w & 15)
            cost += 3
        if any(r in written and r not in defined for r in reads):
            return None
        if kind == "dp" and (w >> 20) & 1:
            flags = True
        if kind == "load" or not 8 <= ((w >> 21) & 15) <= 11:
            defined.add((w >> 12) & 15)
    return cost, body[-1][0]


class Emitter:
    def __init__(self, img, code, leaders):
        self.img = img
        self.code = code
        self.leaders = leaders
        self.out = []
        self.stats = {"inline": 0, "interp": 0, "idle": 0}
        self.idle_heads = {}                # loop head -> cost of one pass
        self.idle_tails = {}                # closing branch -> cost of one pass
        for head in sorted(leaders):
            found = idle_loop(img, code, leaders, head)
            if found:
                self.idle_heads[head] = found[0]
                self.idle_tails[found[1]] = found[0]
                self.stats["idle"] += 1

    def reg(self, n, cur, psr=False, ahead=8):
        if n == 15:
            v = (cur + ahead) & PC_MASK
            return f"(0x{v:08x}u | PSR())" if psr else f"0x{v:08x}u"
        return f"r{n}"

    def goto(self, target, chunk):
        if target in self.leaders and (target >> CHUNK_SHIFT) == chunk:
            return f"goto L_{target:x};"
        return f"{{ pc = 0x{target:08x}u; goto leave; }}"

    def interp(self, w, cur):
        self.stats["interp"] += 1
        return [f"INTERP(0x{w:08x}u, 0x{cur:08x}u);"]

    # ---- operand 2 -------------------------------------------------------
    def op2(self, w, cur, need_carry):
        """Return (statements, b_expr, carry_expr or None)."""
        if (w >> 25) & 1:
            rot = (w >> 7) & 0x1E
            val = w & 0xFF
            if rot:
                val = ((val >> rot) | (val << (32 - rot))) & 0xFFFFFFFF
            return [], f"0x{val:08x}u", (str(val >> 31) if rot else None)
        rm = w & 15
        typ = (w >> 5) & 3
        if w & 0x10:
            rs = (w >> 8) & 15
            if rs == 15:
                return None
            st = [f"uint32_t m = {self.reg(rm, cur, True, 12)}, co = fC;",
                  f"uint32_t b = shift_reg({typ}, m, r{rs} & 0xFF, &co);", "cyc -= 1;"]
            return st, "b", ("co" if need_carry else None)
        amt = (w >> 7) & 31
        st = [f"uint32_t m = {self.reg(rm, cur, True)};"]
        if typ == 0:
            if amt == 0:
                return st, "m", None
            return st, f"(m << {amt})", f"((m >> {32 - amt}) & 1)"
        if typ == 1:
            if amt == 0:
                return st, "0u", "(m >> 31)"
            return st, f"(m >> {amt})", f"((m >> {amt - 1}) & 1)"
        if typ == 2:
            if amt == 0:
                return st, "(uint32_t)((int32_t)m >> 31)", "(m >> 31)"
            return st, f"(uint32_t)((int32_t)m >> {amt})", f"((m >> {amt - 1}) & 1)"
        if amt == 0:
            return st, "((m >> 1) | (fC << 31))", "(m & 1)"
        return st, f"((m >> {amt}) | (m << {32 - amt}))", f"((m >> {amt - 1}) & 1)"

    # ---- instruction classes --------------------------------------------
    def data_proc(self, w, cur):
        opc = (w >> 21) & 15
        s = (w >> 20) & 1
        rn = (w >> 16) & 15
        rd = (w >> 12) & 15
        test = 8 <= opc <= 11
        regshift = not ((w >> 25) & 1) and bool(w & 0x10)
        if (test and not s) or (rd == 15 and (s or test)):
            return self.interp(w, cur)
        logical = opc in (0, 1, 8, 9, 12, 13, 14, 15)
        o = self.op2(w, cur, s and logical)
        if o is None:
            return self.interp(w, cur)
        st, b, carry = o
        a = self.reg(rn, cur, False, 12 if regshift else 8)
        lines = list(st)
        uses_a = opc not in (13, 15)
        if uses_a:
            lines.append(f"uint32_t a = {a};")
        lines.append(f"uint32_t bb = {b};")
        if s and logical and carry is not None:
            lines.append(f"uint32_t cc = {carry};")
        expr = {
            0: "a & bb", 1: "a ^ bb", 2: "a - bb", 3: "bb - a", 4: "a + bb",
            5: "a + bb + fC", 6: "a - bb - (1 - fC)", 7: "bb - a - (1 - fC)",
            8: "a & bb", 9: "a ^ bb", 10: "a - bb", 11: "a + bb",
            12: "a | bb", 13: "bb", 14: "a & ~bb", 15: "~bb",
        }[opc]
        lines.append(f"uint32_t res = {expr};")
        flags = []
        if s:
            flags.append("fN = res >> 31; fZ = (res == 0);")
            if logical:
                if carry is not None:
                    flags.append("fC = cc;")
            elif opc in (2, 10):
                flags.append("fC = (a >= bb); fV = ((a ^ bb) & (a ^ res)) >> 31;")
            elif opc == 3:
                flags.append("fC = (bb >= a); fV = ((bb ^ a) & (bb ^ res)) >> 31;")
            elif opc in (4, 11):
                flags.append("fC = (res < a); fV = (~(a ^ bb) & (a ^ res)) >> 31;")
            elif opc == 5:
                flags.append("fC = (uint32_t)(((uint64_t)a + bb + fC) >> 32); fV = (~(a ^ bb) & (a ^ res)) >> 31;")
            elif opc == 6:
                flags.append("fC = (uint32_t)(((uint64_t)a + (uint32_t)~bb + fC) >> 32); fV = ((a ^ bb) & (a ^ res)) >> 31;")
            elif opc == 7:
                flags.append("fC = (uint32_t)(((uint64_t)bb + (uint32_t)~a + fC) >> 32); fV = ((bb ^ a) & (bb ^ res)) >> 31;")
        if rd == 15:
            lines.append("pc = res & PC_MASK; cyc -= 2; goto dispatch;")
        else:
            if not test:
                lines.append(f"r{rd} = res;")
            lines += flags
        self.stats["inline"] += 1
        return lines

    def mul(self, w, cur):
        rd, rn, rs, rm = (w >> 16) & 15, (w >> 12) & 15, (w >> 8) & 15, w & 15
        if 15 in (rd, rn, rs, rm):
            return self.interp(w, cur)
        expr = f"r{rm} * r{rs}" + (f" + r{rn}" if w & 0x00200000 else "")
        lines = [f"uint32_t res = {expr};", f"r{rd} = res;"]
        if w & 0x00100000:
            lines.append("fN = res >> 31; fZ = (res == 0);")
        lines.append("cyc -= 8;")
        self.stats["inline"] += 1
        return lines

    def single(self, w, cur):
        rn, rd = (w >> 16) & 15, (w >> 12) & 15
        p, u, byte = (w >> 24) & 1, (w >> 23) & 1, (w >> 22) & 1
        wb, load = (w >> 21) & 1, (w >> 20) & 1
        lines = [f"uint32_t base = {self.reg(rn, cur)};"]
        if not (w >> 25) & 1:
            off = f"0x{w & 0xFFF:x}u"
        else:
            rm, typ, amt = w & 15, (w >> 5) & 3, (w >> 7) & 31
            lines.append(f"uint32_t m = {self.reg(rm, cur, True)};")
            if typ == 0:
                off = f"(m << {amt})" if amt else "m"
            elif typ == 1:
                off = f"(m >> {amt})" if amt else "0u"
            elif typ == 2:
                off = f"(uint32_t)((int32_t)m >> {amt if amt else 31})"
            else:
                off = f"((m >> {amt}) | (m << {32 - amt}))" if amt else "((m >> 1) | (fC << 31))"
        lines.append(f"uint32_t addr = base {'+' if u else '-'} {off};")
        ea = "addr" if p else "base"
        writeback = (not p or wb) and rn != 15
        if load:
            lines.append(f"uint32_t v; {'RD8' if byte else 'RD32R'}(v, {ea});")
            if writeback:
                lines.append(f"r{rn} = addr;")
            if rd == 15:
                lines.append("pc = v & PC_MASK; cyc -= 4; goto dispatch;")
            else:
                lines.append(f"r{rd} = v; cyc -= 2;")
        else:
            lines.append(f"uint32_t v = {self.reg(rd, cur, True, 12)};")
            lines.append(f"{'WR8' if byte else 'WR32'}({ea}, v);")
            if writeback:
                lines.append(f"r{rn} = addr;")
            lines.append("cyc -= 1;")
        self.stats["inline"] += 1
        return lines

    def block(self, w, cur):
        rn = (w >> 16) & 15
        p, u, sbit = (w >> 24) & 1, (w >> 23) & 1, (w >> 22) & 1
        wb, load = (w >> 21) & 1, (w >> 20) & 1
        regs = [i for i in range(16) if w & (1 << i)]
        count = len(regs)
        if sbit or rn == 15 or count == 0:
            return self.interp(w, cur)
        lines = [f"uint32_t base = r{rn};"]
        start = "base" if u else f"base - {4 * count}"
        final = f"base + {4 * count}" if u else f"base - {4 * count}"
        lines.append(f"uint32_t addr = ({start}{' + 4' if p == u else ''}) & ~3u;")
        lines.append(f"cyc -= {count + 1};")
        if load:
            if wb:
                lines.append(f"r{rn} = {final};")
            for k, i in enumerate(regs):
                if i == 15:
                    lines.append(f"{{ uint32_t v; RD32(v, addr + {4 * k}); pc = v & PC_MASK; }} cyc -= 2; goto dispatch;")
                else:
                    lines.append(f"RD32(r{i}, addr + {4 * k});")
        else:
            for k, i in enumerate(regs):
                if i == 15:
                    v = self.reg(15, cur, True, 12)
                elif i == rn:
                    v = "base" if (k == 0 or not wb) else f"({final})"
                else:
                    v = f"r{i}"
                lines.append(f"WR32(addr + {4 * k}, {v});")
            if wb:
                lines.append(f"r{rn} = {final};")
        self.stats["inline"] += 1
        return lines

    def branch(self, w, cur, chunk):
        off = w & 0x00FFFFFF
        if off & 0x00800000:
            off -= 0x01000000
        target = (cur + 8 + (off << 2)) & PC_MASK
        lines = []
        if w & 0x01000000:
            lines.append(f"r14 = 0x{(cur + 4) & PC_MASK:08x}u | PSR();")
        lines.append("cyc -= 2;")
        if cur in self.idle_tails:
            lines.append(f"IDLE({self.idle_tails[cur]});")
        lines.append(self.goto(target, chunk))
        self.stats["inline"] += 1
        return lines

    def swi(self, w, cur):
        nxt = (cur + 4) & PC_MASK
        self.stats["inline"] += 1
        return [f"cyc -= 2; SYNC_OUT(); cpu->pc = 0x{nxt:08x}u;",
                f"if (swi_call(cpu, 0x{w & 0x00FFFFFF:06x}u)) cpu->stop = 1;",
                "SYNC_IN();",
                "if (cpu->stop) { pc = cpu->pc; goto leave; }",
                f"if (cpu->pc != 0x{nxt:08x}u) {{ pc = cpu->pc; goto dispatch; }}"]

    def instruction(self, a, w, chunk):
        cond = w >> 28
        if cond == 15:
            return ["cyc -= 1;"]
        cls = (w >> 25) & 7
        if cls in (0, 1):
            if cls == 0 and is_mul(w):
                body = self.mul(w, a)
            elif cls == 0 and is_swp(w):
                body = self.interp(w, a)
            else:
                body = self.data_proc(w, a)
        elif cls in (2, 3):
            body = self.single(w, a)
        elif cls == 4:
            body = self.block(w, a)
        elif cls == 5:
            body = self.branch(w, a, chunk)
        elif (w & 0x0F000000) == 0x0F000000:
            body = self.swi(w, a)
        else:
            body = self.interp(w, a)
        if body and body[0].startswith("INTERP("):
            return body                     # the interpreter does its own cycle and condition
        text = " ".join(body)
        if cond == 14:
            return ["cyc -= 1;", "{ " + text + " }"]
        return ["cyc -= 1;", f"if ({COND[cond]}) {{ {text} }}"]

    def chunk(self, k, addrs):
        o = self.out
        o.append(f"static void chunk_{k:x}(arm26_t *cpu)\n{{")
        o.append("    LOCALS; uint32_t pc = cpu->pc; SYNC_IN();")
        o.append("dispatch:")
        o.append("    switch (pc) {")
        for a in addrs:
            if a in self.leaders:
                o.append(f"    case 0x{a:x}: goto L_{a:x};")
        o.append("    default: goto leave;")
        o.append("    }")
        prev_falls = False
        prev = None
        for a in addrs:
            w = self.img.word(a)
            if prev is not None and prev_falls and prev + 4 != a:
                o.append(f"    pc = 0x{prev + 4:08x}u; goto leave;")
            if a in self.leaders:
                o.append(f"L_{a:x}: if (cyc <= 0) {{ pc = 0x{a:x}; goto leave; }}")
                if a in self.idle_heads:
                    o.append("    io_seen = 0;")
            for line in self.instruction(a, w, k):
                o.append(f"    {line}")
            prev, prev_falls = a, flow(a, w)[0]
        if prev is not None and prev_falls:
            o.append(f"    pc = 0x{prev + 4:08x}u; goto leave;")
        o.append("leave:")
        o.append("    SYNC_OUT(); cpu->pc = pc;")
        o.append("}\n")


def load_extra(build):
    extra_path = build / "leaders_extra.txt"
    extra = set(int(x, 16) for x in extra_path.read_text().split()) if extra_path.exists() else set()
    seen_path = build / "leaders_seen.txt"
    if seen_path.exists():                  # fallback entry points from the last translated run
        extra |= set(int(x, 16) for x in seen_path.read_text().split())
        extra_path.write_text("".join(f"{a:x}\n" for a in sorted(extra)))
        seen_path.unlink()
    return sorted(extra)


def translate(name, img, extra, out):
    """Emit the chunks of one image; return its region table entry."""
    code, leaders = discover(img, extra)
    limit = ((max(code) >> CHUNK_SHIFT) + 1) << CHUNK_SHIFT
    em = Emitter(img, code, leaders)
    chunks = {}
    for a in sorted(code):
        chunks.setdefault(a >> CHUNK_SHIFT, []).append(a)
    first, last = img.base >> CHUNK_SHIFT, (limit >> CHUNK_SHIFT) - 1
    for k in range(first, last + 1):
        if k in chunks:
            em.chunk(k, chunks[k])
    em.out.append(f"static const recomp_chunk_fn {name}_chunks[] = {{")
    for k in range(first, last + 1):
        em.out.append(f"    {'chunk_%x' % k if k in chunks else '0'},")
    em.out.append("};")
    bits = bytearray(((limit - img.base) >> 2) // 8 + 1)
    for a in leaders:
        i = (a - img.base) >> 2
        bits[i >> 3] |= 1 << (i & 7)
    em.out.append(f"static const uint8_t {name}_leaders[] = {{")
    for i in range(0, len(bits), 24):
        em.out.append("    " + ",".join(str(b) for b in bits[i:i + 24]) + ",")
    em.out.append("};")
    out += em.out
    covered = sum(1 for a in code if img.executed(a))
    print(f"{name}: code words {len(code)} (executed in reference runs {covered}), leaders {len(leaders)}, "
          f"range {img.base:x}..{limit:x}, chunks {len(chunks)}, "
          f"inline {em.stats['inline']}, via interpreter {em.stats['interp']}, wait loops {em.stats['idle']}")
    return f"    {{ 0x{img.base:x}u, 0x{limit:x}u, {name}_leaders, {name}_chunks }},"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--build", type=Path, default=BUILD)
    args = ap.parse_args()
    extra = load_extra(args.build)
    out = ["/* Generated by tools/lotus/recomp.py from the user's game image. Do not publish. */",
           '#include "recomp_rt.h"\n']
    regions = []

    # the image file runs to &70000; code and data end far earlier, trim trailing zeros
    data = (args.build / "game_image.bin").read_bytes()
    end = len(data)
    while end > 4 and data[end - 4:end] == b"\0\0\0\0":
        end -= 4
    # own-view hooks for linked consoles (port/core/view.c): the runtime writes the same
    # SWIs into guest memory once the program is unpacked
    data = bytearray(data)
    for addr, old, new in ((0x16D74, 0xE92D8000, 0xEF0FFFF2), (0x16DD4, 0xE5DCE5BB, 0xEF0FFFF4), (0x16E40, 0xE92D8000, 0xEF0FFFF3), (0x16E4C, 0xE92D8000, 0xEF0FFFF5)):
        o = addr - 0x8000
        if int.from_bytes(data[o:o + 4], "little") != old:
            raise SystemExit(f"game image differs at {addr:#x}: not the expected version")
        data[o:o + 4] = new.to_bytes(4, "little")
    data = bytes(data)
    regions.append(translate("game", Image(data[:end], (args.build / "coverage.bin").read_bytes()), extra, out))

    mus = args.build / "musmod2.bin"
    mus_cov = args.build / "coverage_mus.bin"
    if mus.exists() and mus_cov.exists():
        regions.append(translate("mus", Image(mus.read_bytes(), mus_cov.read_bytes(), MUS_BASE), extra, out))

    out.append("const arm26_region_t recomp_regions[] = {")
    out += regions
    out.append("};")
    out.append(f"const unsigned recomp_region_count = {len(regions)};")
    gen = args.build / "gen"
    gen.mkdir(parents=True, exist_ok=True)
    (gen / "lotus_gen.c").write_text("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
