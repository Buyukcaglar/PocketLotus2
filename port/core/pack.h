#ifndef PACK_H
#define PACK_H

#include <stdint.h>

int pack_attach(const uint8_t *data, uint32_t size);
const uint8_t *pack_find(const char *guest_name, uint32_t *size);
int pack_load(const char *guest_name, uint32_t load_addr, uint32_t *size);

#endif
