// SPDX-License-Identifier: GPL-3.0-or-later
// Pocket wiring for the pinned Archie ARM26/MEMC/VIDC/IOC modules.
// Disk controllers are deliberately absent from this ROM-free diagnostic.
`timescale 1ns/1ps
module pocket_chipset(
    input clk, input pix_clk, input aud_ce, input reset, input video_reset,
    output [21:0] mem_addr, output mem_cyc, output mem_stb,
    output mem_we, output [3:0] mem_sel, output [31:0] mem_wdata,
    input [31:0] mem_rdata, input mem_ack,
    input [31:0] keys, input [31:0] keys2,
    output hs, output vs, output de, output [11:0] rgb,
    output [15:0] audio_l, output [15:0] audio_r,
    output [31:0] diag_status, output [31:0] cpu_count,
    output [31:0] video_count, output [31:0] sound_count,
    output [31:0] last_cpu_addr, output [31:0] peripheral_count,
    output [1:0] pixel_select,
    input [7:0] kbd_data, input kbd_strobe,
    output [7:0] kbd_out, output kbd_out_strobe
);
    wire [31:0] address, wdata, rdata, memc_data;
    wire [3:0] sel;
    wire cyc, stb, we, ack, err, supervisor, irq, fiq;
    wire flyback, vidreq, vidack, sndreq, sndack, vidwrite;
    wire memc_ack,write_full,write_empty;
    wire [31:0] pixel_write;
    reg write_pending=0,write_seen=0;
    wire write_cycle=vidwrite & cyc & stb;
    assign ack=vidwrite ? ((memc_ack | write_pending) & !write_full) : memc_ack;
    wire write_push=write_cycle & ack & !write_seen;
    always @(posedge clk) begin
        if(reset | !write_cycle) begin write_pending<=0;write_seen<=0;end
        else begin
            if(memc_ack) write_pending<=1;
            if(write_push) begin write_pending<=0;write_seen<=1;end
        end
    end
    // Apply complete register-write events in the pixel domain. CPU ACK is
    // fenced by space; a full queue retains the pending MEMC ACK and CPU word.
    async_fifo #(.WIDTH(32)) vidc_writes(.wclk(clk),.rclk(pix_clk),
        .reset(reset | video_reset),.push(write_push),.wdata(wdata),.full(write_full),
        .pop(!write_empty),.rdata(pixel_write),.empty(write_empty));
    (* async_reg="true" *) reg [1:0] hs_sync=0,fly_sync=0;
    always @(posedge clk) begin
        if(reset) begin hs_sync<=0;fly_sync<=0;end
        else begin hs_sync<={hs_sync[0],hs};fly_sync<={fly_sync[0],flyback};end
    end
    wire ioc_cs, romlow, ram_cs, sirq_n;
    wire [2:0] cti;
    wire [5:0] cin, cout;
    wire [7:1] ioc_select;
    wire sext, ce2m, ce7m;
    wire [7:0] ioc_data, latch_data;
    wire latch_en = ioc_cs & ioc_select[5] & (address[20:19] == 2);
    // IOC bank 6 is an explicitly diagnostic-only observation peripheral.
    wire diag_en = ioc_cs & address[21] & (address[18:16] == 6);
    reg [31:0] status = 0, cycles = 0, vc = 0, sc = 0, pc = 0, last_addr = 0;
    reg diag_write_seen = 0;
    wire [31:0] diag_read = address[5:2] == 0 ? status :
                            address[5:2] == 1 ? keys :
                            address[5:2] == 2 ? cycles :
                            address[5:2] == 3 ? vc :
                            address[5:2] == 4 ? sc : 32'h504c3031;
    assign rdata = diag_en ? diag_read :
                   latch_en ? {24'b0,latch_data} :
                   ioc_cs & ~sext ? {24'b0,ioc_data} :
                   ram_cs ? memc_data : 32'hffffffff;
    assign mem_wdata = wdata;
    assign diag_status = status;
    assign cpu_count = cycles;
    assign video_count = vc;
    assign sound_count = sc;
    assign peripheral_count = pc;
    assign last_cpu_addr = last_addr;
    always @(posedge clk) begin
        if (reset) begin
            status <= 0; cycles <= 0; vc <= 0; sc <= 0; pc <= 0;
            last_addr <= 0; diag_write_seen <= 0;
        end else begin
            if (ack & cyc & stb) begin
                cycles <= cycles + 1'b1;
                last_addr <= address;
                if (ioc_cs | vidwrite | (address[25:21] == 5'b11011)) pc <= pc + 1'b1;
            end
            if (vidack) vc <= vc + 1'b1;
            if (sndack) sc <= sc + 1'b1;
            if (!(diag_en & cyc & stb & we)) diag_write_seen <= 0;
            else if (!diag_write_seen) begin
                status <= wdata;
                diag_write_seen <= 1;
            end
        end
    end
    a23_core ARM(
        .i_clk(clk), .i_reset(reset), .i_system_rdy(~reset),
        .o_wb_cyc(cyc), .o_wb_stb(stb), .o_wb_we(we),
        .o_wb_adr(address), .o_wb_sel(sel), .o_wb_dat(wdata),
        .i_wb_dat(rdata), .i_wb_ack(ack), .i_wb_err(err),
        .o_wb_tga(supervisor), .i_irq(irq), .i_firq(fiq));
    memc MEMC(
        .clkcpu(clk), .rst_i(reset), .spvmd(supervisor),
        .cpu_address(address[25:0]), .cpu_cyc(cyc), .cpu_stb(stb),
        .cpu_we(we), .cpu_sel(sel), .cpu_ack(memc_ack), .cpu_err(err), .cpu_dout(memc_data),
        .mem_addr_o(mem_addr), .mem_cyc_o(mem_cyc), .mem_stb_o(mem_stb),
        .mem_we_o(mem_we), .mem_sel_o(mem_sel), .mem_cti_o(cti),
        .mem_dat_i(mem_rdata), .mem_ack_i(mem_ack),
        .hsync(hs_sync[1]), .flybk(fly_sync[1]), .vidrq(vidreq), .vidak(vidack),
        .sndrq(sndreq), .sndak(sndack), .vidw(vidwrite),
        .ioc_cs(ioc_cs), .rom_low_cs(romlow), .ram_cs(ram_cs), .sirq_n(sirq_n));
    vidc #(.CLKCPU(42000000)) VIDC(
        .clkcpu(clk), .clkpix(pix_clk), .cepix(1'b1), .selpix(pixel_select),
        .ceaud(aud_ce), .rst_i(video_reset), .cpu_dat(pixel_write), .viddat(mem_rdata),
        .flybk(flyback), .vidak(vidack), .vidrq(vidreq), .sndak(sndack), .sndrq(sndreq),
        .vidw(!write_empty), .hsync_cpu(hs_sync[1]), .hsync(hs), .vsync(vs), .video_r(rgb[11:8]),
        .video_g(rgb[7:4]), .video_b(rgb[3:0]), .video_en(de),
        .audio_l(audio_l), .audio_r(audio_r), .audio_sync());
    ioc IOC(
        .clkcpu(clk), .clk2m_en(ce2m), .clk7m_en(ce7m), .por(reset), .ir(fly_sync[1]),
        .fh(2'b00), .il({6'b111111,sirq_n,1'b1}), .c_in(cin), .c_out(cout),
        .select(ioc_select), .sext(sext), .wb_adr(address[6:2]),
        .wb_stb(stb & address[21] & ioc_cs), .wb_cyc(cyc & address[21] & ioc_cs),
        .wb_we(we), .wb_dat_i(wdata[23:16]), .wb_dat_o(ioc_data),
        .wb_bank(address[18:16]), .irq(irq), .firq(fiq),
        .kbd_out_data(kbd_out), .kbd_out_strobe(kbd_out_strobe),
        .kbd_in_data(kbd_data), .kbd_in_strobe(kbd_strobe));
    // CMOS line pulled high until the later RTC/CMOS gate.
    assign cin = {cout[5:1],1'b1};
    latches LATCHES(
        .clkcpu(clk), .wb_cyc(cyc & latch_en), .wb_stb(stb & latch_en),
        .wb_we(we & latch_en), .wb_dat_i(wdata[23:16]), .wb_dat_o(latch_data),
        .wb_adr(address[15:2]), .joy0(~{keys[4],keys[3:0]}),
        .joy1(~{keys2[4],keys2[3:0]}), .floppy_drive(), .floppy_motor(),
        .floppy_inuse(), .floppy_side(), .floppy_density(), .floppy_reset(),
        .baseclk(), .syncpol());
endmodule
