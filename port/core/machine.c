/* Guest bus, IOC/VIDC/MEMC model and frame scheduler. */
#include <stdlib.h>
#include <string.h>
#include "machine.h"

machine_t M;

void *guest_ptr(uint32_t addr) { return M.ram + (addr & (GUEST_RAM_SIZE - 1)); }

void guest_string(uint32_t addr, char *out, size_t max)
{
    size_t i = 0;
    for (; i + 1 < max; i++) {
        uint8_t c = M.ram[(addr + i) & (GUEST_RAM_SIZE - 1)];
        if (c < 32) break;
        out[i] = (char)c;
    }
    out[i] = 0;
}

static uint32_t io_read(uint32_t addr, int byte)
{
    (void)byte;
    if (addr == RETURN_TRAP) return 0xEF0FFFF0u;
    if ((addr & 0x03E00000u) == 0x03200000u) {
        unsigned reg = addr & 0x7C;
        switch (reg) {
        case 0x00: return 0xFF;                       /* control: all inputs high */
        case 0x04: return 0;                          /* keyboard rx */
        case 0x10: return M.irqa_status | 0x80;
        case 0x14: return (M.irqa_status | 0x80) & M.irqa_mask;
        case 0x18: return M.irqa_mask;
        case 0x20: return M.irqb_status;
        case 0x24: return M.irqb_status & M.irqb_mask;
        case 0x28: return M.irqb_mask;
        case 0x30: return 0;
        case 0x34: return 0;
        case 0x38: return M.fiq_mask;
        default:
            if (reg >= 0x40 && reg < 0x80) {
                unsigned t = (reg - 0x40) >> 4, sub = reg & 0x0C;
                if (sub == 0) return M.timer_out[t] & 0xFF;
                if (sub == 4) return M.timer_out[t] >> 8;
            }
            break;
        }
        if (M.trace) host_log("IOC read %08x pc=%08x\n", addr, M.cpu.pc - 4);
        return 0xFF;
    }
    host_log("IO read %08x pc=%08x\n", addr, M.cpu.pc - 4);
    return 0xFFFFFFFFu;
}

static void vidc_write(uint32_t v)
{
    unsigned reg = v >> 26;
    if (reg < 16) { M.palette[reg] = v & 0x1FFF; M.palette_dirty = 1; }
    else if (reg == 16) M.border = v & 0x1FFF;
    else if (M.trace) host_log("VIDC %08x pc=%08x\n", v, M.cpu.pc - 4);
}

static void io_write(uint32_t addr, uint32_t v, int byte)
{
    (void)byte;
    if ((addr & 0x03E00000u) == 0x03200000u) {
        unsigned reg = addr & 0x7C;
        switch (reg) {
        case 0x14: M.irqa_status &= ~(v & 0x7C); return;
        case 0x18: M.irqa_mask = v; arm26_yield(&M.cpu); return;
        case 0x28: M.irqb_mask = v; arm26_yield(&M.cpu); return;
        case 0x38: M.fiq_mask = v; return;
        default:
            if (reg >= 0x40 && reg < 0x80) {
                unsigned t = (reg - 0x40) >> 4, sub = reg & 0x0C;
                if (sub == 0) M.timer_latch[t] = (M.timer_latch[t] & 0xFF00) | (v & 0xFF);
                else if (sub == 4) M.timer_latch[t] = (M.timer_latch[t] & 0x00FF) | ((v & 0xFF) << 8);
                else if (sub == 8) M.timer_count[t] = M.timer_latch[t];
                else M.timer_out[t] = M.timer_count[t];
                if (M.trace) host_log("IOC timer%u reg %x = %02x pc=%08x\n", t, sub, v & 0xFF, M.cpu.pc - 4);
                return;
            }
            break;
        }
        host_log("IOC write %08x = %08x pc=%08x\n", addr, v, M.cpu.pc - 4);
        return;
    }
    if ((addr & 0x03E00000u) == 0x03400000u) { vidc_write(v); return; }
    if ((addr & 0x03E00000u) == 0x03600000u) {
        if (M.trace) host_log("MEMC %08x pc=%08x\n", addr, M.cpu.pc - 4);
        return;
    }
    host_log("IO write %08x = %08x pc=%08x\n", addr, v, M.cpu.pc - 4);
}

#ifdef ARM26_COVERAGE
/* Per guest word: 1 executed, 2 written while armed, 4 already reported. */
uint8_t cov_map[GUEST_RAM_SIZE / 4];
int cov_armed;
unsigned cov_write_hits, cov_exec_hits;

void cov_exec(uint32_t addr)
{
    if (addr >= GUEST_RAM_SIZE) return;
    uint8_t *c = &cov_map[addr >> 2];
    if ((*c & 6) == 2) {
        *c |= 4;
        if (cov_exec_hits++ < 40) host_log("COV executing word written at run time: %08x\n", addr);
    }
    *c |= 1;
}

static void cov_write(uint32_t addr)
{
    uint8_t *c = &cov_map[addr >> 2];
    if (!cov_armed) return;
    if ((*c & 5) == 1) {
        *c |= 4;
        if (cov_write_hits++ < 40) host_log("COV write to executed word %08x from pc=%08x\n", addr & ~3u, M.cpu.pc - 4);
    }
    *c |= 2;
}
/* analysis aid: LOTUS_WATCH=addr[,len] logs every access to that range with the PC */
uint32_t watch_lo = 1, watch_hi = 0;
static void watch(uint32_t addr, unsigned size, int write, uint32_t v)
{
    if (addr + size > watch_lo && addr < watch_hi)
        host_log("WATCH frame %u line %u %s%u %08x = %08x pc=%08x\n", M.frame, M.line, write ? "W" : "R", size * 8, addr, v,
                 M.cpu.pc - 8);
}
#define WATCH(a, s, w, v) watch(a, s, w, v)
#else
#define cov_write(addr) ((void)0)
#define WATCH(a, s, w, v) ((void)0)
#endif

uint32_t bus_read32(uint32_t addr)
{
    addr &= 0x03FFFFFCu;
    WATCH(addr, 4, 0, M.ram && addr < GUEST_RAM_SIZE ? *(uint32_t *)(M.ram + addr) : 0);
    if (addr < GUEST_RAM_SIZE) {
        const uint8_t *p = M.ram + addr;
        return p[0] | (p[1] << 8) | (p[2] << 16) | ((uint32_t)p[3] << 24);
    }
    return io_read(addr, 0);
}

uint32_t bus_read8(uint32_t addr)
{
    addr &= 0x03FFFFFFu;
    WATCH(addr, 1, 0, addr < GUEST_RAM_SIZE ? M.ram[addr] : 0);
    if (addr < GUEST_RAM_SIZE) return M.ram[addr];
    return io_read(addr & ~3u, 1) & 0xFF;
}

void bus_write32(uint32_t addr, uint32_t v)
{
    addr &= 0x03FFFFFCu;
    if (addr < GUEST_RAM_SIZE) {
        uint8_t *p = M.ram + addr;
        cov_write(addr);
        WATCH(addr, 4, 1, v);
        p[0] = v; p[1] = v >> 8; p[2] = v >> 16; p[3] = v >> 24;
        return;
    }
    io_write(addr, v, 0);
}

void bus_write8(uint32_t addr, uint32_t v)
{
    addr &= 0x03FFFFFFu;
    if (addr < GUEST_RAM_SIZE) { cov_write(addr); WATCH(addr, 1, 1, v); M.ram[addr] = v; return; }
    io_write(addr & ~3u, (v & 0xFF) * 0x01010101u, 1);
}

void cpu_fault(arm26_t *cpu, const char *what, uint32_t insn)
{
    host_log("CPU fault: %s insn=%08x pc=%08x mode=%u\n", what, insn, cpu->pc - 4, cpu->psr & 3);
    M.fatal = 1;
}

void machine_init(void)
{
    memset(&M, 0, sizeof M);
    M.ram = calloc(1, GUEST_RAM_SIZE + 16);
    arm26_reset(&M.cpu);
    M.cpu.bank_svc[0] = SVC_STACK_TOP;
    M.cpu.bank_irq[0] = IRQ_STACK_TOP;
    M.run = arm26_run;
    M.rma_next = RMA_BASE;
    M.bpp = 4;
    M.irqa_mask = 0x28;                   /* RISC OS: VSync and Timer0 */
    M.timer_latch[0] = M.timer_count[0] = 19999;   /* 100 Hz ticker */
    M.timer_latch[1] = M.timer_count[1] = 0xFFFF;
    bus_write32(0x18, 0xEA000000u | (((OS_IRQ_ENTRY - 0x18 - 8) >> 2) & 0x00FFFFFFu));
    bus_write32(OS_IRQ_ENTRY, 0xEF0FFFF1u);
    for (int i = 0; i < 16; i++) M.palette[i] = (i * 0x111) & 0xFFF;
    sound_init();
}

/* Run a guest routine to completion in SVC mode, preserving the caller. */
int guest_call(uint32_t addr, uint32_t r0, uint32_t r12)
{
    arm26_t saved = M.cpu;
    arm26_set_mode(&M.cpu, MODE_SVC);
    M.cpu.psr |= PSR_I;
    M.cpu.r[0] = r0;
    M.cpu.r[12] = r12;
    M.cpu.r[14] = RETURN_TRAP | M.cpu.psr;
    M.cpu.pc = addr & PC_MASK;
    M.cpu.stop = 0;
    M.cpu.cycles = 4 * CYCLES_PER_LINE * LINES_PER_FRAME;
    M.run(&M.cpu);
    int ok = (M.cpu.stop == 2);
    if (!ok && !M.fatal) { host_log("guest_call %08x did not return (pc=%08x)\n", addr, M.cpu.pc); M.fatal = 1; }
    uint64_t insns = M.cpu.insns;
    M.cpu = saved;
    M.cpu.insns = insns;
    return ok;
}

/* Run a guest routine with a full register set in the given mode. */
int guest_call_regs(uint32_t addr, uint32_t mode, uint32_t regs[13])
{
    arm26_t saved = M.cpu;
    arm26_set_mode(&M.cpu, mode);
    M.cpu.psr |= PSR_I;
    memcpy(M.cpu.r, regs, 13 * sizeof regs[0]);
    M.cpu.r[14] = RETURN_TRAP | M.cpu.psr;
    M.cpu.pc = addr & PC_MASK;
    M.cpu.stop = 0;
    /* the routine may enable interrupts, which yields; nothing is delivered here, so carry on */
    for (int32_t budget = 64 * CYCLES_PER_LINE * LINES_PER_FRAME; budget > 0 && !M.cpu.stop; ) {
        M.cpu.cycles = budget;
        M.cpu.yielded = 0;
        M.run(&M.cpu);
        budget = M.cpu.cycles + M.cpu.yielded;
    }
    int ok = (M.cpu.stop == 2) ? ((M.cpu.psr & PSR_V) ? -1 : 1) : 0;
    if (!ok && !M.fatal) {
        host_log("guest call %08x did not return (pc=%08x mode=%u r7=%08x r10=%08x r11=%08x r12=%08x r13=%08x stop=%d cycles=%d)\n",
                 addr, M.cpu.pc, M.cpu.psr & 3, M.cpu.r[7], M.cpu.r[10], M.cpu.r[11], M.cpu.r[12], M.cpu.r[13],
                 M.cpu.stop, M.cpu.cycles);
        M.fatal = 1;
    }
    memcpy(regs, M.cpu.r, 13 * sizeof regs[0]);
    uint64_t insns = M.cpu.insns;
    M.cpu = saved;
    M.cpu.insns = insns;
    return ok;
}

/* Advance both IOC timers by a number of 2 MHz ticks. */
static void timers_tick(uint32_t ticks)
{
    for (int t = 0; t < 2; t++) {
        uint32_t c = M.timer_count[t];
        if (ticks == 0) continue;
        if (c > ticks) { M.timer_count[t] = c - ticks; continue; }
        uint32_t latch = M.timer_latch[t] ? M.timer_latch[t] : 0x10000;
        uint32_t over = ticks - c;
        M.timer_count[t] = latch - (over % latch);
        M.irqa_status |= (t == 0) ? 0x20 : 0x40;
    }
}

static uint32_t next_timer_cycles(void)
{
    uint32_t c = M.timer_count[0] < M.timer_count[1] ? M.timer_count[0] : M.timer_count[1];
    if (c == 0) c = 1;
    return c * 4 - M.tick_fraction;
}

static int irq_pending(void)
{
    return ((M.irqa_status | 0x80) & M.irqa_mask) || (M.irqb_status & M.irqb_mask);
}

/* The OS interrupt handler, reached through the untouched vector at &18. */
void os_irq_handler(arm26_t *cpu)
{
    uint8_t req = (M.irqa_status | 0x80) & M.irqa_mask;
    if (req & 0x08) {
        M.irqa_status &= ~0x08;
        if (M.vsync_event_enabled)
            for (int i = M.event_handlers - 1; i >= 0; i--)
                guest_call(M.event_handler[i], 4, M.event_r12[i]);
    }
    if (req & 0x20) M.irqa_status &= ~0x20;
    if (req & 0x40) M.irqa_status &= ~0x40;
    if (M.irqb_status & M.irqb_mask & 0x02) sound_service();
    M.irqa_mask &= 0x7F;
    /* SUBS PC,R14,#4 */
    uint32_t lr = cpu->r[14];
    cpu->psr = (cpu->psr & PSR_MODE) | (lr & (PSR_FLAGS | PSR_I | PSR_F));
    arm26_set_mode(cpu, lr & PSR_MODE);
    cpu->pc = (lr - 4) & PC_MASK;
}

/* Emulated time now, inside a CPU slice. */
uint64_t machine_now(const arm26_t *cpu)
{
    return M.cycle_clock + (uint64_t)(M.run_slice - cpu->cycles - cpu->yielded);
}

void machine_run_frame(void)
{
    /* once the start-up stub has unpacked the program, install the own-view hooks (view.c) */
    if (!M.view_patched && M.cpu.pc >= APP_BASE && M.cpu.pc < 0x70000 && view_patch_ok()) {
        view_patch();
        M.view_patched = 1;
    }
    for (M.line = 0; M.line < LINES_PER_FRAME && !M.fatal; M.line++) {
        if (M.line == VSYNC_LINE) {
            M.irqa_status |= 0x08;
            M.monotonic_cs += 2;
            M.wait_vsync = 0;
        }
        int32_t left = CYCLES_PER_LINE - M.line_debt;
        while (left > 0 && !M.fatal) {
            int32_t slice = (int32_t)next_timer_cycles();
            if (slice > left) slice = left;
            int32_t used = slice;
            /* while own-view drawing is frozen no time passes, so nothing new is pending;
               anything already pending waits until the drawing is done */
            if (irq_pending() && !(M.cpu.psr & PSR_I) && !M.frozen) { arm26_irq(&M.cpu); M.wait_vsync = 0; }
            if (!M.wait_vsync) {
                M.cpu.cycles = slice;
                M.cpu.yielded = 0;
                M.cpu.stop = 0;
                M.run_slice = slice;
                M.time_refund = 0;
                if (M.frozen) M.freeze_at = M.cycle_clock;
                M.run(&M.cpu);
                if (M.cpu.stop) { M.fatal = 1; break; }
                used = slice - M.cpu.cycles - M.cpu.yielded;
                if (M.frozen) M.time_refund += (int32_t)(M.cycle_clock + (uint64_t)used - M.freeze_at);
                used -= M.time_refund;
                if (used < 0) used = 0;
            }
            M.cycle_clock += (uint64_t)used;
            left -= used;
            M.tick_fraction += (uint32_t)used;
            timers_tick(M.tick_fraction / 4);
            sound_tick(used);
            M.tick_fraction &= 3;
        }
        M.line_debt = -left;
        if (M.line < SCREEN_H) {
            memcpy(M.line_palette[M.line], M.palette, sizeof M.palette);
            M.line_new_palette[M.line] = M.palette_dirty || M.line == 0;
            M.palette_dirty = 0;
            M.line_display[M.line] = M.display_offset;
            /* The picture is what the video hardware read while this line was on
               screen. The race swaps banks at vertical sync and starts drawing the next
               frame into the other bank during the blank lines that follow, so screen
               memory at the end of the frame is not what was displayed. */
            unsigned bytes = (M.bpp == 8) ? SCREEN_W : LINE_BYTES;
            memcpy(M.line_pixels[M.line], M.ram + SCREEN_BASE + (M.display_offset + M.line * bytes) % SCREEN_BYTES, bytes);
        }
    }
    M.frame++;
}

/* The race clears the leftmost word of every line, 8 pixels, to hide its scroll
   seam (&16E64), which leaves the picture looking pushed to the right. While
   racing the picture is moved 4 pixels left so the black edge is shared by both
   sides. Racing: the game's own IRQ handler is installed at &18. */
#define RACE_IRQ_VECTOR 0xEA0037A0u
static unsigned race_shift(void)
{
    return (M.bpp != 8 && bus_read32(0x18) == RACE_IRQ_VECTOR) ? 4 : 0;
}

void machine_render_rgb(uint8_t *rgb)
{
    unsigned shift = race_shift();
    for (int y = 0; y < SCREEN_H; y++) {
        const uint16_t *pal = M.line_palette[y];
        if (M.bpp == 8) {
            const uint8_t *src = M.line_pixels[y];
            for (int x = 0; x < SCREEN_W; x++) {
                unsigned px = src[x], c = pal[px & 15];
                unsigned r = (c & 7) | ((px >> 1) & 8);
                unsigned g = ((c >> 4) & 3) | ((px >> 3) & 12);
                unsigned b = ((c >> 8) & 7) | ((px >> 4) & 8);
                *rgb++ = r * 17; *rgb++ = g * 17; *rgb++ = b * 17;
            }
            continue;
        }
        const uint8_t *src = M.line_pixels[y];
        for (int x = 0; x < SCREEN_W; x++) {
            unsigned sx = x + shift;
            if (sx >= SCREEN_W) { *rgb++ = 0; *rgb++ = 0; *rgb++ = 0; continue; }
            unsigned px = (src[sx >> 1] >> ((sx & 1) * 4)) & 15;
            unsigned c = pal[px];
            *rgb++ = (c & 15) * 17;
            *rgb++ = ((c >> 4) & 15) * 17;
            *rgb++ = ((c >> 8) & 15) * 17;
        }
    }
}

static inline uint16_t rgb565(unsigned r4, unsigned g4, unsigned b4)
{
    return (uint16_t)((((r4 << 1) | (r4 >> 3)) << 11) | (((g4 << 2) | (g4 >> 2)) << 5) | ((b4 << 1) | (b4 >> 3)));
}

/* The palette can change on any scanline (the race does it about twenty times a
   frame), so the lookup table is rebuilt only when the palette of a line differs
   from the one before (line_new_palette, kept by machine_run_frame). In 16-colour modes one table entry holds both pixels of a byte.
   Screen lines start on word boundaries, so source bytes are read four at a time and
   the picture is written as 32-bit words (two pixels each). */
void machine_render_565(uint16_t *dst, unsigned stride, unsigned first, unsigned lines, unsigned repeat)
{
    static uint32_t pair[256];
    static uint16_t wide[256];
    static int cached_bpp;
    unsigned skip = race_shift() / 2;            /* bytes: two pixels a byte */
    if (repeat < 1) repeat = 1;
    for (unsigned y = first; y < first + lines && y < SCREEN_H; y++, dst = (uint16_t *)((uint8_t *)dst + stride * repeat)) {
        const uint16_t *pal = M.line_palette[y];
        if (y == first || M.line_new_palette[y] || cached_bpp != M.bpp) {
            cached_bpp = M.bpp;
            if (M.bpp == 8) {
                for (unsigned px = 0; px < 256; px++) {
                    unsigned c = pal[px & 15];
                    wide[px] = rgb565((c & 7) | ((px >> 1) & 8), ((c >> 4) & 3) | ((px >> 3) & 12),
                                      ((c >> 8) & 7) | ((px >> 4) & 8));
                }
            } else {
                uint16_t one[16];
                for (unsigned i = 0; i < 16; i++) one[i] = rgb565(pal[i] & 15, (pal[i] >> 4) & 15, (pal[i] >> 8) & 15);
                for (unsigned b = 0; b < 256; b++) pair[b] = one[b & 15] | ((uint32_t)one[b >> 4] << 16);
            }
        }
        uint32_t *out = (uint32_t *)dst;
        if (M.bpp == 8) {
            const uint32_t *src = (const uint32_t *)M.line_pixels[y];
            for (unsigned x = 0; x < SCREEN_W / 4; x++, out += 2) {
                uint32_t b = src[x];
                out[0] = wide[b & 0xFF] | ((uint32_t)wide[(b >> 8) & 0xFF] << 16);
                out[1] = wide[(b >> 16) & 0xFF] | ((uint32_t)wide[b >> 24] << 16);
            }
        } else {
            if (skip) {
                const uint8_t *src = M.line_pixels[y] + skip;
                for (unsigned x = 0; x < LINE_BYTES - skip; x++) out[x] = pair[src[x]];
                for (unsigned x = LINE_BYTES - skip; x < LINE_BYTES; x++) out[x] = 0;
            } else {
                const uint32_t *src = (const uint32_t *)M.line_pixels[y];
                for (unsigned x = 0; x < LINE_BYTES / 4; x++, out += 4) {
                    uint32_t b = src[x];
                    out[0] = pair[b & 0xFF];
                    out[1] = pair[(b >> 8) & 0xFF];
                    out[2] = pair[(b >> 16) & 0xFF];
                    out[3] = pair[b >> 24];
                }
            }
        }
        for (unsigned r = 1; r < repeat; r++)
            memcpy((uint8_t *)dst + stride * r, dst, SCREEN_W * 2);
    }
}
