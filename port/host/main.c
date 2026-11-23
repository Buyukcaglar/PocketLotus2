/* Headless host runner: executes the unpacked program and dumps frames. */
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../core/machine.h"
#ifdef LOTUS_RECOMP
#include "../core/recomp_rt.h"
extern uint32_t hybrid_fallback_log[];
extern unsigned hybrid_fallback_logged;
#endif

#ifdef ARM26_COVERAGE
extern uint8_t cov_map[];
extern int cov_armed;
extern unsigned cov_write_hits, cov_exec_hits;
#endif

static const char *roots[] = {
    "analysis/media/F1023201/extracted/!LOTUS",
    "analysis/media/F1023202/extracted",
    "analysis/media/F1023201/extracted",
    NULL
};

void host_log(const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    vfprintf(stderr, fmt, ap);
    va_end(ap);
}

static FILE *open_guest(const char *guest_name)
{
    char rel[160], path[320];
    const char *p = guest_name;
    const char *close = strchr(p, '>');
    size_t n = 0;
    if (p[0] == '<' && close) p = close + 1;
    while (*p == '.' || *p == '$' || *p == ':') p++;
    for (; *p && n + 1 < sizeof rel; p++) rel[n++] = (*p == '.') ? '/' : *p;
    rel[n] = 0;
    for (int i = 0; roots[i]; i++) {
        snprintf(path, sizeof path, "%s/%s", roots[i], rel);
        FILE *f = fopen(path, "rb");
        if (f) return f;
    }
    return NULL;
}

int host_file_size(const char *guest_name, uint32_t *size)
{
    FILE *f = open_guest(guest_name);
    if (!f) return 0;
    fseek(f, 0, SEEK_END);
    *size = (uint32_t)ftell(f);
    fclose(f);
    return 1;
}

int host_load_file(const char *guest_name, uint32_t load_addr, uint32_t *size)
{
    FILE *f = open_guest(guest_name);
    if (!f) return 0;
    uint32_t room = GUEST_RAM_SIZE - (load_addr & (GUEST_RAM_SIZE - 1));
    *size = (uint32_t)fread(guest_ptr(load_addr), 1, room < 0x100000 ? room : 0x100000, f);
    fclose(f);
    return 1;
}

static int load_raw(const char *path, uint32_t addr)
{
    FILE *f = fopen(path, "rb");
    if (!f) { fprintf(stderr, "cannot open %s (run tools/lotus/unpack.py)\n", path); return 0; }
    size_t n = fread(guest_ptr(addr), 1, 0x100000, f);
    fclose(f);
    return n > 0;
}

/* FNV-1a over CPU state and the memory the game owns: one value per frame. */
static uint32_t state_hash(void)
{
    uint32_t h = 2166136261u;
#define MIX(ptr, len) do { const uint8_t *p_ = (const uint8_t *)(ptr); \
    for (size_t i_ = 0; i_ < (size_t)(len); i_++) h = (h ^ p_[i_]) * 16777619u; } while (0)
    MIX(M.cpu.r, 15 * 4);
    MIX(&M.cpu.pc, 4);
    MIX(&M.cpu.psr, 4);
    MIX(M.cpu.bank_usr, sizeof M.cpu.bank_usr);
    MIX(M.cpu.bank_irq, sizeof M.cpu.bank_irq);
    MIX(M.cpu.bank_svc, sizeof M.cpu.bank_svc);
    MIX(guest_ptr(0), APP_LIMIT);
    MIX(guest_ptr(SCREEN_BASE), SCREEN_BYTES);
    MIX(M.line_palette, sizeof M.line_palette);
#undef MIX
    return h;
}

/* 16-bit stereo WAV header; the sample rate is the last one the game selected. */
static const uint8_t *wav_header(uint32_t frames, uint32_t rate)
{
    static uint8_t h[44];
    uint32_t bytes = frames * 4, v[] = { 36 + bytes, 16, 0x00020001u, rate, rate * 4, 0x00100004u, bytes };
    memcpy(h, "RIFF\0\0\0\0WAVEfmt ", 16);
    memcpy(h + 4, &v[0], 4);
    memcpy(h + 16, &v[1], 20);
    memcpy(h + 36, "data", 4);
    memcpy(h + 40, &v[6], 4);
    return h;
}

static void dump_frame(const char *dir, unsigned frame)
{
    static uint8_t rgb[SCREEN_W * SCREEN_H * 3];
    char path[256];
    machine_render_rgb(rgb);
    snprintf(path, sizeof path, "%s/frame%05u.ppm", dir, frame);
    FILE *f = fopen(path, "wb");
    if (!f) return;
    fprintf(f, "P6\n%d %d\n255\n", SCREEN_W, SCREEN_H);
    fwrite(rgb, 1, sizeof rgb, f);
    fclose(f);
}

int main(int argc, char **argv)
{
    unsigned frames = 100, every = 0;
    const char *outdir = "build/lotus/frames";
    const char *dump_app = NULL;
    int lockstep_hash = 0;
    const char *hash_path = NULL;
    const char *script = NULL;     /* "frame:pMASK frame:kKEY frame:uKEY ..." pad state, key down, key up */
    const char *engine = "interp";
    const char *wav_path = NULL;
    unsigned autodrive = 0;        /* frame from which the autopilot drives */
    FILE *wav = NULL;
    uint32_t wav_frames = 0, wav_rate = 48000;
    FILE *hash_file = NULL;
    machine_init();
#ifdef ARM26_COVERAGE
    {
        extern uint32_t watch_lo, watch_hi;
        const char *w = getenv("LOTUS_WATCH");        /* LOTUS_WATCH=hexaddr[,len] */
        if (w) {
            char *end;
            watch_lo = (uint32_t)strtoul(w, &end, 16);
            watch_hi = watch_lo + (*end == ',' ? (uint32_t)strtoul(end + 1, NULL, 0) : 1);
        }
    }
#endif
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--frames") && i + 1 < argc) frames = (unsigned)atoi(argv[++i]);
        else if (!strcmp(argv[i], "--every") && i + 1 < argc) every = (unsigned)atoi(argv[++i]);
        else if (!strcmp(argv[i], "--out") && i + 1 < argc) outdir = argv[++i];
        else if (!strcmp(argv[i], "--dump-app") && i + 1 < argc) dump_app = argv[++i];
        else if (!strcmp(argv[i], "--hash") && i + 1 < argc) hash_path = argv[++i];
        else if (!strcmp(argv[i], "--lockstep-hash") && i + 1 < argc) { hash_path = argv[++i]; lockstep_hash = 1; }
        else if (!strcmp(argv[i], "--engine") && i + 1 < argc) engine = argv[++i];
        else if (!strcmp(argv[i], "--input") && i + 1 < argc) script = argv[++i];
        else if (!strcmp(argv[i], "--wav") && i + 1 < argc) wav_path = argv[++i];
        else if (!strcmp(argv[i], "--autodrive") && i + 1 < argc) autodrive = (unsigned)atoi(argv[++i]);
        else if (!strcmp(argv[i], "--view") && i + 1 < argc) M.view_player = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--trace")) M.trace = 1;
        else if (!strcmp(argv[i], "--lenient")) M.lenient = 1;
        else { fprintf(stderr, "usage: lotus_host [--frames N] [--every N] [--out DIR] [--dump-app FILE] [--hash FILE] [--lockstep-hash FILE] [--input SCRIPT] [--wav FILE] [--autodrive FRAME] [--view 1|2] [--engine interp|reference|translated] [--trace] [--lenient]\n"); return 2; }
    }
    if (!load_raw("build/lotus/stub_70000.bin", 0x70000) || !load_raw("build/lotus/packed_8000.bin", 0x8000))
        return 1;
#ifdef LOTUS_RECOMP
    /* "translated" runs generated code; "reference" interprets with the same
       checkpoint rule, so the two produce identical state every frame. */
    if (!strcmp(engine, "translated")) hybrid_install();
    else if (!strcmp(engine, "reference")) { hybrid_install(); M.run = arm26_run; }
    else
#endif
    if (strcmp(engine, "interp")) { fprintf(stderr, "unknown engine %s\n", engine); return 2; }
    if (hash_path) hash_file = fopen(hash_path, "w");
    if (wav_path && (wav = fopen(wav_path, "wb")) != NULL) fwrite(wav_header(0, wav_rate), 1, 44, wav);
    M.cpu.pc = 0x70000;
    M.cpu.r[13] = APP_LIMIT;

    unsigned f;
    int dumped = 0;
    for (f = 0; f < frames && !M.fatal; f++) {
        for (const char *p = script; p && *p; ) {
            char kind = 0; unsigned at = 0, val = 0; int used = 0;
            if (sscanf(p, "%u:%c%u%n", &at, &kind, &val, &used) < 3) break;
            if (at == f) {
                if (kind == 'p') M.pad = val;
                else if (kind == 'k' && val < 128) M.keys[val] = 1;
                else if (kind == 'u' && val < 128) M.keys[val] = 0;
            }
            p += used;
            while (*p == ' ' || *p == ',') p++;
        }
        if (autodrive && f >= autodrive) {
            /* Hold player 1 fire (accelerate), change up and steer towards the middle of
               the road while a race is on: the game points the IRQ vector at its race
               handler (&DEA0) only then, and &1D368 is the car's lateral position (found
               by comparing memory after steering left and right). Outside a race, every
               10 s: down once, then fire. That moves the options menu from "redefine
               keys", where it returns after game over, to "game" and starts it, and
               moves other screens on. */
            int racing = bus_read32(0x18) == 0xEA0037A0u;
            int32_t x = (int32_t)bus_read32(0x1D368);
            M.keys[5] = racing ? 1 : (f % 500) >= 100 && (f % 500) < 104;
            M.keys[50] = !racing && (f % 500) < 4;
            M.keys[51] = racing && (f % 75) < 4;
            M.keys[97] = racing && x > 40;
            M.keys[66] = racing && x < -40;
        }
        machine_run_frame();
        if (getenv("LOTUS_REGS") && f % 100 == 0) fprintf(stderr, "frame %u r12=%08x pc=%08x\n", f, M.cpu.r[12], M.cpu.pc);
        if (getenv("LOTUS_BANKSTAT")) {
            /* debugging aid: which screen bank changed during this frame, and which was shown */
            static uint8_t prev[SCREEN_BYTES];
            const uint8_t *scr = guest_ptr(SCREEN_BASE);
            unsigned changed[2] = { 0, 0 };
            for (unsigned i = 0; i < SCREEN_BYTES; i++) changed[i >= SCREEN_BYTES / 2] += scr[i] != prev[i];
            memcpy(prev, scr, SCREEN_BYTES);
            fprintf(stderr, "frame %u: bank0 changed %u, bank1 changed %u, shown line 0 %u line 100 %u line 255 %u\n", f,
                    changed[0], changed[1], M.line_display[0], M.line_display[100], M.line_display[255]);
        }
        {
            static int16_t pcm[4096 * 2];
            unsigned got = sound_read(pcm, 4096, 48000);
            if (wav && got) { fwrite(pcm, 4, got, wav); wav_frames += got; }
        }
        if (!dumped && M.cpu.pc < 0x70000) {
            /* the stub has expanded the program and entered it */
            FILE *img = fopen("build/lotus/game_image.bin", "wb");
            if (img) { fwrite(guest_ptr(APP_BASE), 1, 0x70000 - APP_BASE, img); fclose(img); }
            dumped = 1;
#ifdef ARM26_COVERAGE
            cov_armed = 1;
#endif
        }
        if (hash_file) fprintf(hash_file, "%u %08x\n", f, lockstep_hash ? view_lockstep_hash() : state_hash());
        if (every && (f % every) == 0) {
            dump_frame(outdir, f);
            if (dump_app) {
                char name[512];
                snprintf(name, sizeof name, "%s.%u", dump_app, f);
                FILE *d = fopen(name, "wb");
                if (d) { fwrite(guest_ptr(0), 1, APP_LIMIT, d); fclose(d); }
            }
        }
    }
    dump_frame(outdir, f);
    if (dump_app) {
        FILE *d = fopen(dump_app, "wb");
        if (d) { fwrite(guest_ptr(0), 1, APP_LIMIT, d); fclose(d); }
    }
#ifdef ARM26_COVERAGE
    {
        unsigned executed = 0;
        for (uint32_t a = APP_BASE; a < APP_LIMIT; a += 4) executed += cov_map[a >> 2] & 1;
        /* accumulate with earlier runs so several scripted sessions build one map */
        FILE *old = fopen("build/lotus/coverage.bin", "rb");
        if (old) {
            int ch;
            for (uint32_t i = APP_BASE >> 2; i < (APP_LIMIT >> 2) && (ch = fgetc(old)) != EOF; i++) cov_map[i] |= (uint8_t)ch;
            fclose(old);
        }
        FILE *c = fopen("build/lotus/coverage.bin", "wb");
        if (c) { fwrite(cov_map + (APP_BASE >> 2), 1, (APP_LIMIT - APP_BASE) >> 2, c); fclose(c); }
        /* the music module: its image as loaded, and its own coverage map */
        if (M.mus_state > 0) {
            uint32_t words = (MUS_MODULE_LIMIT - MUS_MODULE) >> 2;
            if ((old = fopen("build/lotus/coverage_mus.bin", "rb")) != NULL) {
                int ch;
                for (uint32_t i = 0; i < words && (ch = fgetc(old)) != EOF; i++) cov_map[(MUS_MODULE >> 2) + i] |= (uint8_t)ch;
                fclose(old);
            }
            if ((c = fopen("build/lotus/coverage_mus.bin", "wb")) != NULL) {
                fwrite(cov_map + (MUS_MODULE >> 2), 1, words, c);
                fclose(c);
            }
            if ((c = fopen("build/lotus/musmod2.bin", "wb")) != NULL) {
                fwrite(guest_ptr(MUS_MODULE), 1, M.mus_size, c);
                fclose(c);
            }
        }
        fprintf(stderr, "coverage: %u words executed in application space; %u writes to executed words, "
                "%u executions of rewritten words\n", executed, cov_write_hits, cov_exec_hits);
    }
#endif
    if (hash_file) fclose(hash_file);
    if (wav) {
        rewind(wav);
        fwrite(wav_header(wav_frames, wav_rate), 1, 44, wav);
        fclose(wav);
    }
    {
        unsigned changes = 0;
        for (int y = 1; y < SCREEN_H; y++)
            if (memcmp(M.line_palette[y], M.line_palette[y - 1], sizeof M.line_palette[0])) changes++;
        fprintf(stderr, "palette changes between scanlines in the last frame: %u\n", changes);
    }
#ifdef LOTUS_RECOMP
    if (!strcmp(engine, "translated")) {
        fprintf(stderr, "interpreter fallback steps inside translated range: %llu\n", hybrid_fallback_steps);
        if (hybrid_fallback_logged) {
            FILE *x = fopen("build/lotus/leaders_seen.txt", "w");
            for (unsigned k = 0; x && k < hybrid_fallback_logged; k++) fprintf(x, "%x\n", hybrid_fallback_log[k]);
            if (x) fclose(x);
        }
    }
#endif
    fprintf(stderr, "stopped after %u frames, %llu instructions, pc=%08x%s\n", f,
            (unsigned long long)M.cpu.insns, M.cpu.pc, M.fatal ? " (fatal)" : "");
    return M.fatal ? 1 : 0;
}
