"""SPDX-License-Identifier: GPL-3.0-or-later
Generate bounded port derivatives; original vendor bytes remain unchanged.
MEMC: split declaration initializers into prior declarations plus continuous
assignments for Icarus 14's forward-reference rules; drain accepted DMA before
flyback resets pointers so slow external reads cannot become CPU cache data.
VIDC FIFO: retain source notice and interface, replace binary-pointer CDC with
Gray pointers and independent synchronized reset release.
"""
from pathlib import Path
import re
from hdl_sources import ROOT


def main():
    out = ROOT / "build/ported"
    out.mkdir(parents=True, exist_ok=True)
    source = (ROOT / "rtl/vendor/archie/memc.v").read_text()
    declarations = []
    pattern = r"\bwire\s*(\[[^\]]+\])?\s+(\w+)\s*=\s*([^;]+);"
    def split(m):
        declarations.append(f"wire {m[1] or ''} {m[2]};")
        return f"assign {m[2]} = {m[3]};"
    source = re.sub(pattern, split, source)
    at = source.index("reg \t\t\trom_overlay;")
    source = source[:at] + "// Pocket port: declarations before uses; equations unchanged.\n" + "\n".join(declarations) + "\n\n" + source[at:]
    start = source.index("\t\tif (flybk == 1'b1) begin")
    end = source.index("\n\t\t// do the dma count", start)
    original = source[start:end]
    source = source[:start] + "`ifdef LEGACY_MEMC_FLYBACK\n" + original + "\n`else\n" + '''
        // Pocket: retain DMA ownership through the final ACK. Flyback can
        // begin while the asynchronous RAM controller still owns this burst.
        // Canceling it would route those outstanding words into a CPU cache
        // fill. Reset video/cursor pointers once the accepted burst drains.
        if (flybk == 1'b1 && !video_dma_ip) begin
            vid_address <= vid_init;
            cur_address <= cur_init;
        end
`endif
''' + source[end:]
    source = source.replace("if (vidrq  & ~dma_in_progress & ~cpu_load)", '''`ifdef LEGACY_MEMC_FLYBACK
        if (vidrq & ~dma_in_progress & ~cpu_load)
`else
        if (vidrq & ~flybk & ~dma_in_progress & ~cpu_load)
`endif''')
    (out / "memc.v").write_text(source)
    fifo = (ROOT / "rtl/vendor/archie/vidc/vidc_fifo.v").read_text()
    notice = fifo[:fifo.index("module vidc_fifo")]
    (out / "vidc_fifo.v").write_text(notice + (ROOT / "rtl/vidc_fifo_body.vh").read_text())
    # The upstream sound DMA instance omits stall. An unconnected input is Z
    # in simulation and can become an arbitrary constant in synthesis.
    vidc = (ROOT / "rtl/vendor/archie/vidc/vidc.v").read_text()
    # Cover an in-flight CPU line read plus the following video refill on the
    # slower asynchronous Pocket PSRAM bus. The MiSTer SDRAM FIFO was 8 words.
    vidc = vidc.replace("vidc_dmachannel VIDEODMA (", "vidc_dmachannel #(.FIFO_SIZE(5)) VIDEODMA (")
    vidc = vidc.replace("vidc_dmachannel SOUNDDMA (", "vidc_dmachannel SOUNDDMA (\n\t.stall (1'b0), // Pocket: sound DMA is never stalled by video sync.")
    # CPU writes now arrive as queued pixel-domain events, while the DMA side
    # remains on clkcpu. Apply palette/control, timing and audio configuration
    # in their consuming domain, removing the upstream unsynchronized buses.
    vidc = vidc.replace("wire cur_enabled;", "input hsync_cpu; // Pocket: synchronized DMA stall.\nwire cur_enabled;")
    # Non-ANSI input declaration also needs its name in the port list.
    vidc = vidc.replace("output reg    audio_sync\n", "output reg    audio_sync,\n    input hsync_cpu\n")
    vidc = vidc.replace("input hsync_cpu; // Pocket: synchronized DMA stall.\n", "")
    vidc = re.sub(r"(vidc_timing TIMING\([\s\S]*?\.clkcpu\s*\()\s*clkcpu", r"\1 clkpix", vidc)
    vidc = re.sub(r"(vidc_audio AUDIOMIXER\([\s\S]*?\.cpu_clk\s*\()\s*clkcpu", r"\1 clkpix", vidc)
    marker=vidc.index("// register write control.")
    prior=vidc.rfind("always @(posedge clkcpu)",0,marker)
    vidc=vidc[:prior]+vidc[prior:].replace("always @(posedge clkcpu)","always @(posedge clkpix)",1)
    vidc=re.sub(r"(\.stall\s*\()\s*~hsync",r"\1 ~hsync_cpu",vidc)
    vidc=re.sub(r"(\.stall\s*\()\s*hsync \|",r"\1 hsync_cpu |",vidc)
    (out / "vidc.v").write_text(vidc)
    audio = (ROOT / "rtl/vendor/archie/vidc/vidc_audio.v").read_text()
    # Explicit disabled power-up state. Without it a functional simulator can
    # run the sample divider before SFR is written, poisoning it with X.
    audio = re.sub(r"reg\s+\[8:0\]\s+vidc_sfr;", "reg [8:0] vidc_sfr = 0; // Pocket: disabled until first SFR write.", audio)
    (out / "vidc_audio.v").write_text(audio)
    # APF uses Quartus-specific inout reg declarations. Separate the external
    # tri-state nets from their procedural drive registers, preserving logic.
    for name in ("apf_top.v", "io_pad_controller.v", "io_bridge_peripheral.v", "core_bridge_cmd.v"):
        prefix = "core" if name == "core_bridge_cmd.v" else "apf"
        text = (ROOT / "rtl/vendor/pocket" / prefix / name).read_text(encoding="utf-8")
        declarations = []
        if name == "apf_top.v":
            for signal in ("scal_ddio_12", "scal_ddio_ctrl"):
                m = re.search(r"wire\s+\[[^\]]+\]\s+" + signal + r"\s*;", text)
                declarations.append(m[0]);text=text[:m.start()]+text[m.end():]
        if name == "io_pad_controller.v":
            start = text.index("    reg         reset_tr_n;")
            end = text.index("always @(posedge clk) begin", start)
            declarations.append(text[start:end]);text=text[:start]+text[end:]
        if name == "io_bridge_peripheral.v":
            for signal in ("rx_byte", "rx_byte_done"):
                m = re.search(r"reg\s+(?:\[[^\]]+\]\s+)?" + signal + r"\s*;", text)
                declarations.append(m[0]);text=text[:m.start()]+text[m.end():]
        if name == "core_bridge_cmd.v":
            text=text.replace("input   wire            status_running,", "input wire debug_event_valid,\ninput wire [31:0] debug_event_data,\noutput reg debug_event_ack = 0,\ninput   wire            status_running,")
            text=text.replace("// target > host command executer", "// Pocket: bounded 0152 events share the existing target command FSM.\n    debug_event_ack <= 0;\n    // target > host command executer")
            text=text.replace("end else if(target_dataslot_read_queue) begin", "end else if(debug_event_valid) begin\n            target_0 <= 32'h636d0152;target_20 <= debug_event_data;\n            debug_event_ack <= 1;tstate <= 4'd4;\n        end else if(target_dataslot_read_queue) begin")
            text=text.replace("TARG_ST_WAITRESULT_RTR: begin", "4'd4: begin // Logging must never block reset/reload bringup.\n        if(!status_running) begin target_0<=0;tstate<=TARG_ST_IDLE;end\n        else if(target_0[31:16] == 16'h6F6B) tstate <= TARG_ST_IDLE;\n    end\n    TARG_ST_WAITRESULT_RTR: begin")
            text = re.sub(r"reg\s+\[31:0\]\s+host_4C;", "reg [31:0] host_4C = 0; // Unused fourth response is deterministic.", text)
            # FPGA power-up zero was implicit upstream; make FSM startup
            # explicit in both simulation and the configuration image.
            text = re.sub(r"reg\s+\[3:0\]\s+hstate;", "reg [3:0] hstate = ST_IDLE;", text)
            text = re.sub(r"reg\s+\[3:0\]\s+tstate;", "reg [3:0] tstate = TARG_ST_IDLE;", text)
            text = re.sub(r"reg\s+host_cmd_start;", "reg host_cmd_start = 0;", text)
            for signal in ("b_datatable_q", "b_datatable_addr", "b_datatable_wren"):
                m = re.search(r"(?:reg|wire)\s+(?:\[[^\]]+\]\s+)?" + signal + r"\s*;", text)
                declarations.append(m[0]);text=text[:m.start()]+text[m.end():]
        for signal in ("phy_spimosi", "phy_spimiso", "phy_spiclk", "pad_1wire"):
            if re.search(r"inout\s+reg\s+" + signal, text):
                text = re.sub(r"inout\s+reg\s+" + signal, "inout wire " + signal, text)
                text = re.sub(r"\b" + signal + r"\s*<=", signal + "_drive <=", text)
                declarations.append(f"reg {signal}_drive;\nassign {signal} = {signal}_drive;")
        at = text.index(");", text.index("module ")) + 2
        text = text[:at] + "\n// Pocket portability: prior declarations and explicit tri-state drivers.\n" + "\n".join(declarations) + "\n" + text[at:]
        (out / name).write_text(text, encoding="utf-8")
    print("Prepared eight documented chipset/APF derivatives in build/ported")


if __name__ == "__main__":
    main()
