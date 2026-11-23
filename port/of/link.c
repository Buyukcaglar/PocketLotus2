/* Link cable lockstep, see link.h.

   Wire format: records of 6 bytes, A5 type frame(16) data(16)... kept fixed
   size so a receiver can resynchronise on the A5 byte after a lost byte:
     A5 kind f0 f1 d0 d1 then a checksum byte (7 bytes in all).
   kind 'H' hello (handshake), 'I' input for frame f, 'C' state hash low/high
   half for frame f (two records, d = 16 bits each). */
#include <stdio.h>
#include <string.h>
#include "link.h"

#ifdef OF_PC
/* The SDK's desktop build has no link cable; two desktop instances talk over
   TCP on localhost port 52710 instead, so the protocol can be tested on a PC. */
#ifdef _WIN32
#include <winsock2.h>
typedef SOCKET sock_t;
#define SOCK_BAD INVALID_SOCKET
#else
#include <arpa/inet.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <sys/socket.h>
#include <unistd.h>
typedef int sock_t;
#define SOCK_BAD (-1)
#define closesocket close
#endif
#include <SDL.h>
static sock_t sock = SOCK_BAD;

static uint32_t now_ms(void) { return SDL_GetTicks(); }
static void nap(void) { SDL_Delay(1); }

static void set_nonblocking(sock_t s)
{
#ifdef _WIN32
    u_long on = 1;
    ioctlsocket(s, FIONBIO, &on);
#else
    fcntl(s, F_SETFL, fcntl(s, F_GETFL) | O_NONBLOCK);
#endif
    int one = 1;
    setsockopt(s, IPPROTO_TCP, TCP_NODELAY, (const char *)&one, sizeof one);
}

static int transport_start(int role, unsigned timeout_ms)
{
#ifdef _WIN32
    WSADATA wsa;
    WSAStartup(MAKEWORD(2, 2), &wsa);
#endif
    struct sockaddr_in a;
    memset(&a, 0, sizeof a);
    a.sin_family = AF_INET;
    a.sin_port = htons(52710);
    a.sin_addr.s_addr = htonl(0x7F000001);
    uint32_t t0 = now_ms();
    if (role == LINK_HOST) {
        sock_t l = socket(AF_INET, SOCK_STREAM, 0);
        int one = 1;
        setsockopt(l, SOL_SOCKET, SO_REUSEADDR, (const char *)&one, sizeof one);
        if (bind(l, (struct sockaddr *)&a, sizeof a) != 0 || listen(l, 1) != 0) { closesocket(l); return 0; }
        set_nonblocking(l);
        while (now_ms() - t0 < timeout_ms) {
            sock = accept(l, NULL, NULL);
            if (sock != SOCK_BAD) break;
            nap();
        }
        closesocket(l);
    } else {
        while (now_ms() - t0 < timeout_ms) {
            sock = socket(AF_INET, SOCK_STREAM, 0);
            if (connect(sock, (struct sockaddr *)&a, sizeof a) == 0) break;
            closesocket(sock);
            sock = SOCK_BAD;
            SDL_Delay(50);
        }
    }
    if (sock == SOCK_BAD) return 0;
    set_nonblocking(sock);
    return 1;
}

static int transport_send(const uint8_t *p, int n)
{
    int sent = 0;
    while (sent < n) {
        int r = send(sock, (const char *)p + sent, n - sent, 0);
        if (r > 0) sent += r;
        else nap();
    }
    return sent;
}

static int transport_recv(uint8_t *p, int n)
{
    int r = recv(sock, (char *)p, n, 0);
    return r > 0 ? r : 0;
}

static void transport_stop(void)
{
    if (sock != SOCK_BAD) closesocket(sock);
    sock = SOCK_BAD;
}

#else /* the Pocket: openfpgaOS link cable through of_net */

#include <unistd.h>
#include "of.h"

static int net_role;

static uint32_t now_ms(void) { return of_time_ms(); }
static void nap(void) { usleep(200); }

static int transport_start(int role, unsigned timeout_ms)
{
    net_role = role;
    int r = (role == LINK_HOST) ? of_net_host_start() : of_net_join();
    if (r < 0) return 0;
    uint32_t t0 = now_ms();
    while (now_ms() - t0 < timeout_ms) {
        of_net_poll();
        if (role == LINK_HOST ? of_net_client_count() > 0 : of_net_status() == OF_NET_JOINED) return 1;
        nap();
    }
    of_net_stop();
    return 0;
}

static int transport_send(const uint8_t *p, int n)
{
    int sent = 0;
    uint32_t t0 = now_ms();
    while (sent < n && now_ms() - t0 < 1000) {
        int r = (net_role == LINK_HOST) ? of_net_broadcast(p + sent, (size_t)(n - sent))
                                        : of_net_send(p + sent, (size_t)(n - sent));
        if (r > 0) sent += r;
        else nap();
    }
    return sent;
}

static int transport_recv(uint8_t *p, int n)
{
    of_net_poll();
    int r = (net_role == LINK_HOST) ? of_net_recv_from(0, p, (size_t)n) : of_net_recv(p, (size_t)n);
    return r > 0 ? r : 0;
}

static void transport_stop(void) { of_net_stop(); }

#endif

/* ---- protocol ---- */

#define DELAY 3                     /* input delay in frames: hides the cable's latency */
#define HIST 64
#define REC 7

static int role = LINK_OFF, active;
static uint16_t remote_input[HIST];
static int32_t remote_frame[HIST];   /* frame number stored in each slot, -1 empty */
static uint16_t local_input[HIST];
static uint32_t remote_hash_lo[HIST], remote_hash_hi[HIST], local_hash[HIST];
static int32_t remote_hash_frame_lo[HIST], remote_hash_frame_hi[HIST], local_hash_frame[HIST];
static int got_hello;
static uint8_t rx[256];
static int rx_len;

int link_active(void) { return active; }
int link_role(void) { return role; }

static void put(uint8_t kind, unsigned frame, uint16_t data)
{
    uint8_t r[REC] = { 0xA5, kind, (uint8_t)frame, (uint8_t)(frame >> 8), (uint8_t)data, (uint8_t)(data >> 8), 0 };
    for (int i = 0; i < REC - 1; i++) r[REC - 1] += r[i];
    if (transport_send(r, REC) != REC) { active = 0; printf("link: send failed, playing on alone\n"); }
}

/* full frame number from its low 16 bits, near the reference frame */
static int32_t widen(unsigned ref, unsigned low16)
{
    int32_t f = (int32_t)((ref & ~0xFFFFu) | low16);
    if (f - (int32_t)ref > 0x8000) f -= 0x10000;
    else if ((int32_t)ref - f > 0x8000) f += 0x10000;
    return f;
}

static void compare_hash(int slot)
{
    int32_t f = local_hash_frame[slot];
    if (f < 0 || remote_hash_frame_lo[slot] != f || remote_hash_frame_hi[slot] != f) return;
    uint32_t theirs = remote_hash_lo[slot] | (remote_hash_hi[slot] << 16);
    if (theirs != local_hash[slot])
        printf("link: the two games differ at frame %d (%08x here, %08x there)\n", f, (unsigned)local_hash[slot], (unsigned)theirs);
    local_hash_frame[slot] = -1;
}

static void pump(unsigned ref)
{
    int n = transport_recv(rx + rx_len, (int)sizeof rx - rx_len);
    rx_len += n;
    int i = 0;
    while (rx_len - i >= REC) {
        uint8_t *r = rx + i, sum = 0;
        if (r[0] != 0xA5) { i++; continue; }
        for (int k = 0; k < REC - 1; k++) sum += r[k];
        if (sum != r[REC - 1]) { i++; continue; }
        unsigned low = r[2] | (r[3] << 8);
        uint16_t d = (uint16_t)(r[4] | (r[5] << 8));
        int32_t f = widen(ref, low);
        int slot = (int)((uint32_t)f % HIST);
        if (r[1] == 'H') got_hello = 1;
        else if (r[1] == 'I') { remote_input[slot] = d; remote_frame[slot] = f; }
        else if (r[1] == 'L') { remote_hash_lo[slot] = d; remote_hash_frame_lo[slot] = f; compare_hash(slot); }
        else if (r[1] == 'U') { remote_hash_hi[slot] = d; remote_hash_frame_hi[slot] = f; compare_hash(slot); }
        i += REC;
    }
    memmove(rx, rx + i, (size_t)(rx_len - i));
    rx_len -= i;
}

int link_start(int r, unsigned timeout_ms)
{
    role = r;
    for (int i = 0; i < HIST; i++) {
        remote_frame[i] = -1;
        remote_hash_frame_lo[i] = remote_hash_frame_hi[i] = local_hash_frame[i] = -1;
    }
    /* frames before DELAY have no input on either side */
    for (int f = 0; f < DELAY; f++) { remote_input[f] = 0; remote_frame[f] = f; local_input[f] = 0; }
    printf("link: %s, waiting for the other console\n", r == LINK_HOST ? "hosting (player 1)" : "joining (player 2)");
    if (!transport_start(r, timeout_ms)) { printf("link: no other console, playing alone\n"); role = LINK_OFF; return 0; }
    active = 1;
    /* handshake: both sides say hello until each has heard the other */
    uint32_t t0 = now_ms(), last = 0;
    while (active && !got_hello && now_ms() - t0 < timeout_ms) {
        if (now_ms() - last >= 100) { put('H', 0, 0); last = now_ms(); }
        pump(0);
        nap();
    }
    if (!got_hello) { printf("link: no answer, playing alone\n"); transport_stop(); active = 0; role = LINK_OFF; return 0; }
    put('H', 0, 0);                 /* in case our earlier hellos were sent before the other side listened */
    printf("link: connected\n");
    return 1;
}

int link_exchange(unsigned frame, uint16_t local, uint16_t *host, uint16_t *join)
{
    unsigned ahead = frame + DELAY;
    local_input[ahead % HIST] = local;
    put('I', ahead, local);
    int slot = (int)(frame % HIST);
    uint32_t t0 = now_ms();
    while (active && remote_frame[slot] != (int32_t)frame) {
        pump(frame);
        if (remote_frame[slot] == (int32_t)frame) break;
        if (now_ms() - t0 > 5000) {
            printf("link: no input from the other console for 5 s, playing on alone\n");
            transport_stop();
            active = 0;
            break;
        }
        nap();
    }
    uint16_t mine = local_input[slot], theirs = active ? remote_input[slot] : 0;
    *host = (role == LINK_HOST) ? mine : theirs;
    *join = (role == LINK_HOST) ? theirs : mine;
    return active;
}

void link_check(unsigned frame, uint32_t hash)
{
    if (!active) return;
    int slot = (int)(frame % HIST);
    local_hash[slot] = hash;
    local_hash_frame[slot] = (int32_t)frame;
    put('L', frame, (uint16_t)hash);
    put('U', frame, (uint16_t)(hash >> 16));
    compare_hash(slot);
}
