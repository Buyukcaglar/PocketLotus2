/* Archimedes-shaped guest environment for the Lotus program. */
#ifndef MACHINE_H
#define MACHINE_H

#include <stddef.h>
#include <stdint.h>
#include "arm26.h"

#define GUEST_RAM_SIZE   0x02000000u      /* 32 MiB logical space, flat */
#define SCREEN_END       0x02000000u
#define SCREEN_BYTES     (80u * 1024u)    /* ScreenSize 80: two MODE 9 banks */
#define SCREEN_BASE      (SCREEN_END - SCREEN_BYTES)
#define SCREEN_W 320
#define SCREEN_H 256
#define LINE_BYTES 160
#define APP_BASE         0x00008000u
#define APP_LIMIT        0x0008F000u      /* WimpSlot 540K */
#define RMA_BASE         0x01800000u
#define MUS_FALLBACK_BUFFER 0x01900000u   /* song buffer when MusMod2 is absent */
#define MUS_PRIVATE      0x019FFFF0u      /* MusicModule2 private word */
#define MUS_MODULE       0x01A00000u      /* MusicModule2 image */
#define MUS_MODULE_LIMIT 0x01A04000u
#define SVC_STACK_TOP    0x01C02000u
#define IRQ_STACK_TOP    0x01C01000u
#define RETURN_TRAP      0x03FFFF00u      /* guest_call return address */
#define OS_IRQ_ENTRY     0x01F00000u      /* trap word standing in for the OS IRQ handler */
#define SND_HANDLER      0x01F00100u      /* default channel handler block */
#define SND_RETURN       0x01F00200u
#define SND_SCCB         0x01F00400u      /* sound channel control blocks */
#define SND_BUFFER0      0x01F01000u      /* the two DMA buffers */
#define SND_BUFFER1      0x01F02000u
#define SND_LOGSCALE     0x01F03000u
#define SND_LIN2LOG      0x01F04000u
#define SND_PCM_FRAMES   4096

#define CYCLES_PER_LINE  512              /* 8 MHz ARM2, 64 us scanline */
#define LINES_PER_FRAME  312
#define VSYNC_LINE       256

enum { PAD_UP = 1, PAD_DOWN = 2, PAD_LEFT = 4, PAD_RIGHT = 8, PAD_FIRE = 16 };

typedef struct machine {
    arm26_t cpu;
    void (*run)(arm26_t *cpu);            /* interpreter or translated-code runner */
    uint8_t *ram;
    uint32_t line;
    int32_t line_debt;
    uint32_t tick_fraction;
    uint32_t frame;
    /* VIDC */
    uint16_t palette[16];
    uint16_t border;
    int bpp;                              /* 4 (MODE 9) or 8 (MODE 13) */
    uint16_t line_palette[SCREEN_H][16];
    uint32_t line_display[SCREEN_H];      /* display start per line */
    uint8_t line_pixels[SCREEN_H][SCREEN_W]; /* screen bytes of each line as the beam passed it */
    uint8_t line_new_palette[SCREEN_H];   /* palette written since the line before */
    int palette_dirty;                    /* set by every palette write */
    uint32_t display_offset;              /* hardware bank, bytes from SCREEN_BASE */
    uint32_t driver_offset;               /* VDU driver bank */
    /* IOC */
    uint8_t irqa_status, irqa_mask, irqb_status, irqb_mask, fiq_mask;
    uint16_t timer_latch[4], timer_count[4], timer_out[4];
    /* OS state */
    uint32_t event_handler[4], event_r12[4];
    int event_handlers;
    int vsync_event_enabled;
    int vsync_pending;
    uint32_t rma_next;
    uint32_t monotonic_cs;
    int wait_vsync;
    uint8_t keys[128];                    /* RISC OS internal key numbers, nonzero = down */
    uint32_t pad;                         /* PAD_* bits for joystick 0 */
    /* sound */
    uint32_t snd_channels, snd_samples, snd_period, snd_handler, snd_scheduler;
    int8_t snd_stereo[8];
    int32_t snd_cycles;                   /* guest cycles until the next buffer interrupt */
    int snd_flip, snd_changed;
    uint32_t snd_rate;                    /* sample rate of snd_pcm */
    uint32_t snd_pcm_frames;              /* stereo frames produced since the host last took them */
    int16_t snd_pcm[SND_PCM_FRAMES * 2];
    int mus_state;                        /* 0 not loaded, 1 running, -1 unavailable */
    uint32_t mus_size;
    int vdu_mute;
    int view_player;                      /* linked consoles: 0 draw both views, 1 or 2 own view only */
    int view_patched;
    /* emulated time: cycles run before the current CPU slice, and that slice's size */
    uint64_t cycle_clock;
    int32_t run_slice;
    /* own-view drawing takes no emulated time (view.c): frozen while it runs,
       with the cycles it used so far in the current slice handed back */
    int frozen;
    uint64_t freeze_at;
    int32_t time_refund;
    int trace;
    int lenient;
    int fatal;
} machine_t;

extern machine_t M;

void machine_init(void);
void machine_run_frame(void);
void os_irq_handler(arm26_t *cpu);
void machine_render_rgb(uint8_t *rgb);   /* SCREEN_W*SCREEN_H*3 bytes */
/* RGB565 picture for a display: `lines` rows starting at guest line `first`, `stride` bytes apart */
/* Lines first..first+lines-1 as RGB565 rows, each written `repeat` times (1 = normal). */
#define SWI_VIEW_START 0x0FFFF2u
#define SWI_VIEW_END   0x0FFFF3u
#define SWI_VIEW_P2    0x0FFFF4u
#define SWI_VIEW_AFTER 0x0FFFF5u
uint64_t machine_now(const arm26_t *cpu);
int view_patch_ok(void);
uint32_t view_lockstep_hash(void);
void view_patch(void);
void view_hook(arm26_t *cpu, uint32_t swi);

void machine_render_565(uint16_t *dst, unsigned stride, unsigned first, unsigned lines, unsigned repeat);
int guest_call(uint32_t addr, uint32_t r0, uint32_t r12);
int guest_call_regs(uint32_t addr, uint32_t mode, uint32_t regs[13]);   /* 1 ok, -1 returned V set, 0 failed */
uint32_t bus_read32(uint32_t addr);
void bus_write32(uint32_t addr, uint32_t v);
void sound_init(void);
void sound_tick(int32_t cycles);
void sound_service(void);
void sound_swi(arm26_t *cpu, uint32_t n);
int mus_swi(arm26_t *cpu, uint32_t offset);
unsigned sound_read(int16_t *out, unsigned max_frames, uint32_t out_rate);
void *guest_ptr(uint32_t addr);
void guest_string(uint32_t addr, char *out, size_t max);

/* Host services */
int host_load_file(const char *guest_name, uint32_t load_addr, uint32_t *size);
int host_file_size(const char *guest_name, uint32_t *size);
void host_log(const char *fmt, ...);

#endif
