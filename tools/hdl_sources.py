"""SPDX-License-Identifier: GPL-3.0-or-later
One reviewed chipset source list for simulation and Quartus. Excludes optional
unused Amber FPGA shifter/decompiler and the upstream board/ROM peripherals.
"""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
AMBER = (
    "a23_barrel_shift.v a23_wishbone.v a23_register_bank.v a23_multiply.v "
    "a23_fetch.v a23_execute.v a23_decode.v a23_coprocessor.v a23_cache.v "
    "a23_alu.v sram_byte_en.v sram_line_en.v a23_core.v"
).split()
CHIPSET = ["rtl/vendor/archie/amber/" + s for s in AMBER]
CHIPSET += ["rtl/vendor/archie/" + s for s in ("memc.v", "memc_translator.v", "ioc.v", "ioc_irq.v", "latches.v")]
CHIPSET += ["rtl/vendor/archie/vidc/" + s for s in ("vidc.v", "vidc_timing.v", "vidc_fifo.v", "vidc_dmachannel.v", "vidc_audio.v")]
CORE = ["rtl/pocket_chipset.v", "rtl/memory_arbiter.v", "rtl/psram_word.v", "rtl/async_fifo.v", "rtl/reset_sync.v", "rtl/pocket_video.v", "rtl/pocket_debug.v", "rtl/pocket_probe.v"]
CHIPSET = ["build/ported/memc.v" if s.endswith("/memc.v") else
           "build/ported/vidc_fifo.v" if s.endswith("/vidc_fifo.v") else
           "build/ported/vidc_audio.v" if s.endswith("/vidc_audio.v") else
           "build/ported/vidc.v" if s.endswith("/vidc.v") else s for s in CHIPSET]
