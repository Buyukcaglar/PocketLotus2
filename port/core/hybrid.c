/* Runner that executes translated chunks and falls back to the interpreter. */
#include "recomp_rt.h"

unsigned long long hybrid_fallback_steps;
uint32_t hybrid_fallback_log[64];
unsigned hybrid_fallback_logged;

void hybrid_install(void)
{
    arm26_regions = recomp_regions;
    arm26_region_count = recomp_region_count;
    M.run = hybrid_run;
}

void hybrid_run(arm26_t *cpu)
{
    int in_fallback = 0;
    for (;;) {
        uint32_t pc = cpu->pc;
        const arm26_region_t *r = arm26_region(pc);
        if (r) {
            uint32_t i = (pc - r->base) >> 2;
            if ((r->leaders[i >> 3] >> (i & 7)) & 1) {
                if (cpu->cycles <= 0 || cpu->stop) return;
                in_fallback = 0;
                r->chunks[(pc - r->base) >> 12](cpu);
                continue;
            }
            /* inside an image but not at a block leader: interpret until one is reached.
               The entry address of each excursion is logged so the recompiler can add it. */
            if (!in_fallback) {
                unsigned k;
                for (k = 0; k < hybrid_fallback_logged; k++)
                    if (hybrid_fallback_log[k] == pc) break;
                if (k == hybrid_fallback_logged && k < 64) hybrid_fallback_log[hybrid_fallback_logged++] = pc;
                in_fallback = 1;
            }
            hybrid_fallback_steps++;
            arm26_step(cpu);
            continue;
        }
        if (cpu->cycles <= 0 || cpu->stop) return;
        arm26_step(cpu);
    }
}
