/* High-level RISC OS services used by the Lotus program. */
#include <string.h>
#include "machine.h"

#define XBIT 0x20000u

static const uint8_t vdu_params[32] = {
    0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 1, 2, 5, 0, 0, 1, 9, 8, 5, 0, 0, 4, 4, 0, 2
};
static uint8_t vdu_queue[10];
static int vdu_have, vdu_need;

static const uint16_t default_palette[16] = {
    0x000, 0x00F, 0x0F0, 0x0FF, 0xF00, 0xF0F, 0xFF0, 0xFFF,
    0x000, 0x00F, 0x0F0, 0x0FF, 0xF00, 0xF0F, 0xFF0, 0xFFF
};

static void set_palette(unsigned logical, unsigned mode, unsigned r, unsigned g, unsigned b)
{
    uint16_t c = (r >> 4) | ((g >> 4) << 4) | ((b >> 4) << 8);
    if (mode < 16) c = default_palette[mode];
    else if (mode == 24) { M.border = c; return; }
    else if (mode != 16 && mode != 17 && mode != 18) return;
    machine_palette_write();
    M.palette[logical & 15] = c;
}

static void vdu_execute(void)
{
    switch (vdu_queue[0]) {
    case 12: case 16:
        memset(guest_ptr(SCREEN_BASE + M.driver_offset), 0, 40960);
        break;
    case 19:
        set_palette(vdu_queue[1], vdu_queue[2], vdu_queue[3], vdu_queue[4], vdu_queue[5]);
        break;
    case 22:
        if (M.trace) host_log("VDU mode %u\n", vdu_queue[1]);
        M.bpp = (vdu_queue[1] == 13) ? 8 : 4;
        machine_palette_write();
        if (M.bpp == 8) {
            /* MODE 13 default: palette supplies the low tint bits */
            for (int i = 0; i < 16; i++)
                M.palette[i] = (i & 3) * 0x111 | ((i & 4) ? 0x004 : 0) | ((i & 8) ? 0x400 : 0);
        } else {
            memcpy(M.palette, default_palette, sizeof M.palette);
        }
        memset(guest_ptr(SCREEN_BASE), 0, SCREEN_BYTES);
        M.display_offset = M.driver_offset = 0;
        break;
    default:
        break;
    }
}

static void vdu(uint8_t c)
{
    if (M.vdu_mute) return;
    if (vdu_need == 0) {
        if (c >= 32) return;              /* text output is not displayed */
        vdu_queue[0] = c;
        vdu_have = 1;
        vdu_need = vdu_params[c];
        if (vdu_need == 0) vdu_execute();
        return;
    }
    vdu_queue[vdu_have++] = c;
    if (--vdu_need == 0) vdu_execute();
}

/* Name and password entry with the pad. The game's editor (&F60C) flushes the
   keyboard buffer (OS_Byte 15), then reads one key at a time with a timed
   OS_Byte 129 (&F688) and takes the letters a to z, space, Delete (8, removes
   the last letter) and Return (13, done). When it reads, r7 is the cursor (0 to
   12) and r8 the 12-letter buffer, so the pad works it by typing: up and down
   change the letter at the cursor (Delete, then the next letter), right accepts
   it (with no letter being chosen, it types a space), left deletes, fire is
   Return. Either pad, so the second player can type too.

   The pad is read once a frame (entry_frame) and presses are kept until the
   editor reads them: after each letter the game redraws the box, which can take
   a few frames. */
#define ENTRY_CALLER 0xF68Cu
#define ENTRY_MAX 12
enum { E_UP = 1, E_DOWN = 2, E_LEFT = 4, E_RIGHT = 8, E_FIRE = 16 };
static const char entry_letters[] = "abcdefghijklmnopqrstuvwxyz ";
static struct {
    uint32_t down, presses, held_since;
    int choosing;                         /* the letter before the cursor is the one up and down change */
    uint8_t queue[2];
    int queued;
} entry;

static uint32_t entry_pad(void)
{
    static const uint8_t keymap[][2] = { { 51, E_UP }, { 88, E_UP }, { 50, E_DOWN }, { 79, E_DOWN }, { 97, E_LEFT },
                                         { 102, E_LEFT }, { 66, E_RIGHT }, { 103, E_RIGHT }, { 5, E_FIRE }, { 8, E_FIRE } };
    uint32_t down = 0;
    for (unsigned i = 0; i < sizeof keymap / sizeof keymap[0]; i++) if (M.keys[keymap[i][0]]) down |= keymap[i][1];
    return down;
}

/* a new box: what is held already does not count */
static void entry_open(void)
{
    entry.down = entry_pad();
    entry.presses = 0;
    entry.choosing = 0;
    entry.queued = 0;
}

void entry_frame(void)
{
    uint32_t down = entry_pad(), pressed = down & ~entry.down;
    if (pressed & (E_UP | E_DOWN)) entry.held_since = M.frame;
    else if (down & (E_UP | E_DOWN)) {
        /* held: repeat after 0.4 s, then 12 letters a second */
        uint32_t held = M.frame - entry.held_since;
        if (held >= 20 && held % 4 == 0) pressed |= down & (E_UP | E_DOWN);
    }
    entry.down = down;
    entry.presses |= pressed;
}

static char entry_step(char c, int dir)
{
    const char *p = c ? strchr(entry_letters, c) : NULL;
    int n = (int)sizeof entry_letters - 1, i = p ? (int)(p - entry_letters) : (dir > 0 ? -1 : 0);
    return entry_letters[(i + dir + n) % n];
}

static void timed_key_read(arm26_t *cpu)
{
    uint32_t cursor = cpu->r[7], buffer = cpu->r[8];
    int editor = cpu->pc == ENTRY_CALLER && cursor <= ENTRY_MAX && buffer >= APP_BASE && buffer + ENTRY_MAX < APP_LIMIT;
    uint32_t p = entry.presses;
    if (!entry.queued && p) {
        if (!editor || (p & E_FIRE)) {
            entry.queue[entry.queued++] = 13;     /* done; from an unknown caller any press is Return */
            entry.choosing = 0;
            p = 0;
        } else if (p & E_LEFT) {
            if (cursor > 0) entry.queue[entry.queued++] = 8;
            entry.choosing = cursor > 1;
            p &= ~E_LEFT;
        } else if (p & (E_UP | E_DOWN)) {
            int dir = (p & E_UP) ? 1 : -1;
            if (cursor > 0 && (entry.choosing || cursor == ENTRY_MAX)) {
                entry.queue[entry.queued++] = 8;
                entry.queue[entry.queued++] = (uint8_t)entry_step((char)bus_read8(buffer + cursor - 1), dir);
            } else {
                entry.queue[entry.queued++] = (uint8_t)entry_step(0, dir);
            }
            entry.choosing = 1;
            p &= ~(E_UP | E_DOWN);
        } else if (p & E_RIGHT) {
            if (!entry.choosing && cursor < ENTRY_MAX) entry.queue[entry.queued++] = ' ';
            entry.choosing = 0;
            p &= ~E_RIGHT;
        }
        entry.presses = p;
    }
    if (entry.queued) {
        cpu->r[1] = entry.queue[0];
        cpu->r[2] = 0;
        entry.queue[0] = entry.queue[1];
        entry.queued--;
    } else {
        /* nothing typed: wait until the next frame, as a real timed read waits, and
           report the time-out (answering at once made the loop spin) */
        cpu->r[1] = 0;
        cpu->r[2] = 0xFF;
        M.wait_vsync = 1;
        cpu->cycles = 0;
    }
}

static void os_byte(arm26_t *cpu)
{
    uint32_t a = cpu->r[0] & 0xFF, x = cpu->r[1], y = cpu->r[2];
    switch (a) {
    case 13: if ((x & 0xFF) == 4) M.vsync_event_enabled = 0; break;
    case 14: if ((x & 0xFF) == 4) M.vsync_event_enabled = 1; break;
    case 19: M.wait_vsync = 1; cpu->cycles = 0; break;
    case 112: M.driver_offset = ((x & 0xFF) == 2) ? 40960 : 0; break;
    case 113:
        M.display_offset = ((x & 0xFF) == 2) ? 40960 : 0;
        if (M.trace) host_log("BANK frame %u line %u: OS_Byte 113 %u pc=%08x\n", M.frame, M.line, x & 0xFF, cpu->pc - 4);
        break;
    case 121: case 129:
        if (M.trace) host_log("KEYSCAN %u x=%02x y=%02x pc=%08x\n", a, x & 0xFF, y & 0xFF, cpu->pc - 4);
        if (a == 121) {
            if (x & 0x80) cpu->r[1] = M.keys[x & 0x7F] ? 0xFF : 0;
            else {
                uint32_t k = x & 0x7F;
                while (k < 128 && !M.keys[k]) k++;
                cpu->r[1] = (k < 128) ? k : 0xFF;
            }
        } else if ((y & 0xFF) == 0xFF) {
            cpu->r[1] = cpu->r[2] = M.keys[(x ^ 0xFF) & 0x7F] ? 0xFF : 0;
        } else {
            timed_key_read(cpu);              /* INKEY with a time limit: the name and password boxes */
        }
        break;
    case 15:                              /* flush the keyboard buffer: the name and password boxes start so */
        entry_open();
        cpu->r[1] = 0;
        break;
    case 200: case 201: case 229: case 4: case 21: case 124: case 126: case 9: case 10:
        cpu->r[1] = 0;
        break;
    default:
        if (M.trace) host_log("OS_Byte %u,%u,%u pc=%08x\n", a, x & 0xFF, y & 0xFF, cpu->pc - 4);
        cpu->r[1] = 0;
        break;
    }
}

static void os_word(arm26_t *cpu)
{
    uint32_t a = cpu->r[0] & 0xFF;
    uint8_t *blk = guest_ptr(cpu->r[1]);
    switch (a) {
    case 12:
        set_palette(blk[0], blk[1], blk[2], blk[3], blk[4]);
        break;
    case 14:
        memset(blk, 0, 7);                /* fixed clock: deterministic runs */
        break;
    case 22: {
        uint32_t off = blk[1] | (blk[2] << 8) | (blk[3] << 16) | ((uint32_t)blk[4] << 24);
        off %= SCREEN_BYTES;
        if (blk[0] & 1) M.driver_offset = off;
        if (blk[0] & 2) M.display_offset = off;
        if (M.trace) host_log("BANK frame %u line %u: OS_Word 22 type %u offset %u pc=%08x\n", M.frame, M.line, blk[0], off, cpu->pc - 4);
        break;
    }
    default:
        if (M.trace) host_log("OS_Word %u pc=%08x\n", a, cpu->pc - 4);
        break;
    }
}

static int os_file(arm26_t *cpu)
{
    char name[128];
    uint32_t size = 0, op = cpu->r[0] & 0xFF;
    guest_string(cpu->r[1], name, sizeof name);
    switch (op) {
    case 0xFF: case 0x10: case 0x0E: case 0x0C:
        if (!host_load_file(name, cpu->r[2], &size)) {
            host_log("OS_File load failed: %s\n", name);
            return 0;
        }
        if (M.trace) host_log("OS_File load %s -> %08x (%u bytes)\n", name, cpu->r[2], size);
        cpu->r[0] = 1;
        cpu->r[4] = size;
        return 1;
    case 5: case 0x11: case 0x0D: case 0x0F:
        if (!host_file_size(name, &size)) { cpu->r[0] = 0; return 1; }
        cpu->r[0] = 1;
        cpu->r[4] = size;
        cpu->r[2] = cpu->r[3] = 0;
        cpu->r[5] = 3;
        return 1;
    default:
        host_log("OS_File op %u (%s) unsupported pc=%08x\n", op, name, cpu->pc - 4);
        return 0;
    }
}

static void read_vdu_variables(arm26_t *cpu)
{
    uint32_t in = cpu->r[0], out = cpu->r[1];
    for (;; in += 4, out += 4) {
        int32_t var = (int32_t)bus_read32(in);
        uint32_t v = 0;
        if (var == -1) break;
        switch (var) {
        case 148: v = SCREEN_BASE + M.driver_offset; break;
        case 149: v = SCREEN_BASE + M.display_offset; break;
        case 150: v = SCREEN_BYTES; break;
        case 6: v = (M.bpp == 8) ? SCREEN_W : LINE_BYTES; break;
        case 7: v = (M.bpp == 8) ? 81920 : 40960; break;
        case 11: v = SCREEN_W - 1; break;
        case 12: v = SCREEN_H - 1; break;
        case 9: v = (M.bpp == 8) ? 3 : 2; break;
        case 3: v = (M.bpp == 8) ? 63 : 15; break;
        default: host_log("VDU variable %d requested\n", var); break;
        }
        bus_write32(out, v);
    }
}

int swi_call(arm26_t *cpu, uint32_t number)
{
    uint32_t n = number & ~XBIT;
    int ok = 1;

    if (number == 0x0FFFF0) { cpu->stop = 2; return 0; }
    if (number == 0x0FFFF1) { os_irq_handler(cpu); return 0; }
    if (number == SWI_VIEW_START || number == SWI_VIEW_P2 || number == SWI_VIEW_END || number == SWI_VIEW_AFTER) { view_hook(cpu, number); return 0; }
    if (n >= 0x100 && n < 0x200) { vdu(n & 0xFF); goto done; }
    if (n >= 0x41C40 && n < 0x41C80) { ok = mus_swi(cpu, n - 0x41C40); goto done; }   /* MusicModule2 */
    if (n >= 0x40140 && n < 0x40200) { sound_swi(cpu, n); goto done; }
    switch (n) {
    case 0x00: vdu(cpu->r[0] & 0xFF); break;
    case 0x01: {                              /* OS_WriteS */
        uint32_t p = cpu->pc;
        uint8_t c;
        while ((c = bus_read8(p++)) != 0) vdu(c);
        cpu->pc = (p + 3) & PC_MASK;
        break;
    }
    case 0x02: {                              /* OS_Write0 */
        uint8_t c;
        while ((c = bus_read8(cpu->r[0]++)) != 0) vdu(c);
        break;
    }
    case 0x03: case 0x05: break;              /* OS_NewLine, OS_CLI */
    case 0x06: os_byte(cpu); break;
    case 0x07: os_word(cpu); break;
    case 0x08: ok = os_file(cpu); break;
    case 0x16: arm26_set_mode(cpu, MODE_SVC); break;      /* OS_EnterOS */
    case 0x11:
        host_log("OS_Exit pc=%08x\n", cpu->pc - 4);
        M.fatal = 1;
        return 1;
    case 0x1E:                                /* OS_Module */
        if (cpu->r[0] == 6) {
            cpu->r[2] = M.rma_next;
            M.rma_next += (cpu->r[3] + 15) & ~15u;
        } else if (cpu->r[0] != 7 && M.trace) {
            host_log("OS_Module %u pc=%08x\n", cpu->r[0], cpu->pc - 4);
        }
        break;
    case 0x1F:                                /* OS_Claim */
        if (cpu->r[0] == 0x10 && M.event_handlers < 4) {
            M.event_handler[M.event_handlers] = cpu->r[1];
            M.event_r12[M.event_handlers++] = cpu->r[2];
        } else {
            host_log("OS_Claim vector %x routine %08x\n", cpu->r[0], cpu->r[1]);
        }
        break;
    case 0x20:                                /* OS_Release */
        if (cpu->r[0] == 0x10) {
            for (int i = 0; i < M.event_handlers; i++)
                if (M.event_handler[i] == cpu->r[1]) {
                    M.event_handlers--;
                    M.event_handler[i] = M.event_handler[M.event_handlers];
                    M.event_r12[i] = M.event_r12[M.event_handlers];
                    break;
                }
        }
        break;
    case 0x2C: break;                         /* OS_WriteEnv filler used by X Lock */
    case 0x31: read_vdu_variables(cpu); break;
    case 0x36: case 0x37: break;              /* cursors */
    case 0x40: cpu->r[1] = cpu->r[2] = cpu->r[3] = 0; break;
    case 0x42: cpu->r[0] = M.monotonic_cs; break;
    case 0x43F40: {                           /* Joystick_Read: Y, X signed bytes, then switches */
        uint32_t v = 0, pad = cpu->r[0] == 0 ? M.pad : cpu->r[0] == 1 ? M.pad2 : 0;
        if (pad & PAD_UP) v |= 0x40;
        if (pad & PAD_DOWN) v |= 0xC0;
        if (pad & PAD_RIGHT) v |= 0x4000;
        if (pad & PAD_LEFT) v |= 0xC000;
        if (pad & PAD_FIRE) v |= 0x10000;
        cpu->r[0] = v;
        break;
    }
    default:
        /* failing X SWIs are expected: the game probes for third-party joystick modules */
        if (!(number & XBIT) || M.trace)
            host_log("SWI %06x unhandled: r0=%08x r1=%08x r2=%08x r3=%08x pc=%08x\n", number,
                     cpu->r[0], cpu->r[1], cpu->r[2], cpu->r[3], cpu->pc - 4);
        if (!(number & XBIT) && !M.lenient) { M.fatal = 1; return 1; }
        ok = 0;
        break;
    }
done:
    if (ok) cpu->psr &= ~PSR_V;
    else if (number & XBIT) cpu->psr |= PSR_V;
    else { host_log("SWI %06x raised an error\n", number); M.fatal = 1; return 1; }
    return 0;
}
