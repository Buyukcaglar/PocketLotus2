// SPDX-License-Identifier: GPL-3.0-or-later
`timescale 1ns/1ps
`include "diagnostic_size.vh"
module tb_diagnostic;
    reg clk=0, pix=0, reset=1, guest_reset=1;
    always #11.904762 clk=~clk;
    always #62.5 pix=~pix;
    reg [2:0] auddiv=0;
    always @(posedge pix) auddiv<=auddiv+1'b1;
    wire [21:0] ga, pa;
    wire gc, gs, gwe, ga_ack, preq, pwe, pbusy, pdone;
    wire [3:0] gsel, psel;
    wire [31:0] gwd, grd, pwd, prd, hrd;
    reg hv=0, hwe=0;
    reg [21:0] ha=0;
    reg [31:0] hwd=0;
    reg [3:0] hsel=15;
    wire ht, hd, idle;
    wire [31:0] hc,gcnt,status,cpu_count,vc,sc,last,pc;
    wire hs,vs,de;
    wire [11:0] rgb;
    wire [15:0] al,ar;
    wire apf_hs,apf_vs,apf_de;
    wire [23:0] apf_rgb;
    pocket_video apf_video(pix,guest_reset,hs,vs,de,rgb,apf_hs,apf_vs,apf_de,apf_rgb);
    reg apf_previous_hs=0,apf_previous_vs=0,apf_previous_de=0;
    integer apf_cycle=0,apf_last_vs=-100,apf_last_hs=-100,apf_last_de=-100;
    integer apf_frames=0,apf_pixels=0,apf_lines=0,apf_width=0;
    always @(posedge pix) begin
        #1;
        if(status[31:16]==16'h600d) begin
            apf_cycle=apf_cycle+1;
            if(!apf_de && apf_rgb!==0)$fatal(1,"APF blanking RGB nonzero");
            if((apf_hs && apf_previous_hs) || (apf_vs && apf_previous_vs))$fatal(1,"APF sync pulse width");
            if(apf_vs) begin
                if(apf_frames>=1 && (apf_pixels!=81920 || apf_lines!=256))$fatal(1,"APF frame geometry");
                apf_frames=apf_frames+1;apf_pixels=0;apf_lines=0;apf_last_vs=apf_cycle;
            end
            if(apf_hs) begin
                if(apf_de || apf_cycle-apf_last_vs<4 || apf_cycle-apf_last_de<2)$fatal(1,"APF HS gap");
                apf_last_hs=apf_cycle;
            end
            if(apf_de) begin
                if(apf_cycle-apf_last_hs<2)$fatal(1,"APF DE gap");
                apf_pixels=apf_pixels+1;apf_width=apf_width+1;apf_last_de=apf_cycle;
            end
            if(apf_previous_de && !apf_de) begin
                if(apf_width!=320)$fatal(1,"APF active line width");
                apf_lines=apf_lines+1;apf_width=0;
            end
        end else begin apf_frames=0;apf_pixels=0;apf_lines=0;apf_width=0;end
        apf_previous_hs=apf_hs;apf_previous_vs=apf_vs;apf_previous_de=apf_de;
    end
    wire [21:16] a;
    wire [15:0] dq;
    wire adv,ce0,ce1,oe,we,ub,lb,wait_pin;
    pocket_chipset chip(.clk(clk),.pix_clk(pix),.aud_ce(auddiv==0),.reset(guest_reset),.video_reset(guest_reset),
        .mem_addr(ga),.mem_cyc(gc),.mem_stb(gs),.mem_we(gwe),.mem_sel(gsel),
        .mem_wdata(gwd),.mem_rdata(grd),.mem_ack(ga_ack),.keys(32'h10),.keys2(32'b0),
        .hs(hs),.vs(vs),.de(de),.rgb(rgb),.audio_l(al),.audio_r(ar),
        .diag_status(status),.cpu_count(cpu_count),.video_count(vc),.sound_count(sc),
        .last_cpu_addr(last),.peripheral_count(pc),.pixel_select(),
        .kbd_data(8'b0),.kbd_strobe(1'b0),.kbd_out(),.kbd_out_strobe());
    memory_arbiter arb(.clk(clk),.reset(reset),.g_cyc(gc & !guest_reset),.g_stb(gs),
        .g_we(gwe),.g_addr(ga),.g_wdata(gwd),.g_sel(gsel),.g_ack(ga_ack),.g_rdata(grd),
        .h_valid(hv),.h_we(hwe),.h_addr(ha),.h_wdata(hwd),.h_sel(hsel),
        .h_take(ht),.h_done(hd),.h_rdata(hrd),.p_req(preq),.p_we(pwe),.p_addr(pa),
        .p_wdata(pwd),.p_sel(psel),.p_busy(pbusy),.p_done(pdone),.p_rdata(prd),
        .idle(idle),.host_count(hc),.guest_count(gcnt));
    psram_word ctl(.clk(clk),.reset(reset),.req(preq),.we(pwe),.addr(pa),
        .wdata(pwd),.sel(psel),.busy(pbusy),.done(pdone),.rdata(prd),
        .cram_a(a),.cram_dq(dq),.cram_wait(wait_pin),.cram_clk(),.cram_adv_n(adv),
        .cram_cre(),.cram_ce0_n(ce0),.cram_ce1_n(ce1),.cram_oe_n(oe),
        .cram_we_n(we),.cram_ub_n(ub),.cram_lb_n(lb));
    psram_model ram(a,dq,adv,ce0,ce1,oe,we,ub,lb,wait_pin);
    reg [31:0] program_words[0:`DIAGNOSTIC_WORDS-1];
    reg [31:0] oldstatus;
    integer n,frames=0, pixels=0, colored=0, timer_events=0;
    integer qualified_frames=0,frame_pixels=0;
    integer video_underflows=0;
    time previous_frame=0;
    reg oldvs=1;
    integer trace_count=0;
    reg [31:0] watchdog_count=0;
    always begin
        #1000000;
        if(!guest_reset) begin
            $display("progress t=%0t status=%08x cpu=%0d last=%08x arb=%0d memc_cpu=%b video=%0d sound=%0d",$time,status,cpu_count,last,arb.state,chip.MEMC.cpu_load,vc,sc);
            if(watchdog_count==cpu_count)$fatal(1,"CPU made no progress for 1ms");
            watchdog_count=cpu_count;
        end
    end
    always @(posedge clk) if(!guest_reset && ga_ack && trace_count<32) begin
        $display("memory addr=%x data=%x we=%b CPUaddr=%x",ga,grd,gwe,chip.address);
        trace_count<=trace_count+1;
    end
    always @(posedge pix) begin
        oldvs<=vs;
        if (oldvs & !vs) begin frames<=frames+1; pixels<=0; end
        if (de) pixels<=pixels+1;
        if (de && rgb != 0 && ^rgb !== 1'bx) colored<=colored+1;
        if(qualified_frames>=1 && chip.VIDC.pix_ack && chip.VIDC.VIDEODMA.VIDEO_FIFO.empty)
            video_underflows<=video_underflows+1;
        if(status[31:16]!=16'h600d) begin qualified_frames<=0;frame_pixels<=0;previous_frame<=0;end
        else begin
            if(de) frame_pixels<=frame_pixels+1;
            if(oldvs & !vs) begin
                if(qualified_frames>=1 && frame_pixels!=81920)
                    $fatal(1,"VIDC frame dimensions: %0d pixels",frame_pixels);
                if(qualified_frames>=1 && $time-previous_frame!=19992875)
                    $fatal(1,"VIDC frame period: %0t",$time-previous_frame);
                qualified_frames<=qualified_frames+1;frame_pixels<=0;previous_frame<=$time;
            end
        end
    end
    always @(posedge clk) begin
        if (!guest_reset && chip.IOC.timer[0].reload) timer_events<=timer_events+1;
        if (status != oldstatus) begin
            $display("status=%08x CPU=%0d video=%0d sound=%0d t=%0t",status,cpu_count,vc,sc,$time);
            oldstatus<=status;
        end
        if (status[31:16] == 16'hbad0) $fatal(1,"ARM diagnostic failed at %08x",last);
    end
    task host_access(input wr, input [21:0] addr, input [31:0] data, input [3:0] mask);
        integer timeout;
        begin
            @(negedge clk); hv=1;hwe=wr;ha=addr;hwd=data;hsel=mask;
            timeout=0;
            while (!ht) begin @(negedge clk);timeout=timeout+1;
                if(timeout>1000)$fatal(1,"Host arbitration timeout");end
            hv=0;
            while (!hd) begin @(negedge clk);timeout=timeout+1;
                if(timeout>1000)$fatal(1,"Host completion timeout");end
        end
    endtask
    initial begin
        oldstatus=32'hffffffff;
        $readmemh("build/diagnostic/diagnostic.hex", program_words);
        repeat(10) @(negedge clk); reset=0;
        // Transfer through the real arbiter and pin controller, not RAM preload.
        for(n=0;n<`DIAGNOSTIC_WORDS;n=n+1) host_access(1,22'h100000+n,program_words[n],15);
        host_access(1,22'h080000,32'h11223344,15);
        host_access(1,22'h080000,32'hffffaaff,2);
        host_access(1,22'h080000,32'hbeef0000,12);
        host_access(0,22'h080000,0,15);
        if(hrd!==32'hbeefaa44)$fatal(1,"Host byte/halfword lanes: %x",hrd);
        repeat(10) @(negedge clk); guest_reset=0;
        wait(status[31:16]==16'h600d);
        // Exercise fair arbitration while real CPU, video and sound traffic run.
        for(n=0;n<64;n=n+1) begin
            host_access(1,22'h080010+n,32'h13570000+n,15);
            host_access(0,22'h080010+n,0,15);
            if(hrd!==32'h13570000+n)$fatal(1,"Contended host readback");
        end
        wait(qualified_frames>=3);
        repeat(10000) @(negedge clk);
        if(vc<100 || sc<100 || cpu_count<100 || pc<20 || colored<100 || timer_events<10)
            $fatal(1,"Inactive chipset vc=%0d sc=%0d pc=%0d rgb=%0d timers=%0d",vc,sc,pc,colored,timer_events);
        if(status!==32'h600d0010)$fatal(1,"Input is not observable: %08x",status);
        if(video_underflows!=0)$fatal(1,"VIDC pixel FIFO underflow: %0d",video_underflows);
        if (^al === 1'bx || ^ar === 1'bx || al==0 || ar==0) $fatal(1,"Inactive or unknown audio");
        $display("PASS ARM26+MEMC+VIDC+IOC: cpu=%0d peripheral=%0d video=%0d sound=%0d host=%0d colored=%0d timers=%0d audio=%x/%x underflows=%0d",
                 cpu_count,pc,vc,sc,hc,colored,timer_events,al,ar,video_underflows);
        $finish;
    end
    initial begin #250000000; $fatal(1,"Diagnostic timeout status=%08x CPU=%0d last=%08x",status,cpu_count,last); end
endmodule
