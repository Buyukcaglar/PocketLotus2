/* Instruction-count benchmark: the Pocket build of the game (same compiler, same
   flags, same generated code) on QEMU's bare RISC-V "virt" machine. QEMU runs with
   -icount shift=0, so its timer advances 1 ns per executed instruction and the
   CLINT mtime register (10 MHz) counts instructions in units of 100. The result is
   instructions per game frame, split into game logic and display conversion. */
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

#include "machine.h"
#include "pack.h"
#include "recomp_rt.h"

#ifndef BENCH_FRAMES
#define BENCH_FRAMES 3000
#endif

extern const uint8_t pack_image[], pack_image_end[];
extern char _heap_start[];

#define UART (*(volatile uint8_t *)0x10000000u)
#define MTIME (*(volatile uint64_t *)0x0200BFF8u)

/* newlib system calls */
void *_sbrk(ptrdiff_t n) { static char *brk = _heap_start; char *p = brk; brk += n; return p; }
int _write(int fd, const char *p, int n) { (void)fd; for (int i = 0; i < n; i++) UART = (uint8_t)p[i]; return n; }
int _read(int fd, char *p, int n) { (void)fd; (void)p; (void)n; return 0; }
int _close(int fd) { (void)fd; return -1; }
int _fstat(int fd, struct stat *st) { (void)fd; st->st_mode = S_IFCHR; return 0; }
int _isatty(int fd) { (void)fd; return 1; }
int _lseek(int fd, int o, int w) { (void)fd; (void)o; (void)w; return 0; }
int _kill(int p, int s) { (void)p; (void)s; return -1; }
int _getpid(void) { return 1; }
void _exit(int c) { (void)c; *(volatile uint32_t *)0x100000u = 0x5555; for (;;) { } }

void host_log(const char *fmt, ...) { (void)fmt; }
int host_load_file(const char *name, uint32_t addr, uint32_t *size) { return pack_load(name, addr, size); }
int host_file_size(const char *name, uint32_t *size) { return pack_find(name, size) != NULL; }

static uint64_t insns(void) { return MTIME * 100u; }

/* the scripted race of docs/PORT_BUILD.md */
static const struct { unsigned frame; char kind; unsigned key; } script[] = {
    { 450, 'k', 8 }, { 470, 'u', 8 }, { 600, 'k', 50 }, { 610, 'u', 50 }, { 700, 'k', 8 }, { 720, 'u', 8 },
    { 1300, 'k', 8 }, { 2000, 'k', 97 }, { 2040, 'u', 97 }, { 2400, 'k', 66 }, { 2440, 'u', 66 },
};

static uint16_t fb[SCREEN_W * SCREEN_H];
static int16_t audio[1024 * 2];

int main(void)
{
    uint32_t size;
    unsigned frames = BENCH_FRAMES, window = 250;
    machine_init();
    hybrid_install();
    if (!pack_attach(pack_image, (uint32_t)(pack_image_end - pack_image))) { printf("bad pack\n"); return 1; }
    pack_load("boot.stub", 0x70000, &size);
    pack_load("boot.packed", 0x8000, &size);
    M.cpu.pc = 0x70000;
    M.cpu.r[13] = APP_LIMIT;
    printf("frames      game  display+sound  worst game frame   (RISC-V instructions per frame)\n");
    uint64_t game = 0, video = 0, worst = 0;
    for (unsigned f = 0; f < frames && !M.fatal; f++) {
        for (unsigned i = 0; i < sizeof script / sizeof script[0]; i++)
            if (script[i].frame == f) M.keys[script[i].key] = (script[i].kind == 'k');
        uint64_t t0 = insns();
        machine_run_frame();
        uint64_t t1 = insns();
        machine_render_565(fb, SCREEN_W * 2, 0, SCREEN_H, 1);
        sound_read(audio, 1024, 48000);
        uint64_t t2 = insns();
        game += t1 - t0;
        video += t2 - t1;
        if (t1 - t0 > worst) worst = t1 - t0;
        if ((f + 1) % window == 0) {
            printf("%5u %10lu %10lu %12lu\n", f + 1, (unsigned long)(game / window), (unsigned long)(video / window),
                   (unsigned long)worst);
            game = video = worst = 0;
        }
    }
    printf("done%s, fallback steps %lu\n", M.fatal ? " (fatal)" : "", (unsigned long)hybrid_fallback_steps);
    return 0;
}
