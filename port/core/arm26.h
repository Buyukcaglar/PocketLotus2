/* ARM2 (26-bit) interpreter: reference CPU and fallback for the Lotus port. */
#ifndef ARM26_H
#define ARM26_H

#include <stdint.h>

#define PSR_N 0x80000000u
#define PSR_Z 0x40000000u
#define PSR_C 0x20000000u
#define PSR_V 0x10000000u
#define PSR_I 0x08000000u
#define PSR_F 0x04000000u
#define PSR_FLAGS 0xF0000000u
#define PSR_MODE 0x00000003u
#define PC_MASK 0x03FFFFFCu

enum { MODE_USR = 0, MODE_FIQ = 1, MODE_IRQ = 2, MODE_SVC = 3 };

typedef struct arm26 {
    uint32_t r[16];      /* r[15] unused; see pc/psr */
    uint32_t pc;         /* address of the next instruction to fetch */
    uint32_t psr;        /* NZCVIF in bits 31..26, mode in bits 1..0 */
    uint32_t bank_usr[7];    /* r8..r14 of user mode while another mode is active */
    uint32_t bank_fiq[7];    /* r8..r14 */
    uint32_t bank_irq[2];    /* r13,r14 */
    uint32_t bank_svc[2];    /* r13,r14 */
    int32_t cycles;      /* 8 MHz cycles left in the current slice */
    int32_t yielded;     /* cycles given back by arm26_yield */
    uint64_t insns;
    int stop;            /* set by callbacks to leave arm26_run */
} arm26_t;

/* Guest bus, provided by the machine. */
uint32_t bus_read32(uint32_t addr);
uint32_t bus_read8(uint32_t addr);
void bus_write32(uint32_t addr, uint32_t value);
void bus_write8(uint32_t addr, uint32_t value);
/* SWI hook. Return 0 when handled in C; nonzero to stop with an error. */
int swi_call(arm26_t *cpu, uint32_t number);
void cpu_fault(arm26_t *cpu, const char *what, uint32_t insn);

/* Optional execution coverage hooks (host analysis builds). */
#ifdef ARM26_COVERAGE
void cov_exec(uint32_t addr);
#else
#define cov_exec(addr) ((void)0)
#endif

void arm26_reset(arm26_t *cpu);
void arm26_set_mode(arm26_t *cpu, unsigned mode);
void arm26_set_psr(arm26_t *cpu, uint32_t value);
void arm26_exec(arm26_t *cpu, uint32_t op, uint32_t cur);   /* one fetched instruction; pc already cur+4 */
void arm26_step(arm26_t *cpu);
void arm26_run(arm26_t *cpu);          /* runs until a checkpoint with cycles <= 0 or stop */

/* A slice may end only at a checkpoint. Without a leader map every instruction
 * is one. With a map (installed by translated code) only block leaders inside
 * the translated range are, so interpreter and translated code stop at exactly
 * the same places and can be compared state for state. */
typedef struct arm26_region {
    uint32_t base, limit;
    const uint8_t *leaders;                       /* one bit per word */
    void (*const *chunks)(arm26_t *cpu);          /* one function per 4 KiB, or 0 */
} arm26_region_t;
extern const arm26_region_t *arm26_regions;
extern unsigned arm26_region_count;

static inline const arm26_region_t *arm26_region(uint32_t pc)
{
    for (unsigned i = 0; i < arm26_region_count; i++)
        if (pc - arm26_regions[i].base < arm26_regions[i].limit - arm26_regions[i].base) return &arm26_regions[i];
    return 0;
}
static inline int arm26_checkpoint(uint32_t pc)
{
    const arm26_region_t *r = arm26_region(pc);
    if (!r) return 1;
    uint32_t i = (pc - r->base) >> 2;
    return (r->leaders[i >> 3] >> (i & 7)) & 1;
}
void arm26_irq(arm26_t *cpu);          /* take IRQ exception now */

/* End the current slice early so the scheduler can re-evaluate interrupts. */
static inline void arm26_yield(arm26_t *cpu)
{
    if (cpu->cycles > 0) { cpu->yielded += cpu->cycles; cpu->cycles = 0; }
}

static inline uint32_t arm26_r15(const arm26_t *cpu, uint32_t ahead)
{
    return ((cpu->pc + ahead) & PC_MASK) | cpu->psr;
}

#endif
