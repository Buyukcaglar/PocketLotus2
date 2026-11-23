/* ARM2 (26-bit) interpreter: reference CPU and fallback for the Lotus port. */
#include "arm26.h"

void arm26_reset(arm26_t *cpu)
{
    for (int i = 0; i < 16; i++) cpu->r[i] = 0;
    cpu->psr = MODE_USR;
    cpu->pc = 0;
    cpu->stop = 0;
}

void arm26_set_mode(arm26_t *cpu, unsigned mode)
{
    unsigned old = cpu->psr & PSR_MODE;
    mode &= 3;
    if (old == mode) return;
    /* park current registers */
    switch (old) {
    case MODE_USR: for (int i = 0; i < 7; i++) cpu->bank_usr[i] = cpu->r[8 + i]; break;
    case MODE_FIQ:
        for (int i = 0; i < 7; i++) cpu->bank_fiq[i] = cpu->r[8 + i];
        for (int i = 0; i < 5; i++) cpu->r[8 + i] = cpu->bank_usr[i];
        break;
    case MODE_IRQ: cpu->bank_irq[0] = cpu->r[13]; cpu->bank_irq[1] = cpu->r[14]; break;
    case MODE_SVC: cpu->bank_svc[0] = cpu->r[13]; cpu->bank_svc[1] = cpu->r[14]; break;
    }
    switch (mode) {
    case MODE_USR:
        cpu->r[13] = cpu->bank_usr[5]; cpu->r[14] = cpu->bank_usr[6];
        break;
    case MODE_FIQ:
        if (old != MODE_USR) { cpu->bank_usr[0] = cpu->r[8]; cpu->bank_usr[1] = cpu->r[9];
            cpu->bank_usr[2] = cpu->r[10]; cpu->bank_usr[3] = cpu->r[11]; cpu->bank_usr[4] = cpu->r[12]; }
        for (int i = 0; i < 7; i++) cpu->r[8 + i] = cpu->bank_fiq[i];
        break;
    case MODE_IRQ: cpu->r[13] = cpu->bank_irq[0]; cpu->r[14] = cpu->bank_irq[1]; break;
    case MODE_SVC: cpu->r[13] = cpu->bank_svc[0]; cpu->r[14] = cpu->bank_svc[1]; break;
    }
    cpu->psr = (cpu->psr & ~PSR_MODE) | mode;
}

/* Write PSR bits from a value in R15 format, honouring the privilege rule. */
void arm26_set_psr(arm26_t *cpu, uint32_t value)
{
    if ((cpu->psr & PSR_MODE) == MODE_USR) {
        cpu->psr = (cpu->psr & ~PSR_FLAGS) | (value & PSR_FLAGS);
    } else {
        unsigned mode = value & PSR_MODE;
        if ((cpu->psr & PSR_I) && !(value & PSR_I)) arm26_yield(cpu);
        cpu->psr = (cpu->psr & PSR_MODE) | (value & (PSR_FLAGS | PSR_I | PSR_F));
        arm26_set_mode(cpu, mode);
    }
}

void arm26_irq(arm26_t *cpu)
{
    uint32_t ret = arm26_r15(cpu, 4);
    arm26_set_mode(cpu, MODE_IRQ);
    cpu->r[14] = ret;
    cpu->psr |= PSR_I;
    cpu->pc = 0x18;
}

static inline int cond_ok(uint32_t psr, unsigned cond)
{
    int n = psr >> 31, z = (psr >> 30) & 1, c = (psr >> 29) & 1, v = (psr >> 28) & 1;
    switch (cond) {
    case 0: return z;
    case 1: return !z;
    case 2: return c;
    case 3: return !c;
    case 4: return n;
    case 5: return !n;
    case 6: return v;
    case 7: return !v;
    case 8: return c && !z;
    case 9: return !c || z;
    case 10: return n == v;
    case 11: return n != v;
    case 12: return !z && n == v;
    case 13: return z || n != v;
    case 14: return 1;
    default: return 0;
    }
}

static inline uint32_t user_reg(arm26_t *cpu, unsigned n)
{
    unsigned mode = cpu->psr & PSR_MODE;
    if (mode == MODE_USR || n < 8 || n == 15) return cpu->r[n];
    if (mode == MODE_FIQ) return cpu->bank_usr[n - 8];
    if (n >= 13) return cpu->bank_usr[n - 8];
    return cpu->r[n];
}

static inline void set_user_reg(arm26_t *cpu, unsigned n, uint32_t v)
{
    unsigned mode = cpu->psr & PSR_MODE;
    if (mode == MODE_USR || n < 8 || n == 15) cpu->r[n] = v;
    else if (mode == MODE_FIQ || n >= 13) cpu->bank_usr[n - 8] = v;
    else cpu->r[n] = v;
}

void arm26_exec(arm26_t *cpu, uint32_t op, uint32_t cur)
{
    {
        cpu->insns++;
        cpu->cycles -= 1;
        if (op < 0xE0000000u && !cond_ok(cpu->psr, op >> 28)) return;
        if (op >= 0xF0000000u) return;

        unsigned cls = (op >> 25) & 7;
        if (cls <= 1) {
            if (cls == 0 && (op & 0x0FC000F0u) == 0x00000090u) {
                /* MUL / MLA */
                unsigned rd = (op >> 16) & 15, rn = (op >> 12) & 15, rs = (op >> 8) & 15, rm = op & 15;
                uint32_t res = cpu->r[rm] * cpu->r[rs];
                if (op & 0x00200000u) res += cpu->r[rn];
                if (rd != 15) cpu->r[rd] = res;
                if (op & 0x00100000u)
                    cpu->psr = (cpu->psr & ~(PSR_N | PSR_Z)) | (res & PSR_N) | (res ? 0 : PSR_Z);
                cpu->cycles -= 8;
                return;
            }
            if (cls == 0 && (op & 0x0FB00FF0u) == 0x01000090u) {
                /* SWP (ARM2as/ARM3) */
                unsigned rn = (op >> 16) & 15, rd = (op >> 12) & 15, rm = op & 15;
                uint32_t addr = cpu->r[rn], v;
                if (op & 0x00400000u) { v = bus_read8(addr); bus_write8(addr, cpu->r[rm]); }
                else { v = bus_read32(addr); bus_write32(addr, cpu->r[rm]); }
                cpu->r[rd] = v;
                cpu->cycles -= 3;
                return;
            }
            /* data processing */
            unsigned opc = (op >> 21) & 15, s = (op >> 20) & 1;
            unsigned rn = (op >> 16) & 15, rd = (op >> 12) & 15;
            uint32_t a, b, cout = (cpu->psr >> 29) & 1;
            unsigned regshift = (cls == 0) && (op & 0x10);
            a = (rn == 15) ? ((cur + (regshift ? 12 : 8)) & PC_MASK) : cpu->r[rn];
            if (cls == 1) {
                unsigned rot = (op >> 7) & 0x1E;
                b = op & 0xFF;
                if (rot) { b = (b >> rot) | (b << (32 - rot)); cout = b >> 31; }
            } else {
                unsigned rm = op & 15, type = (op >> 5) & 3, amt;
                b = (rm == 15) ? (((cur + (regshift ? 12 : 8)) & PC_MASK) | cpu->psr) : cpu->r[rm];
                if (regshift) {
                    amt = cpu->r[(op >> 8) & 15] & 0xFF;
                    cpu->cycles -= 1;
                    if (amt) {
                        switch (type) {
                        case 0:
                            if (amt < 32) { cout = (b >> (32 - amt)) & 1; b <<= amt; }
                            else { cout = (amt == 32) ? (b & 1) : 0; b = 0; }
                            break;
                        case 1:
                            if (amt < 32) { cout = (b >> (amt - 1)) & 1; b >>= amt; }
                            else { cout = (amt == 32) ? (b >> 31) : 0; b = 0; }
                            break;
                        case 2:
                            if (amt < 32) { cout = (b >> (amt - 1)) & 1; b = (uint32_t)((int32_t)b >> amt); }
                            else { cout = b >> 31; b = (uint32_t)((int32_t)b >> 31); }
                            break;
                        default:
                            amt &= 31;
                            if (amt) b = (b >> amt) | (b << (32 - amt));
                            cout = b >> 31;
                            break;
                        }
                    }
                } else {
                    amt = (op >> 7) & 31;
                    switch (type) {
                    case 0:
                        if (amt) { cout = (b >> (32 - amt)) & 1; b <<= amt; }
                        break;
                    case 1:
                        if (amt) { cout = (b >> (amt - 1)) & 1; b >>= amt; }
                        else { cout = b >> 31; b = 0; }
                        break;
                    case 2:
                        if (amt) { cout = (b >> (amt - 1)) & 1; b = (uint32_t)((int32_t)b >> amt); }
                        else { cout = b >> 31; b = (uint32_t)((int32_t)b >> 31); }
                        break;
                    default:
                        if (amt) { cout = (b >> (amt - 1)) & 1; b = (b >> amt) | (b << (32 - amt)); }
                        else { uint32_t c = (cpu->psr >> 29) & 1; cout = b & 1; b = (b >> 1) | (c << 31); }
                        break;
                    }
                }
            }
            uint32_t res, cin = (cpu->psr >> 29) & 1, vout = (cpu->psr >> 28) & 1;
            uint64_t wide;
            int logical = 0, test = 0;
            switch (opc) {
            case 0: res = a & b; logical = 1; break;
            case 1: res = a ^ b; logical = 1; break;
            case 2: wide = (uint64_t)a + (uint32_t)~b + 1; res = (uint32_t)wide; cout = (uint32_t)(wide >> 32);
                    vout = ((a ^ b) & (a ^ res)) >> 31; break;
            case 3: wide = (uint64_t)b + (uint32_t)~a + 1; res = (uint32_t)wide; cout = (uint32_t)(wide >> 32);
                    vout = ((b ^ a) & (b ^ res)) >> 31; break;
            case 4: wide = (uint64_t)a + b; res = (uint32_t)wide; cout = (uint32_t)(wide >> 32);
                    vout = (~(a ^ b) & (a ^ res)) >> 31; break;
            case 5: wide = (uint64_t)a + b + cin; res = (uint32_t)wide; cout = (uint32_t)(wide >> 32);
                    vout = (~(a ^ b) & (a ^ res)) >> 31; break;
            case 6: wide = (uint64_t)a + (uint32_t)~b + cin; res = (uint32_t)wide; cout = (uint32_t)(wide >> 32);
                    vout = ((a ^ b) & (a ^ res)) >> 31; break;
            case 7: wide = (uint64_t)b + (uint32_t)~a + cin; res = (uint32_t)wide; cout = (uint32_t)(wide >> 32);
                    vout = ((b ^ a) & (b ^ res)) >> 31; break;
            case 8: res = a & b; logical = 1; test = 1; break;
            case 9: res = a ^ b; logical = 1; test = 1; break;
            case 10: wide = (uint64_t)a + (uint32_t)~b + 1; res = (uint32_t)wide; cout = (uint32_t)(wide >> 32);
                     vout = ((a ^ b) & (a ^ res)) >> 31; test = 1; break;
            case 11: wide = (uint64_t)a + b; res = (uint32_t)wide; cout = (uint32_t)(wide >> 32);
                     vout = (~(a ^ b) & (a ^ res)) >> 31; test = 1; break;
            case 12: res = a | b; logical = 1; break;
            case 13: res = b; logical = 1; break;
            case 14: res = a & ~b; logical = 1; break;
            default: res = ~b; logical = 1; break;
            }
            (void)logical;
            if (test && !s) return;   /* no MRS/MSR on ARM2 */
            if (rd == 15) {
                if (s) arm26_set_psr(cpu, res);
                if (!test) { cpu->pc = res & PC_MASK; cpu->cycles -= 2; }
            } else {
                if (!test) cpu->r[rd] = res;
                if (s)
                    cpu->psr = (cpu->psr & ~PSR_FLAGS) | (res & PSR_N) | (res ? 0 : PSR_Z) |
                               (cout ? PSR_C : 0) | (vout ? PSR_V : 0);
            }
            return;
        }
        if (cls == 2 || cls == 3) {
            /* LDR / STR */
            unsigned rn = (op >> 16) & 15, rd = (op >> 12) & 15;
            unsigned p = (op >> 24) & 1, u = (op >> 23) & 1, byte = (op >> 22) & 1;
            unsigned w = (op >> 21) & 1, load = (op >> 20) & 1;
            uint32_t base = (rn == 15) ? ((cur + 8) & PC_MASK) : cpu->r[rn];
            uint32_t off;
            if (cls == 2) off = op & 0xFFF;
            else {
                unsigned rm = op & 15, type = (op >> 5) & 3, amt = (op >> 7) & 31;
                off = (rm == 15) ? (((cur + 8) & PC_MASK) | cpu->psr) : cpu->r[rm];
                switch (type) {
                case 0: off <<= amt; break;
                case 1: off = amt ? off >> amt : 0; break;
                case 2: off = (uint32_t)((int32_t)off >> (amt ? amt : 31)); break;
                default:
                    if (amt) off = (off >> amt) | (off << (32 - amt));
                    else off = (off >> 1) | (((cpu->psr >> 29) & 1) << 31);
                    break;
                }
            }
            uint32_t addr = u ? base + off : base - off;
            uint32_t ea = p ? addr : base;
            if (load) {
                uint32_t v;
                if (byte) v = bus_read8(ea);
                else {
                    v = bus_read32(ea & ~3u);
                    if (ea & 3) { unsigned sh = (ea & 3) * 8; v = (v >> sh) | (v << (32 - sh)); }
                }
                if ((!p || w) && rn != 15) cpu->r[rn] = addr;
                if (rd == 15) { cpu->pc = v & PC_MASK; cpu->cycles -= 2; }
                else cpu->r[rd] = v;
                cpu->cycles -= 2;
            } else {
                uint32_t v = (rd == 15) ? (((cur + 12) & PC_MASK) | cpu->psr) : cpu->r[rd];
                if (byte) bus_write8(ea, v); else bus_write32(ea & ~3u, v);
                if ((!p || w) && rn != 15) cpu->r[rn] = addr;
                cpu->cycles -= 1;
            }
            return;
        }
        if (cls == 4) {
            /* LDM / STM */
            unsigned rn = (op >> 16) & 15;
            unsigned p = (op >> 24) & 1, u = (op >> 23) & 1, sbit = (op >> 22) & 1;
            unsigned w = (op >> 21) & 1, load = (op >> 20) & 1;
            unsigned list = op & 0xFFFF, count = 0;
            for (unsigned m = list; m; m &= m - 1) count++;
            uint32_t base = cpu->r[rn];
            uint32_t start = u ? base : base - 4 * count;
            uint32_t final = u ? base + 4 * count : base - 4 * count;
            if (p == u) start += 4;
            uint32_t addr = start & ~3u;
            int userbank = sbit && !(load && (list & 0x8000));
            cpu->cycles -= count + 1;
            if (load) {
                if (w) cpu->r[rn] = final;
                for (unsigned i = 0; i < 15; i++) {
                    if (!(list & (1u << i))) continue;
                    uint32_t v = bus_read32(addr);
                    addr += 4;
                    if (userbank) set_user_reg(cpu, i, v); else cpu->r[i] = v;
                }
                if (list & 0x8000) {
                    uint32_t v = bus_read32(addr);
                    if (sbit) arm26_set_psr(cpu, v);
                    cpu->pc = v & PC_MASK;
                    cpu->cycles -= 2;
                }
            } else {
                int first = 1;
                for (unsigned i = 0; i < 16; i++) {
                    if (!(list & (1u << i))) continue;
                    uint32_t v;
                    if (i == 15) v = ((cur + 12) & PC_MASK) | cpu->psr;
                    else if (i == rn) v = first ? base : final;
                    else v = userbank ? user_reg(cpu, i) : cpu->r[i];
                    if (i == rn && !w) v = base;
                    bus_write32(addr, v);
                    addr += 4;
                    first = 0;
                }
                if (w) cpu->r[rn] = final;
            }
            return;
        }
        if (cls == 5) {
            int32_t off = (int32_t)(op << 8) >> 6;
            if (op & 0x01000000u) cpu->r[14] = ((cur + 4) & PC_MASK) | cpu->psr;
            cpu->pc = (cur + 8 + off) & PC_MASK;
            cpu->cycles -= 2;
            return;
        }
        if ((op & 0x0F000000u) == 0x0F000000u) {
            cpu->cycles -= 2;
            if (swi_call(cpu, op & 0x00FFFFFFu)) cpu->stop = 1;
            return;
        }
        cpu_fault(cpu, "undefined instruction", op);
        cpu->stop = 1;
    }
}

const arm26_region_t *arm26_regions;
unsigned arm26_region_count;

void arm26_step(arm26_t *cpu)
{
    uint32_t cur = cpu->pc;
    cov_exec(cur);
    uint32_t op = bus_read32(cur);
    cpu->pc = (cur + 4) & PC_MASK;
    arm26_exec(cpu, op, cur);
}

void arm26_run(arm26_t *cpu)
{
    for (;;) {
        if (arm26_checkpoint(cpu->pc) && (cpu->cycles <= 0 || cpu->stop)) return;
        arm26_step(cpu);
    }
}
