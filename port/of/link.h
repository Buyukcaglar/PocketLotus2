/* Two-console play over the Pocket link cable.

   Both consoles run the same game in lockstep. The emulated machine is fully
   deterministic, so only controller input crosses the cable: every frame each
   console sends its pad state for a frame a few frames ahead, and a frame runs
   once both inputs for it are known. The host's pad is player 1, the joining
   console's pad is player 2; the game's own two-player mode does the rest. */
#ifndef LOTUS_LINK_H
#define LOTUS_LINK_H

#include <stdint.h>

enum { LINK_OFF, LINK_HOST, LINK_JOIN };

/* Start the link in the given role and wait for the other console (up to
   timeout_ms). Returns 1 when connected, 0 otherwise (play continues alone). */
int link_start(int role, unsigned timeout_ms);
int link_active(void);
int link_role(void);

/* Exchange input for frame `frame`: send this console's input for a later frame,
   then wait for the other console's input for `frame`. Fills in both players'
   input for `frame`. Returns 0 if the link was lost (play continues alone). */
int link_exchange(unsigned frame, uint16_t local, uint16_t *host, uint16_t *join);

/* Every LINK_CHECK_FRAMES frames both sides compare a hash of the game state. */
#define LINK_CHECK_FRAMES 250
void link_check(unsigned frame, uint32_t hash);

#endif
