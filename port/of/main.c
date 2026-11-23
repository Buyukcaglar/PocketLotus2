/* Lotus Turbo Challenge 2 on openfpgaOS: Pocket (and SDK desktop) front end. */
#include "of.h"
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include "machine.h"
#include "pack.h"
#include "link.h"
#ifdef LOTUS_RECOMP
#include "recomp_rt.h"
#endif

#define PACK_SLOT 4
#define PACK_NAME "lotus2.dat"

/* RISC OS internal key numbers the game polls: the default key sets of the two
   players (found by probing the options menu and the race), Escape and F1. */
enum { KEY_FIRE = 5, KEY_DOWN = 50, KEY_UP = 51, KEY_RIGHT = 66, KEY_LEFT = 97,
       KEY2_FIRE = 8, KEY2_DOWN = 79, KEY2_UP = 88, KEY2_LEFT = 102, KEY2_RIGHT = 103,
       KEY_ESCAPE = 112, KEY_F1 = 113 };

/* Sound is kept about 60 ms ahead of the speaker. The game makes one frame (20 ms)
   of sound per frame; with nothing more queued, any late frame empties the
   output and the gap is heard as a crackle. */
#define AUDIO_TARGET 2880                   /* stereo pairs queued, 3 frames at 48 kHz */
static int audio_capacity;
static int16_t audio[1024 * 2];
static int16_t silence[AUDIO_TARGET * 2];

static void play_sound(void)
{
    int queued = audio_capacity - of_audio_free();
    if (queued < 0) queued = 0;
    /* start, or recovery after a stall (loading, boot): refill the margin with silence */
    if (queued < AUDIO_TARGET / 3) {
        of_audio_write(silence, AUDIO_TARGET - queued);
        queued = AUDIO_TARGET;
    }
    /* The display and the audio clock never run at exactly the same speed. Make
       slightly more or fewer output samples (at most 1 %, not audible) so the
       queue stays near the target instead of slowly emptying or growing. */
    int adjust = (AUDIO_TARGET - queued) / 8;
    if (adjust > OF_AUDIO_RATE / 100) adjust = OF_AUDIO_RATE / 100;
    if (adjust < -OF_AUDIO_RATE / 100) adjust = -OF_AUDIO_RATE / 100;
    unsigned frames = sound_read(audio, 1024, (unsigned)(OF_AUDIO_RATE + adjust));
    if (frames) of_audio_write(audio, (int)frames);
}

static int out_w = SCREEN_W, out_h = SCREEN_H, out_stride = SCREEN_W * 2;
static unsigned bench_frames;         /* scripted session length, 0 in normal play */
static int display_is_50hz;           /* the display refresh matches the game: flips can pace it */

void host_log(const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    vprintf(fmt, ap);
    va_end(ap);
}

int host_load_file(const char *guest_name, uint32_t load_addr, uint32_t *size)
{
    return pack_load(guest_name, load_addr, size);
}

int host_file_size(const char *guest_name, uint32_t *size)
{
    return pack_find(guest_name, size) != NULL;
}

static void fatal(const char *msg)
{
    of_video_set_display_mode(OF_DISPLAY_TERMINAL);
    printf("\nPocketLotus: %s\n", msg);
    for (;;) usleep(100000);
}

static void load_pack(void)
{
#ifndef OF_PC
    /* the SDK simulator serves slots from its app profile and has no registry service */
    if (!bench_frames) of_file_slot_register(PACK_SLOT, PACK_NAME);
#endif
    FILE *f = fopen(PACK_NAME, "rb");
    if (!f) fatal("cannot open " PACK_NAME " (build it with tools/lotus/pack.py)");
    fseek(f, 0, SEEK_END);
    long size = ftell(f);
    fseek(f, 0, SEEK_SET);
    uint8_t *data = malloc((size_t)size);
    if (!data || fread(data, 1, (size_t)size, f) != (size_t)size) fatal("cannot read " PACK_NAME);
    fclose(f);
    if (!pack_attach(data, (uint32_t)size)) fatal(PACK_NAME " is not a Lotus asset pack");
}

static void video_refresh_50hz(void)
{
    of_video_set_refresh_vtotal(OF_VIDEO_VTOTAL_50HZ);
}

static void video_setup(void)
{
    of_video_mode_t mode = { SCREEN_W, SCREEN_H, 0, OF_VIDEO_MODE_RGB565, 0 }, got;
    of_video_init();
    if (of_video_set_mode(&mode) != 0) {
        /* no 320x256 source mode: show the middle 240 lines */
        mode.height = 240;
        if (of_video_set_mode(&mode) != 0) of_video_set_color_mode(OF_VIDEO_MODE_RGB565);
    }
    of_video_get_mode(&got);
    if (got.width) { out_w = got.width; out_h = got.height; out_stride = got.stride; }
    else { out_h = 240; }
    of_video_set_display_mode(OF_DISPLAY_FRAMEBUFFER);
    of_audio_init();
    audio_capacity = of_audio_free();       /* the whole ring while nothing plays */
}

static void present(void)
{
    uint8_t *fb = (uint8_t *)of_video_surface16();
    int skip = (SCREEN_H - out_h) / 2;
    if (skip < 0) skip = 0;
    if (out_w >= SCREEN_W) machine_render_565((uint16_t *)fb, (unsigned)out_stride, (unsigned)skip, (unsigned)out_h, 1);
    play_sound();
#ifdef OF_PC
    /* desktop self-test: LOTUS_SHOT=frames writes the presented picture and exits */
    static int shot = -1, count;
    if (shot < 0) { const char *e = getenv("LOTUS_SHOT"); shot = e ? atoi(e) : 0; }
    if (shot && ++count == shot) {
        FILE *f = fopen("lotus_shot.ppm", "wb");
        if (!f) exit(1);
        fprintf(f, "P6\n%d %d\n255\n", out_w, out_h);
        for (int y = 0; y < out_h; y++)
            for (int x = 0; x < out_w; x++) {
                unsigned v = ((uint16_t *)(fb + (size_t)y * out_stride))[x];
                fputc((v >> 11) << 3, f); fputc(((v >> 5) & 63) << 2, f); fputc((v & 31) << 3, f);
            }
        fclose(f);
        exit(0);
    }
#endif
    of_video_flip();
    if (display_is_50hz && !bench_frames) of_video_wait_flip();
}

/* The game is a 50 Hz program: one frame of it is 20 ms of game time and of sound.
   The clock decides when the next frame runs, so speed and music tempo are right
   on any display. Where the display itself runs at 50 Hz the flip in present()
   already waits for it and this returns at once. */
#define FRAME_US 20000u

static void pace(void)
{
    static uint32_t due;
    static int started;
    uint32_t now = of_time_us();
    if (!started || (int32_t)(now - due) > 5 * (int32_t)FRAME_US) { due = now; started = 1; }   /* (re)start after a stall */
    due += FRAME_US;
    while ((int32_t)(due - (now = of_time_us())) > 0) {
        uint32_t left = due - now;
        if (left > 2000) usleep(left - 1000);
    }
}

/* Time a few flips to learn whether the display refresh is the game's 50 Hz. */
static void measure_display(void)
{
    uint32_t t0, t1;
    of_video_flip(); of_video_wait_flip();
    t0 = of_time_us();
    for (int i = 0; i < 8; i++) { of_video_flip(); of_video_wait_flip(); }
    t1 = of_time_us();
    uint32_t period = (t1 - t0) / 8;
    display_is_50hz = period > 19000 && period < 21000;
    printf("display period %u us: %s\n", (unsigned)period, display_is_50hz ? "pacing by flips" : "pacing by clock");
}

/* One pad as 16 bits, the unit that crosses the link cable. */
enum { IN_UP = 1, IN_DOWN = 2, IN_LEFT = 4, IN_RIGHT = 8, IN_FIRE = 16, IN_GEAR_UP = 32, IN_GEAR_DOWN = 64,
       IN_SKIP = 128, IN_ESCAPE = 256 };

/* "bench N" on the command line (ARGS= in the .ini) replaces the pad with a fixed
   session for N frames: attract sequence, options menu, then a race. It gives the
   SDK simulator, and timing runs on the device, a repeatable workload. */
static const struct { unsigned frame; uint16_t bits; } bench_script[] = {
    { 450, IN_FIRE }, { 470, 0 }, { 600, IN_DOWN }, { 610, 0 }, { 700, IN_FIRE }, { 720, 0 },
    { 1300, IN_FIRE }, { 1400, IN_FIRE | IN_GEAR_UP }, { 1404, IN_FIRE }, { 2000, IN_FIRE | IN_LEFT },
    { 2040, IN_FIRE }, { 2400, IN_FIRE | IN_RIGHT }, { 2440, IN_FIRE },
};
/* Linked bench runs (desktop link test): the host selects two players and drives
   player 1, the joining console drives player 2 and steers right for a while. */
static const struct { unsigned frame; uint16_t bits; } link_host_script[] = {
    { 450, IN_FIRE }, { 470, 0 }, { 600, IN_UP }, { 610, 0 }, { 650, IN_FIRE }, { 660, 0 }, { 700, IN_DOWN },
    { 710, 0 }, { 750, IN_DOWN }, { 760, 0 }, { 800, IN_FIRE }, { 820, 0 }, { 1300, IN_FIRE },
};
static const struct { unsigned frame; uint16_t bits; } link_join_script[] = {
    { 1300, IN_FIRE }, { 1500, IN_FIRE | IN_RIGHT }, { 1560, IN_FIRE },
};
static uint16_t bench_bits;
/* "bench N view P": the linked two-player race on one console, both scripts, drawn
   as console P's own view; a CPU load test of linked play for the simulator */
static int bench_view;

static uint16_t pad_bits(int player)
{
    int (*btn)(uint32_t) = player ? of_btn_p2 : of_btn;
    return (uint16_t)((btn(OF_BTN_UP) ? IN_UP : 0) | (btn(OF_BTN_DOWN) ? IN_DOWN : 0) |
                      (btn(OF_BTN_LEFT) ? IN_LEFT : 0) | (btn(OF_BTN_RIGHT) ? IN_RIGHT : 0) |
                      (btn(OF_BTN_A) || btn(OF_BTN_B) ? IN_FIRE : 0) | (btn(OF_BTN_R1) ? IN_GEAR_UP : 0) |
                      (btn(OF_BTN_L1) ? IN_GEAR_DOWN : 0) | (btn(OF_BTN_X) || btn(OF_BTN_START) ? IN_SKIP : 0) |
                      (btn(OF_BTN_SELECT) ? IN_ESCAPE : 0));
}

/* This console's own input for the frame: player 1's pad, or the bench script. */
static uint16_t local_input(unsigned frame)
{
    if (bench_frames) {
        if (link_role() == LINK_HOST) {
            for (unsigned i = 0; i < sizeof link_host_script / sizeof link_host_script[0]; i++)
                if (link_host_script[i].frame == frame) bench_bits = link_host_script[i].bits;
        } else if (link_role() == LINK_JOIN) {
            for (unsigned i = 0; i < sizeof link_join_script / sizeof link_join_script[0]; i++)
                if (link_join_script[i].frame == frame) bench_bits = link_join_script[i].bits;
        } else {
            for (unsigned i = 0; i < sizeof bench_script / sizeof bench_script[0]; i++)
                if (bench_script[i].frame == frame) bench_bits = bench_script[i].bits;
        }
        return bench_bits;
    }
    of_input_poll();
    return pad_bits(0);
}

/* Player 1 and player 2 inputs to the game's keys. Both players' default key sets
   are used; gear changes are up and down. Skip and Escape come from either. */
static void apply_input(uint16_t p1, uint16_t p2)
{
    M.keys[KEY_UP] = (p1 & (IN_UP | IN_GEAR_UP)) != 0;
    M.keys[KEY_DOWN] = (p1 & (IN_DOWN | IN_GEAR_DOWN)) != 0;
    M.keys[KEY_LEFT] = (p1 & IN_LEFT) != 0;
    M.keys[KEY_RIGHT] = (p1 & IN_RIGHT) != 0;
    M.keys[KEY_FIRE] = (p1 & IN_FIRE) != 0;
    M.keys[KEY2_UP] = (p2 & (IN_UP | IN_GEAR_UP)) != 0;
    M.keys[KEY2_DOWN] = (p2 & (IN_DOWN | IN_GEAR_DOWN)) != 0;
    M.keys[KEY2_LEFT] = (p2 & IN_LEFT) != 0;
    M.keys[KEY2_RIGHT] = (p2 & IN_RIGHT) != 0;
    M.keys[KEY2_FIRE] = (p2 & IN_FIRE) != 0;
    M.keys[KEY_ESCAPE] = ((p1 | p2) & IN_ESCAPE) != 0;
    M.keys[KEY_F1] = ((p1 | p2) & IN_SKIP) != 0;
    M.pad = (p1 & IN_UP ? PAD_UP : 0) | (p1 & IN_DOWN ? PAD_DOWN : 0) | (p1 & IN_LEFT ? PAD_LEFT : 0) |
            (p1 & IN_RIGHT ? PAD_RIGHT : 0) | (p1 & IN_FIRE ? PAD_FIRE : 0);
}

static void read_input(unsigned frame)
{
    uint16_t mine = local_input(frame), p1, p2;
    if (link_active()) {
        link_exchange(frame, mine, &p1, &p2);
    } else if (bench_frames && bench_view) {
        p1 = p2 = 0;                               /* each script's latest entry so far */
        for (unsigned i = 0; i < sizeof link_host_script / sizeof link_host_script[0]; i++)
            if (link_host_script[i].frame <= frame) p1 = link_host_script[i].bits;
        for (unsigned i = 0; i < sizeof link_join_script / sizeof link_join_script[0]; i++)
            if (link_join_script[i].frame <= frame) p2 = link_join_script[i].bits;
    } else {
        p1 = mine;
        p2 = bench_frames ? 0 : pad_bits(1);       /* a second pad on the dock plays as player 2 */
    }
    apply_input(p1, p2);
}

/* Hash of the game state that matters for lockstep: the program counter and the
   game's memory, less what each console's own-view drawing writes (view.c). */
static uint32_t state_hash(void)
{
    return view_lockstep_hash();
}

/* Link role: hold L while the core starts to host (player 1), R to join (player 2).
   On the desktop, LOTUS_LINK=host or LOTUS_LINK=join. */
static int choose_link_role(void)
{
#ifdef OF_PC
    const char *e = getenv("LOTUS_LINK");
    if (e && !strcmp(e, "host")) return LINK_HOST;
    if (e && !strcmp(e, "join")) return LINK_JOIN;
    return LINK_OFF;
#else
    if (bench_frames) return LINK_OFF;
    of_input_poll();
    if (of_btn(OF_BTN_L1)) return LINK_HOST;
    if (of_btn(OF_BTN_R1)) return LINK_JOIN;
    return LINK_OFF;
#endif
}

int main(int argc, char **argv)
{
    uint32_t size;
    for (int i = 1; i + 1 < argc; i++)
        if (!strcmp(argv[i], "bench")) bench_frames = (unsigned)atoi(argv[i + 1]);
        else if (!strcmp(argv[i], "view")) bench_view = atoi(argv[i + 1]);
    video_setup();
    if (!bench_frames) video_refresh_50hz();
    load_pack();
    machine_init();
#ifdef LOTUS_RECOMP
    hybrid_install();
#endif
    if (!pack_load("boot.stub", 0x70000, &size) || !pack_load("boot.packed", 0x8000, &size))
        fatal("asset pack has no boot images");
    M.cpu.pc = 0x70000;
    M.cpu.r[13] = APP_LIMIT;

    int role = choose_link_role();
    /* linked: each console draws its own player's view, full screen (core/view.c) */
    if (role != LINK_OFF && link_start(role, 30000)) M.view_player = (role == LINK_HOST) ? 1 : 2;
    else if (bench_frames && bench_view) M.view_player = bench_view;
    if (!bench_frames) measure_display();
    uint32_t t0 = bench_frames ? 0 : of_time_ms();
    for (unsigned frame = 0; !M.fatal; frame++) {
        read_input(frame);
        machine_run_frame();
        if (link_active() && frame % LINK_CHECK_FRAMES == LINK_CHECK_FRAMES - 1) link_check(frame, state_hash());
        present();
        if (!bench_frames) pace();
        if (!bench_frames && (frame % 250) == 249) {   /* the simulator measures bench runs itself */
            uint32_t t1 = of_time_ms();
            printf("250 frames in %u ms\n", (unsigned)(t1 - t0));
            t0 = t1;
        }
        if (bench_frames && frame + 1 == bench_frames) {
            printf("BENCH DONE %u frames\n", bench_frames);
            bench_frames = 0;                 /* hand the pad back */
            bench_bits = 0;
        }
    }
    fatal("the game stopped (see console log)");
    return 0;
}
