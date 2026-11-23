// SPDX-License-Identifier: GPL-3.0-or-later
// Slow external-memory flyback boundary: DMA data must not acknowledge a new
// CPU read or populate its cache line. Real MEMC, arbiter and pin controller.
`timescale 1ns/1ps
module tb_memc_flyback;
    reg clk=0,reset=1;
    always #11.904762 clk=~clk;
    reg cpu_cyc=0,cpu_stb=0,flyback=0,vidrq=0,hsync=1;
    reg [25:0] cpu_addr=26'h2010000;
    wire cpu_ack,cpu_err;
    wire [31:0] cpu_data;
    wire [21:0] ga,pa;
    wire gc,gs,gwe,gack,preq,pwe,pbusy,pdone,vidack;
    wire [31:0] grd,pwd,prd,hrd;
    wire [3:0] gsel,psel;
    reg hv=0,hwe=1;
    reg [21:0] ha=0;
    reg [31:0] hwd=0;
    wire ht,hd;
    memc memc(.clkcpu(clk),.rst_i(reset),.spvmd(1'b1),
        .cpu_address(cpu_addr),.cpu_cyc(cpu_cyc),.cpu_stb(cpu_stb),.cpu_we(1'b0),
        .cpu_sel(4'hf),.cpu_ack(cpu_ack),.cpu_err(cpu_err),.cpu_dout(cpu_data),
        .mem_addr_o(ga),.mem_cyc_o(gc),.mem_stb_o(gs),.mem_we_o(gwe),
        .mem_sel_o(gsel),.mem_dat_i(grd),.mem_ack_i(gack),
        .hsync(hsync),.flybk(flyback),.vidrq(vidrq),.vidak(vidack),.sndrq(1'b0));
    memory_arbiter arb(.clk(clk),.reset(reset),.g_cyc(gc),.g_stb(gs),.g_we(gwe),
        .g_addr(ga),.g_wdata(32'b0),.g_sel(gsel),.g_ack(gack),.g_rdata(grd),
        .h_valid(hv),.h_we(hwe),.h_addr(ha),.h_wdata(hwd),.h_sel(4'hf),
        .h_take(ht),.h_done(hd),.h_rdata(hrd),.p_req(preq),.p_we(pwe),.p_addr(pa),
        .p_wdata(pwd),.p_sel(psel),.p_busy(pbusy),.p_done(pdone),.p_rdata(prd));
    wire [21:16] a;
    wire [15:0] dq;
    wire adv,ce0,ce1,oe,we,ub,lb,wait_pin;
    psram_word ctl(.clk(clk),.reset(reset),.req(preq),.we(pwe),.addr(pa),
        .wdata(pwd),.sel(psel),.busy(pbusy),.done(pdone),.rdata(prd),
        .cram_a(a),.cram_dq(dq),.cram_wait(wait_pin),.cram_adv_n(adv),
        .cram_ce0_n(ce0),.cram_ce1_n(ce1),.cram_oe_n(oe),.cram_we_n(we),
        .cram_ub_n(ub),.cram_lb_n(lb));
    psram_model ram(a,dq,adv,ce0,ce1,oe,we,ub,lb,wait_pin);
    task store(input [21:0] addr,input [31:0] data);
        begin
            @(negedge clk);hv=1;ha=addr;hwd=data;
            while(!ht) @(negedge clk);
            hv=0;while(!hd) @(negedge clk);
        end
    endtask
    integer i,phase,video_beats=0;
    always @(posedge clk) if(reset) video_beats<=0;else if(vidack) video_beats<=video_beats+1;
    initial begin
        for(phase=0;phase<16;phase=phase+1) begin
            hsync=phase<8;
            reset=1;cpu_cyc=0;cpu_stb=0;cpu_addr=26'h2010000;flyback=0;vidrq=0;
            repeat(10) @(negedge clk);reset=0;
            for(i=0;i<4;i=i+1) begin
                store(i,32'h76543210+i);
                store(22'h004000+i,32'hcafe0000+i);
            end
            repeat(10) @(negedge clk);vidrq=1;
            if(phase%8<4) wait(arb.state==2 && arb.beat==phase%8);
            else wait(arb.state==3 && arb.beat==(phase%8)-4);
            @(negedge clk);vidrq=0;flyback=1;cpu_cyc=1;cpu_stb=1;
            wait(cpu_ack);#1;
            if(cpu_err || cpu_data!==32'hcafe0000)
                $fatal(1,"Flyback DMA crossed into CPU cache: phase=%0d CPU data=%x expected=cafe0000 arb=%0d",phase,cpu_data,arb.state);
            if(video_beats!=4)$fatal(1,"Outstanding DMA did not drain all four beats: %0d",video_beats);
            @(negedge clk);cpu_cyc=0;cpu_stb=0;
            repeat(10) @(negedge clk);cpu_addr=26'h2010004;cpu_cyc=1;cpu_stb=1;
            wait(cpu_ack);#1;
            if(cpu_data!==32'hcafe0001)$fatal(1,"CPU cache-hit data corrupt after DMA boundary");
            @(negedge clk);cpu_cyc=0;cpu_stb=0;
        end
        $display("PASS slow-memory flyback: sixteen video/cursor read/ACK boundary phases, four DMA beats drain before CPU cache read, correct CPU miss/hit data");
        $finish;
    end
    initial begin #200000;$fatal(1,"Flyback CPU timeout arb=%0d cpu_load=%b gc=%b gs=%b armed=%b",arb.state,memc.cpu_load,gc,gs,arb.guest_armed);end
endmodule
