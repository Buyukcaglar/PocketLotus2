/* Own-player view for two linked consoles.

   In the game's two-player mode the race frame routine (&16CC4 onwards) draws
   player 1's view into screen lines 0-95 (calls at &16D74-&16DD0), then, if the
   two-player flag ip+&5BB is set (test at &16DD4), player 2's view into lines
   104-199 (&16DE0-&16E3C: the same routines duplicated for player 2's data,
   which add &4100 bytes, 104 lines, to the screen pointer ip+&C). The view
   height ip+&E0 is 96 in two-player mode and 200 in one-player mode, and the
   drawing routines take their geometry from it, plus a depth-to-line table
   built at race start.

   With two consoles in lockstep the game logic stays in two-player mode on both.
   Only drawing differs: the host draws player 1's view and the joining console
   player 2's, each 200 lines high from line 0, which is the one-player layout.
   Three hook SWIs replace instructions in the race frame routine; each hook
   performs the instruction it replaced:
     &16D74 STMDB sp!,{pc}       start of drawing: switch to the full-height view
     &16DD4 LDRB lr,[ip,#&5BB]   before player 2's drawing: skip it on the host
     &16E40 STMDB sp!,{pc}       end of the per-player drawing: restore the view;
                                 then the raster palette list (&18230) is built
                                 for the drawn player only, as a one-player list
     &16E4C STMDB sp!,{pc}       after the list: restore the two-player flag
   Everything the hooks change is restored before the game logic runs again.

   Timing. The game runs a frame as: logic, drawing, wait for VSync, swap banks,
   wait for the next VSync. The VSync handler samples both players' keys, so on
   which emulated frame the logic runs decides the input it sees. Drawing one
   full-height view does not cost the same as the other console's view, so the
   drawing is taken out of emulated time: the clock stops from the start hook to
   the end of the raster list, and the after hook then spins for a fixed
   DRAW_CYCLES, servicing interrupts as a real busy CPU would. Both consoles so
   reach every VSync at the same point of the game, and their games stay
   identical (checked by the link's state hash). DRAW_CYCLES is the average cost
   of the original two-view drawing, which keeps the game's own speed. */
#include <stdlib.h>
#include "machine.h"

#define HOOK_START 0x00016D74u
#define HOOK_P2    0x00016DD4u
#define HOOK_END   0x00016E40u
#define HOOK_AFTER 0x00016E4Cu
#define CALL_WORD  0xE92D8000u          /* STMDB sp!,{pc} */
#define FLAG_WORD  0xE5DCE5BBu          /* LDRB lr,[ip,#&5BB] */
#define FLAG_2P    0x5BB
#define VIEW_H     0xE0
#define SCREEN_PTR 0x0C
#define P2_OFFSET  0x4100
#define FULL_H     200
#define DRAW_CYCLES 200000  /* average cost of the original two-view drawing, measured */

/* Depth-to-screen-line table, 128 halfwords, built at race start as
   f(depth) + view height - 56 (&13EE0-&13F68). A taller view moves every entry
   down by the height difference. */
#define LINE_TABLE 0x00029738u
#define LINE_TABLE_ENTRIES 128

/* Raster palette list input (&18230): per player a count of entries (ip+&1C0,
   ip+&1C4) and a table of line/colour pairs (&2A020, &2A070). Player 2's list is
   placed 104 lines down; for the joining console its data takes player 1's
   place while the list is built. */
#define RASTER_COUNT1 0x1C0
#define RASTER_COUNT2 0x1C4
#define RASTER_TABLE1 0x0002A020u
#define RASTER_TABLE2 0x0002A070u
#define RASTER_TABLE_BYTES 0x50

static uint32_t saved_height;
static int32_t stall;                    /* fixed drawing time still to spend */
static int stalling;
static uint64_t draw_start, draw_total, draw_count;
static int stat = -1;
static uint8_t saved_flag;
static int active;                       /* this frame's drawing is timed by the hooks */
static int own;                          /* and drawn as this console's own view */

static void shift_line_table(int by)
{
    for (unsigned i = 0; i < LINE_TABLE_ENTRIES; i++) {
        uint32_t a = LINE_TABLE + 2 * i;
        uint32_t v = (bus_read8(a) | (bus_read8(a + 1) << 8)) + (uint32_t)by;
        bus_write8(a, v & 0xFF);
        bus_write8(a + 1, (v >> 8) & 0xFF);
    }
}

int view_patch_ok(void)
{
    return bus_read32(HOOK_START) == CALL_WORD && bus_read32(HOOK_P2) == FLAG_WORD &&
           bus_read32(HOOK_END) == CALL_WORD && bus_read32(HOOK_AFTER) == CALL_WORD;
}

/* Called once the program has been unpacked into memory: install the hooks. The
   recompiler applies the same three words to its copy of the program. */
void view_patch(void)
{
    if (!view_patch_ok()) { host_log("view: program differs from the expected version, hooks not installed\n"); return; }
    bus_write32(HOOK_START, 0xEF000000u | SWI_VIEW_START);
    bus_write32(HOOK_P2, 0xEF000000u | SWI_VIEW_P2);
    bus_write32(HOOK_END, 0xEF000000u | SWI_VIEW_END);
    bus_write32(HOOK_AFTER, 0xEF000000u | SWI_VIEW_AFTER);
}

static void swap_raster(uint32_t ip)
{
    uint32_t c1 = bus_read32(ip + RASTER_COUNT1);
    bus_write32(ip + RASTER_COUNT1, bus_read32(ip + RASTER_COUNT2));
    bus_write32(ip + RASTER_COUNT2, c1);
    for (uint32_t i = 0; i < RASTER_TABLE_BYTES; i++) {
        uint8_t a = bus_read8(RASTER_TABLE1 + i);
        bus_write8(RASTER_TABLE1 + i, bus_read8(RASTER_TABLE2 + i));
        bus_write8(RASTER_TABLE2 + i, a);
    }
}

/* STMDB sp!,{pc} at `at`: ARM2 stores the instruction address + 12 with the PSR. */
static void push_return(arm26_t *cpu, uint32_t at)
{
    cpu->r[13] -= 4;
    bus_write32(cpu->r[13], ((at + 12) & PC_MASK) | (cpu->psr & (PSR_FLAGS | PSR_I | PSR_F | PSR_MODE)));
}

void view_hook(arm26_t *cpu, uint32_t swi)
{
    uint32_t ip = cpu->r[12];
    if (swi == SWI_VIEW_START) {
        active = M.view_player != 0 && bus_read8(ip + FLAG_2P) != 0;
        draw_start = machine_now(cpu);
        if (active) {
            M.frozen = 1;
            M.freeze_at = draw_start;
        }
        /* --view 3 keeps the timing but draws both views: a reference for tests */
        own = active && (M.view_player == 1 || M.view_player == 2);
        if (own) {
            saved_height = bus_read32(ip + VIEW_H);
            bus_write32(ip + VIEW_H, FULL_H);
            shift_line_table(FULL_H - (int)saved_height);
            if (M.view_player == 2) {
                /* player 2's routines add &4100 to the screen pointer: let them start at
                   line 0, and skip player 1's drawing */
                bus_write32(ip + SCREEN_PTR, bus_read32(ip + SCREEN_PTR) - P2_OFFSET);
                cpu->pc = HOOK_P2 + 4;
                cpu->r[14] = bus_read8(ip + FLAG_2P);
                return;
            }
        }
        push_return(cpu, HOOK_START);
    } else if (swi == SWI_VIEW_P2) {
        cpu->r[14] = bus_read8(ip + FLAG_2P);
        if (own && M.view_player == 1) cpu->pc = HOOK_END;     /* the host does not draw player 2 */
    } else if (swi == SWI_VIEW_END) {
        if (own) {
            shift_line_table((int)saved_height - FULL_H);
            bus_write32(ip + VIEW_H, saved_height);
            saved_flag = bus_read8(ip + FLAG_2P);
            bus_write8(ip + FLAG_2P, 0);
            if (M.view_player == 2) {
                bus_write32(ip + SCREEN_PTR, bus_read32(ip + SCREEN_PTR) + P2_OFFSET);
                swap_raster(ip);
            }
        }
        push_return(cpu, HOOK_END);
    } else {
        if (!stalling) {
            if (stat < 0) stat = getenv("LOTUS_VIEWSTAT") != NULL;
            if (stat && bus_read8(ip + FLAG_2P)) {
                draw_total += machine_now(cpu) - draw_start;
                if (++draw_count % 500 == 0)
                    host_log("view: drawing takes %llu cycles a frame on average\n", (unsigned long long)(draw_total / draw_count));
            }
            if (own) {
                bus_write8(ip + FLAG_2P, saved_flag);
                if (M.view_player == 2) swap_raster(ip);
                own = 0;
            }
            if (active) {
                active = 0;
                M.time_refund += (int32_t)(machine_now(cpu) - M.freeze_at);
                M.frozen = 0;
                stall = DRAW_CYCLES;
                stalling = 1;
            }
        }
        if (stalling) {
            /* spin here, re-running this hook, until the fixed drawing time is spent */
            int32_t spend = cpu->cycles < stall ? cpu->cycles : stall;
            if (spend > 0) { cpu->cycles -= spend; stall -= spend; }
            if (stall > 0) { cpu->pc = HOOK_AFTER; return; }
            stalling = 0;
        }
        push_return(cpu, HOOK_AFTER);
    }
}

/* Memory the drawing writes, which differs between two linked consoles drawing
   different views (found by comparing own-view runs with the timed two-view run
   through a whole race). The game logic never reads it back into game state, so
   the lockstep hash leaves it out. */
static const struct { uint32_t lo, hi; } view_scratch[] = {
    { 0x0000A000u, 0x0000C300u },        /* drawing code, modified as it draws */
    { 0x0000E000u, 0x0000E800u },        /* line buffers */
    { 0x0001D1ECu, 0x0001D254u },        /* ip+&10C..&173: per-view camera */
    { 0x0001D29Cu, 0x0001D2A8u },        /* ip+&1BC..&1C7: raster counts */
    { 0x0001D2D8u, 0x0001D324u },        /* ip+&1F8..&243 */
    { 0x0001D424u, 0x0001D428u },        /* player 1 view fields */
    { 0x0001D448u, 0x0001D464u },
    { 0x0001D4C4u, 0x0001D4C8u },
    { 0x0001D594u, 0x0001D598u },        /* player 2 view fields */
    { 0x0001D5B8u, 0x0001D5D4u },
    { 0x0001D634u, 0x0001D680u },
    { 0x00021540u, 0x00021588u },
    { 0x00022BC0u, 0x00023840u },        /* projected road and scenery */
    { 0x00029730u, 0x00029738u },
    { 0x00029FF8u, 0x0002A090u },        /* raster tables */
    { 0x0002B890u, 0x0002B910u },
};

uint32_t view_lockstep_hash(void)
{
    uint32_t h = 2166136261u;
    h = (h ^ M.cpu.pc) * 16777619u;
    uint32_t a = APP_BASE;
    for (size_t k = 0; k <= sizeof view_scratch / sizeof view_scratch[0]; k++) {
        uint32_t end = k < sizeof view_scratch / sizeof view_scratch[0] ? view_scratch[k].lo : 0x70000u;
        for (; a < end; a += 4) h = (h ^ bus_read32(a)) * 16777619u;
        if (k < sizeof view_scratch / sizeof view_scratch[0]) a = view_scratch[k].hi;
    }
    return h;
}
