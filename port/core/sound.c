/* RISC OS sound system, level 0: buffer interrupts, the channel handler call
   and conversion of the VIDC logarithmic samples to linear stereo. Also hosts
   the game's own MusicModule2, which runs as guest code. */
#include <string.h>
#include "machine.h"

static int16_t log_lin[256];

static uint8_t lin_to_log(int v)                  /* v: -4015..4015 */
{
    int mag = v < 0 ? -v : v, best = 0;
    for (int b = 0; b < 256; b += 2)
        if (log_lin[b] <= mag) best = b;
    return (uint8_t)(best | (v < 0 ? 1 : 0));
}

void sound_init(void)
{
    for (int b = 0; b < 256; b++) {
        int chord = b >> 5, point = (b >> 1) & 15;
        int mag = (((2 * point + 33) << chord) - 33) / 2;
        log_lin[b] = (int16_t)((b & 1) ? -mag : mag);
    }
    uint8_t *scale = guest_ptr(SND_LOGSCALE), *l2l = guest_ptr(SND_LIN2LOG);
    for (int i = 0; i < 256; i++) scale[i] = (uint8_t)i;
    for (int i = 0; i < 8192; i++) l2l[i] = lin_to_log(i < 4096 ? i : i - 8192);
    bus_write32(SND_RETURN, 0xE1A0F00Eu);         /* MOV PC,R14 */
    bus_write32(SND_HANDLER, SND_RETURN);
    bus_write32(SND_HANDLER + 4, SND_RETURN);
    bus_write32(SND_HANDLER + 8, SND_LIN2LOG);
    bus_write32(SND_HANDLER + 12, SND_LOGSCALE);
    M.snd_channels = 1;
    M.snd_samples = 208;
    M.snd_period = 48;
    M.snd_handler = SND_HANDLER;
    M.snd_scheduler = 0;
    M.snd_cycles = (int32_t)(M.snd_samples * M.snd_period * 8);
    M.irqb_mask |= 0x02;
}

/* Advance guest time; raise the buffer interrupt (IRQ B bit 1) when one buffer has played. */
void sound_tick(int32_t cycles)
{
    M.snd_cycles -= cycles;
    if (M.snd_cycles > 0) return;
    M.snd_cycles += (int32_t)(M.snd_samples * M.snd_period * 8);
    if (M.snd_cycles <= 0) M.snd_cycles = 1;
    M.irqb_status |= 0x02;
}

/* The buffer interrupt: have the channel handler fill the next buffer, then mix it. */
void sound_service(void)
{
    uint32_t ch = M.snd_channels, n = M.snd_samples;
    uint32_t buf = M.snd_flip ? SND_BUFFER1 : SND_BUFFER0;
    uint8_t *p = guest_ptr(buf);
    M.irqb_status &= ~0x02;
    M.snd_flip ^= 1;
    memset(p, 0, n * ch);
    if (M.snd_handler != SND_HANDLER) {
        uint32_t regs[13] = { 0 };
        regs[6] = M.snd_changed ? 0x80000000u : 0;
        regs[7] = ch;
        regs[8] = M.snd_period;
        regs[9] = SND_SCCB;
        regs[10] = buf + n * ch;
        regs[11] = ch;
        regs[12] = buf;
        M.snd_changed = 0;
        guest_call_regs(bus_read32(M.snd_handler), MODE_IRQ, regs);
    }
    M.snd_rate = 1000000u / M.snd_period;
    for (uint32_t s = 0; s < n && M.snd_pcm_frames < SND_PCM_FRAMES; s++, p += ch) {
        int l = 0, r = 0;
        for (uint32_t c = 0; c < ch; c++) {
            int v = log_lin[p[c]], pos = M.snd_stereo[c];
            l += v * (127 - pos);
            r += v * (127 + pos);
        }
        /* VIDC gives each channel its own time slot, so channels average rather than
           add: one full-scale channel panned hard to one side is the loudest case,
           2 x 4015 x 4 = 32120, so the output can never clip. */
        l = l * 4 / (127 * (int)ch); r = r * 4 / (127 * (int)ch);
        if (l > 32767) l = 32767; else if (l < -32768) l = -32768;
        if (r > 32767) r = 32767; else if (r < -32768) r = -32768;
        M.snd_pcm[M.snd_pcm_frames * 2] = (int16_t)l;
        M.snd_pcm[M.snd_pcm_frames * 2 + 1] = (int16_t)r;
        M.snd_pcm_frames++;
    }
}

void sound_swi(arm26_t *cpu, uint32_t n)
{
    if (M.trace) host_log("Sound SWI %05x r0=%08x r1=%08x r2=%08x r3=%08x r4=%08x pc=%08x\n", n, cpu->r[0],
                          cpu->r[1], cpu->r[2], cpu->r[3], cpu->r[4], cpu->pc - 4);
    switch (n) {
    case 0x40140: {                               /* Sound_Configure */
        uint32_t old[5] = { M.snd_channels, M.snd_samples, M.snd_period, M.snd_handler, M.snd_scheduler };
        uint32_t c = cpu->r[0];
        if (c) M.snd_channels = c > 4 ? 8 : c > 2 ? 4 : c;
        if (cpu->r[1] >= 16 && cpu->r[1] <= 512) M.snd_samples = cpu->r[1];
        if (cpu->r[2] >= 8 && cpu->r[2] <= 255) M.snd_period = cpu->r[2];
        if (cpu->r[3]) M.snd_handler = cpu->r[3];
        if (cpu->r[4]) M.snd_scheduler = cpu->r[4];
        M.snd_changed = 1;
        memcpy(cpu->r, old, sizeof old);
        break;
    }
    case 0x40141: cpu->r[0] = 2; break;           /* Sound_Enable: on */
    case 0x40142: {                               /* Sound_Stereo */
        uint32_t c = (cpu->r[0] - 1) & 7;
        int32_t pos = (int32_t)cpu->r[1], old = M.snd_stereo[c];
        if (pos != -128) {
            if (pos < -127) pos = -127;
            if (pos > 127) pos = 127;
            /* RISC OS repeats the setting on every channel that shares the output slot */
            for (uint32_t k = c; k < 8; k += M.snd_channels) M.snd_stereo[k] = (int8_t)pos;
        }
        cpu->r[1] = (uint32_t)old;
        break;
    }
    case 0x40143: cpu->r[0] = 2; break;           /* Sound_Speaker */
    default: break;
    }
}

/* MusicModule2: loaded from the game directory on first use and run as guest code. */
static int mus_start(void)
{
    uint32_t size = 0, regs[13] = { 0 };
    if (M.mus_state) return M.mus_state > 0;
    M.mus_state = -1;
    if (!host_load_file("<Lotu$Dir>.MusMod2", MUS_MODULE, &size) || size < 0x30) {
        host_log("MusMod2 is missing: no music\n");
        return 0;
    }
    M.mus_size = size;
    bus_write32(MUS_PRIVATE, 0);
    bus_write32(MUS_PRIVATE + 4, 0);
    regs[10] = MUS_PRIVATE + 4;                   /* empty command tail */
    regs[12] = MUS_PRIVATE;
    M.vdu_mute = 1;                               /* the module prints a banner */
    int ok = guest_call_regs(MUS_MODULE + bus_read32(MUS_MODULE + 4), MODE_SVC, regs);
    M.vdu_mute = 0;
    if (!ok) return 0;
    M.mus_state = 1;
    return 1;
}

int mus_swi(arm26_t *cpu, uint32_t offset)
{
    uint32_t regs[13];
    if (M.trace) host_log("Mus SWI %u r0=%08x r1=%08x pc=%08x\n", offset, cpu->r[0], cpu->r[1], cpu->pc - 4);
    if (!mus_start()) {
        if (offset == 13) cpu->r[0] = MUS_FALLBACK_BUFFER;
        return 1;
    }
    memcpy(regs, cpu->r, sizeof regs);
    regs[11] = offset;
    regs[12] = MUS_PRIVATE;
    int ok = guest_call_regs(MUS_MODULE + bus_read32(MUS_MODULE + 0x20), MODE_SVC, regs);
    memcpy(cpu->r, regs, 10 * sizeof regs[0]);
    return ok > 0;
}

/* Hand the host everything produced since the last call, resampled to out_rate.
   Returns the number of stereo frames written. */
unsigned sound_read(int16_t *out, unsigned max_frames, uint32_t out_rate)
{
    static uint32_t phase;                        /* 16.16 position; 0 is the last frame of the previous call */
    static int16_t last[2];
    uint32_t frames = M.snd_pcm_frames, n = 0;
    if (!frames || !M.snd_rate) return 0;
    uint32_t step = (uint32_t)(((uint64_t)M.snd_rate << 16) / out_rate);
    while (n < max_frames) {
        uint32_t idx = phase >> 16, frac = phase & 0xFFFF;
        if (idx >= frames) break;
        const int16_t *a = idx ? &M.snd_pcm[(idx - 1) * 2] : last, *b = &M.snd_pcm[idx * 2];
        out[n * 2] = (int16_t)(a[0] + (((b[0] - a[0]) * (int32_t)frac) >> 16));
        out[n * 2 + 1] = (int16_t)(a[1] + (((b[1] - a[1]) * (int32_t)frac) >> 16));
        n++;
        phase += step;
    }
    last[0] = M.snd_pcm[(frames - 1) * 2];
    last[1] = M.snd_pcm[(frames - 1) * 2 + 1];
    phase = (phase >> 16) >= frames ? phase - (frames << 16) : 0;
    M.snd_pcm_frames = 0;
    return n;
}
