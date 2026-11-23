/* Bare-metal start-up for the QEMU "virt" instruction-count benchmark. */
    .section .text.start
    .globl _start
_start:
    la   sp, _stack_top
    li   t0, 0x6000              /* mstatus.FS: enable the FPU */
    csrs mstatus, t0
    la   t0, _bss_start
    la   t1, _bss_end
1:  bgeu t0, t1, 2f
    sw   zero, 0(t0)
    addi t0, t0, 4
    j    1b
2:  call main
    li   t0, 0x100000            /* SiFive test device: power off */
    li   t1, 0x5555
    sw   t1, 0(t0)
3:  j    3b

    .section .rodata
    .globl pack_image
    .globl pack_image_end
    .balign 4
pack_image:
    .incbin "lotus2.dat"
pack_image_end:
