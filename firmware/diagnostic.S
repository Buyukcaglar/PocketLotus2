@ SPDX-License-Identifier: GPL-3.0-or-later
@ Original ARM2/ARM26 diagnostic. No RISC OS or proprietary ROM required.
@ This deliberately uses ARMv2 instructions: ARM2 has no native STRH/LDRH.
@ The halfword test uses two byte stores and verifies all four lanes together.
@ ROM is loaded through APF into physical PSRAM at byte offset 0x00400000.
@ MEMC's reset overlay aliases it at zero; the first instruction relocates PC.
    ldr pc, =start
    b fail
    b fail
    b fail
    b fail
    b fail
    b fail
    b fail
start:
    ldr r10, =0x03260000
    mov r0, #1
    str r0, [r10]
    ldr r1, =0x02010000
    ldr r2, =0x12345678
    str r2, [r1]
    ldr r3, [r1]
    cmp r3, r2
    bne fail
    mov r2, #0xa5
    strb r2, [r1, #1]
    mov r2, #0x5a
    strb r2, [r1, #2]
    mov r2, #0xc3
    strb r2, [r1, #3]
    ldr r2, =0xc35aa578
    ldr r3, [r1]
    cmp r3, r2
    bne fail
    ldrb r3, [r1, #1]
    cmp r3, #0xa5
    bne fail
    mov r0, #2
    str r0, [r10]
@ IOC control is written on D23:D16 and read in the low byte.
    ldr r1, =0x03200000
    ldr r2, =0x00150000
    str r2, [r1]
    ldr r3, [r1]
    and r3, r3, #0x3e
    cmp r3, #0x14
    bne fail
@ Program IOC timer 0. Timer input is a multiple of sixteen in this baseline.
    ldr r2, =0x00400000
    str r2, [r1, #0x40]
    mov r2, #0
    str r2, [r1, #0x44]
    str r2, [r1, #0x48]
    mov r0, #3
    str r0, [r10]
@ Fill a complete 320x256 4bpp display, 40960 bytes, with original test pixels.
    ldr r1, =0x02000000
    ldr r2, =0x76543210
    mov r3, r2
    mov r4, r2
    mov r5, r2
    mov r6, r2
    mov r7, r2
    mov r8, r2
    mov r9, r2
    ldr r11, =1280
fill:
    stmia r1!, {r2-r9}
    subs r11, r11, #1
    bne fill
@ Distinct 256-byte synthetic sound buffer at physical 0x18000.
    ldr r1, =0x02018000
    ldr r2, =0x20202020
    mov r4, #64
soundfill:
    str r2, [r1]
    add r1, r1, #4
    subs r4, r4, #1
    cmp r4, #32
    bne soundcontinue
    ldr r2, =0x21212121
soundcontinue:
    cmp r4, #0
    bne soundfill
@ MEMC control: 32KiB pages (4MiB), video/sound DMA enabled; no OS mode.
    ldr r1, =0x03600000
    str r2, [r1]
    ldr r1, =0x03620000
    str r2, [r1]
    ldr r1, =0x036427fc
    str r2, [r1]
    ldr r1, =0x03686000
    str r2, [r1]
    ldr r1, =0x036a603c
    str r2, [r1]
    ldr r1, =0x036c0000
    str r2, [r1]
@ DMA must be enabled only after its pointers have valid buffer addresses.
    ldr r1, =0x036e0c0c
    str r2, [r1]
@ VIDC register table uses live palette and timing writes through the real bus.
    ldr r1, =0x03400000
    ldr r5, =vidc_table
    ldr r4, =vidc_end
vidc_loop:
    ldr r2, [r5]
    str r2, [r1]
    add r5, r5, #4
    cmp r5, r4
    bne vidc_loop
    ldr r0, =0x600d0000
    str r0, [r10]
@ Live heartbeat combines input with success signature. CPU keeps executing
@ RAM reads/writes alongside video and sound DMA; failures remain observable.
    ldr r1, =0x02010010
    mov r6, #0
heartbeat:
    add r6, r6, #1
    str r6, [r1]
    ldr r7, [r1]
    cmp r6, r7
    bne fail
    ldr r7, [r10, #4]
    and r7, r7, #0xff
    ldr r0, =0x600d0000
    orr r0, r0, r7
    str r0, [r10]
    b heartbeat
fail:
    ldr r10, =0x03260000
    ldr r0, =0xbad00001
    str r0, [r10]
    b fail
vidc_table:
@ Palette 0..7 is diagnostic artwork, produced by the retained VIDC DAC.
    .word 0x00000000, 0x0400000f, 0x080000f0, 0x0c0000ff
    .word 0x10000f00, 0x14000f0f, 0x18000ff0, 0x1c000fff
@ 511 pixels x 313 lines at requested 8 MHz = 50.018 Hz. Active 320x256.
@ H timing stores half the count in bits22:14, V timing bits23:14.
    .word 0x803fc000, 0x84030000, 0x880c0000, 0x8c0c0000
    .word 0x90340000, 0x94340000
    .word 0xa04e0000, 0xa4008000, 0xa8080000, 0xac080000
    .word 0xb0480000, 0xb4480000
@ Disable cursor, select 4bpp and baseline 8 MHz pixel mode.
    .word 0xb8ffc000, 0xbcffc000, 0xe0000008
@ Stereo center, all eight channels; sample divider 31 on 1MHz enable.
    .word 0x64000004, 0x68000004, 0x6c000004, 0x70000004
    .word 0x74000004, 0x78000004, 0x7c000004, 0x60000004
    .word 0xc000011f
vidc_end:
