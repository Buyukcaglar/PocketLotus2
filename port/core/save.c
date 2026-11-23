/* What the game would keep between sessions if it could: the high score table,
   the player names and the password, and the options menu settings. The original
   keeps them in memory only. This copies them to and from a small block that the
   front end stores in a save file.

   All of them are initialised data in the program image, so they are put back
   once the program has started, after its start-up code (&128D8) has set the
   accelerate and control options of both players to their defaults. */
#include <string.h>
#include "machine.h"

#define TABLE        0x2B0ABu   /* "todays best scores......" and ten "1st nigel..... 50000000" lines, as text */
#define TABLE_LEN    0x125u     /* up to the course names that follow it */
#define OPTIONS      0x2B33Cu   /* per player: +1 gears (1 automatic), +2 accelerate, +3 control; +5 two players */
#define NAMES        0x2B425u   /* player 1, player 2, password: 12 letters and a terminator each */
#define NAMES_LEN    39u
#define CONTROL_FLAGS 0x1D6ACu  /* copies of the two control options the game keeps (&F08C) */

static const uint8_t option_offsets[] = { 1, 2, 3, 5, 9, 10, 11 };

#define SAVE_MAGIC "PL2S"
#define SAVE_VERSION 1
enum { OFF_TABLE = 5, OFF_OPTIONS = OFF_TABLE + TABLE_LEN, OFF_NAMES = OFF_OPTIONS + sizeof option_offsets,
       OFF_SUM = OFF_NAMES + NAMES_LEN };
_Static_assert(OFF_SUM + 4 == SAVE_SIZE, "SAVE_SIZE");

static uint32_t checksum(const uint8_t *p, unsigned n)
{
    uint32_t s = 0x4C324E53u;
    while (n--) s = (s << 5 | s >> 27) ^ *p++;
    return s;
}

static int text_ok(const uint8_t *p, unsigned n)
{
    for (unsigned i = 0; i < n; i++)
        if (p[i] && (p[i] < 32 || p[i] > 126)) return 0;
    return 1;
}

/* the program in memory is the one this layout was taken from */
static int layout_ok(void)
{
    return !memcmp(guest_ptr(TABLE), "todays best scores", 18) &&
           !memcmp(guest_ptr(TABLE + TABLE_LEN), "forest course", 13) &&
           !memcmp(guest_ptr(NAMES - 10), "ply1\0ply2\0", 10);
}

int save_game_ready(void)
{
    return M.view_patched && bus_read8(CONTROL_FLAGS) != 0 && layout_ok();
}

void save_capture(uint8_t out[SAVE_SIZE])
{
    memcpy(out, SAVE_MAGIC, 4);
    out[4] = SAVE_VERSION;
    memcpy(out + OFF_TABLE, guest_ptr(TABLE), TABLE_LEN);
    for (unsigned i = 0; i < sizeof option_offsets; i++) out[OFF_OPTIONS + i] = bus_read8(OPTIONS + option_offsets[i]);
    memcpy(out + OFF_NAMES, guest_ptr(NAMES), NAMES_LEN);
    uint32_t s = checksum(out, OFF_SUM);
    memcpy(out + OFF_SUM, &s, 4);
}

int save_apply(const uint8_t in[SAVE_SIZE])
{
    uint32_t s;
    memcpy(&s, in + OFF_SUM, 4);
    if (memcmp(in, SAVE_MAGIC, 4) || in[4] != SAVE_VERSION || s != checksum(in, OFF_SUM) || !layout_ok()) return 0;
    if (memcmp(in + OFF_TABLE, "todays best scores", 18) || !text_ok(in + OFF_TABLE, TABLE_LEN) ||
        !text_ok(in + OFF_NAMES, NAMES_LEN))
        return 0;
    for (unsigned i = 0; i < 3; i++)                /* each name ends in its terminator */
        if (in[OFF_NAMES + 13 * i + 12]) return 0;
    for (unsigned i = 0; i < sizeof option_offsets; i++)
        if (in[OFF_OPTIONS + i] > 1) return 0;
    memcpy(guest_ptr(TABLE), in + OFF_TABLE, TABLE_LEN);
    for (unsigned i = 0; i < sizeof option_offsets; i++) bus_write8(OPTIONS + option_offsets[i], in[OFF_OPTIONS + i]);
    memcpy(guest_ptr(NAMES), in + OFF_NAMES, NAMES_LEN);
    bus_write8(CONTROL_FLAGS, bus_read8(OPTIONS + 3));
    bus_write8(CONTROL_FLAGS + 1, bus_read8(OPTIONS + 11));
    return 1;
}
