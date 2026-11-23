/* Asset pack reader: serves the game's OS_File requests from one memory image. */
#include <string.h>
#include "machine.h"
#include "pack.h"

static const uint8_t *pack_data;
static uint32_t pack_count;

static uint32_t rd32(const uint8_t *p)
{
    return p[0] | (p[1] << 8) | (p[2] << 16) | ((uint32_t)p[3] << 24);
}

int pack_attach(const uint8_t *data, uint32_t size)
{
    if (size < 12 || memcmp(data, "LTC2PAK1", 8)) return 0;
    pack_count = rd32(data + 8);
    if (12 + 48 * (uint64_t)pack_count > size) return 0;
    pack_data = data;
    return 1;
}

/* "<Lotu$Dir>.Disk1.files1.file04" or "ADFS::0.Disk2.TEST" -> "disk1/files1/file04" */
static void normalise(const char *guest, char *out, size_t max)
{
    const char *p = guest, *q;
    size_t n = 0;
    if (*p == '<' && (q = strchr(p, '>')) != NULL) p = q + 1;
    if ((q = strstr(p, "::")) != NULL && (q = strchr(q, '.')) != NULL) p = q;
    while (*p == '.' || *p == '$') p++;
    for (; *p > ' ' && n + 1 < max; p++) {
        char c = *p;
        if (c == '.') c = '/';
        else if (c >= 'A' && c <= 'Z') c += 32;
        out[n++] = c;
    }
    out[n] = 0;
}

const uint8_t *pack_find(const char *guest_name, uint32_t *size)
{
    char name[40];
    normalise(guest_name, name, sizeof name);
    for (uint32_t i = 0; i < pack_count; i++) {
        const uint8_t *e = pack_data + 12 + 48 * i;
        if (!strncmp((const char *)e, name, 40)) {
            *size = rd32(e + 44);
            return pack_data + rd32(e + 40);
        }
    }
    return NULL;
}

int pack_load(const char *guest_name, uint32_t load_addr, uint32_t *size)
{
    const uint8_t *src = pack_find(guest_name, size);
    if (!src) return 0;
    load_addr &= GUEST_RAM_SIZE - 1;
    if (*size > GUEST_RAM_SIZE - load_addr) *size = GUEST_RAM_SIZE - load_addr;
    memcpy(guest_ptr(load_addr), src, *size);
    return 1;
}
