// SPDX-License-Identifier: GPL-3.0-or-later
`timescale 1ns/1ps
`include "diagnostic_size.vh"
module tb_apf_boot;
    reg clk=0;
    always #6.734007 clk=~clk;
    reg [31:0] addr=0,wd=0;
    reg wr=0,rd=0;
    wire [31:0] data;
    wire [21:16] a;
    wire [15:0] dq;
    wire adv,ce0,ce1,oe,we,ub,lb,wait_pin;
    wire [23:0] video_rgb;
    wire video_de,video_hs,video_vs,pix,pix90;
    core_top dut(.clk_74a(clk),.clk_74b(clk),.bridge_addr(addr),.bridge_wr(wr),
        .bridge_rd(rd),.bridge_wr_data(wd),.bridge_rd_data(data),
        .cont1_key(32'h10),.cont2_key(32'b0),.cont3_key(32'b0),.cont4_key(32'b0),
        .cont1_joy(32'b0),.cont2_joy(32'b0),.cont3_joy(32'b0),.cont4_joy(32'b0),
        .cont1_trig(16'b0),.cont2_trig(16'b0),.cont3_trig(16'b0),.cont4_trig(16'b0),
        .cram0_a(a),.cram0_dq(dq),.cram0_adv_n(adv),.cram0_ce0_n(ce0),
        .cram0_ce1_n(ce1),.cram0_oe_n(oe),.cram0_we_n(we),.cram0_ub_n(ub),
        .cram0_lb_n(lb),.cram0_wait(wait_pin),.video_rgb(video_rgb),
        .video_de(video_de),.video_hs(video_hs),.video_vs(video_vs),
        .video_rgb_clock(pix),.video_rgb_clock_90(pix90));
    psram_model ram(a,dq,adv,ce0,ce1,oe,we,ub,lb,wait_pin);
    reg [31:0] program_words[0:`DIAGNOSTIC_WORDS-1];
    integer n;
    reg [31:0] response;
`ifdef LONG_APF_DIAGNOSTIC
    // Accelerate only the debug reporting interval in this long functional run.
    defparam dut.debug_events.INTERVAL=742500;
    wire [11:0] rgb_pins,control_pins,clock_pins;
    mf_ddio_bidir_12 vd(.datain_h(video_rgb[23:12]),.datain_l(video_rgb[11:0]),
        .outclock(pix),.oe(1'b1),.padio(rgb_pins));
    mf_ddio_bidir_12 vc(.datain_h({8'b0,video_vs,video_hs,video_de,1'b0}),
        .datain_l({8'b0,video_vs,video_hs,video_de,1'b0}),.outclock(pix),.oe(1'b1),.padio(control_pins));
    mf_ddio_bidir_12 vk(.datain_h(12'hfff),.datain_l(12'b0),
        .outclock(pix90),.oe(1'b1),.padio(clock_pins));
    reg [11:0] first_rgb;
    reg [3:0] first_controls;
    integer exported_frames=0,exported_pixels=0,exported_lines=0,exported_width=0;
    integer exported_cycle=0,last_vs=-100,last_hs=-100,last_de=-100;
    reg old_hs=0,old_vs=0,old_de=0;
    time previous_frame=0;
    always @(posedge clock_pins[0]) begin first_rgb=rgb_pins;first_controls=control_pins[3:0];end
    always @(negedge clock_pins[0]) begin
        if(dut.diag_status[31:16]==16'h600d) begin
            exported_cycle=exported_cycle+1;
            if(first_controls!==control_pins[3:0])$fatal(1,"Core DDR control halves disagree");
            if(!first_controls[1] && {first_rgb,rgb_pins}!==24'b0)$fatal(1,"Core DDR blanking RGB");
            if((first_controls[2] && old_hs) || (first_controls[3] && old_vs))$fatal(1,"Core DDR sync width");
            if(first_controls[3]) begin
                if(exported_frames>=1 && (exported_pixels!=81920 || exported_lines!=256 || $time-previous_frame!=19992875))
                    $fatal(1,"Core DDR geometry/cadence pixels=%0d lines=%0d",exported_pixels,exported_lines);
                exported_frames=exported_frames+1;exported_pixels=0;exported_lines=0;last_vs=exported_cycle;previous_frame=$time;
            end
            if(first_controls[2]) begin
                if(first_controls[1] || exported_cycle-last_vs<4 || exported_cycle-last_de<2)$fatal(1,"Core DDR HS gap");
                last_hs=exported_cycle;
            end
            if(first_controls[1]) begin
                if(exported_cycle-last_hs<2)$fatal(1,"Core DDR DE gap");
                exported_pixels=exported_pixels+1;exported_width=exported_width+1;last_de=exported_cycle;
            end
            if(old_de && !first_controls[1]) begin
                if(exported_width!=320)$fatal(1,"Core DDR line width");
                exported_lines=exported_lines+1;exported_width=0;
            end
        end else begin exported_frames=0;exported_pixels=0;exported_lines=0;exported_width=0;end
        old_hs=first_controls[2];old_vs=first_controls[3];old_de=first_controls[1];
    end
    integer events=0,marker=0,success_bursts=0;
    reg [31:0] logged[0:7];
    reg [31:0] parameter_word,prior_cpu=0,prior_probe=0;
    always begin #1000000;$display("APF progress t=%0t status=%x frames=%0d events=%0d",$time,dut.diag_status,exported_frames,events);end
`endif
    // Command handler byte-swaps when bridge_endian_little is one, as in APF.
    function [31:0] swap(input [31:0] x);
        swap={x[7:0],x[15:8],x[23:16],x[31:24]};
    endfunction
    task write_bridge(input [31:0] location,input [31:0] value);
        begin
            @(negedge clk);addr=location;wd=value;wr=1;
            @(negedge clk);wr=0;
            repeat(87) @(negedge clk);
        end
    endtask
    task read_command_word(input [31:0] location,output [31:0] value);
        begin
            @(negedge clk);addr=location;rd=1;
            @(negedge clk);value=swap(data);rd=0;
            repeat(87) @(negedge clk);
        end
    endtask
    task command(input [15:0] code,input [15:0] result);
        begin
            write_bridge(32'hf8000000,swap({16'h434d,code}));
            read_command_word(32'hf8000000,response);
            if(response!=={16'h4f4b,result})
                $fatal(1,"APF command %x returned %x",code,response);
        end
    endtask
    initial begin
        $readmemh("build/diagnostic/diagnostic.hex",program_words);
        repeat(100) @(negedge clk);
        if(!dut.cpu_reset)$fatal(1,"Guest started before load");
        // Follow Analogue's Core Boot Process: Setup precedes assets; the host
        // WRITES a slot into the core using 0082, then waits for Ready to Run.
        command(16'h0000,2);
        command(16'h0010,0);
        write_bridge(32'hf8000020,swap(1));
        write_bridge(32'hf8000024,swap(4*`DIAGNOSTIC_WORDS));
        command(16'h0082,2); // unsupported write slot must use the current ID
        write_bridge(32'hf8000020,swap(0));
        command(16'h0082,0);
        for(n=0;n<`DIAGNOSTIC_WORDS;n=n+1)
            write_bridge(32'h00400000+n*4,program_words[n]);
        command(16'h008f,0);
        command(16'h0090,0);
        repeat(400) @(negedge clk);
        read_command_word(32'hf8001000,response);
        if(response!==32'h636d0140)$fatal(1,"Missing Ready to Run: %x",response);
        if(!dut.cpu_reset)$fatal(1,"Guest started before Reset Exit");
        command(16'h0000,3);
        write_bridge(32'hf8001000,swap(32'h6f6b0000));
        command(16'h0011,0);
        wait(!dut.cpu_reset);
        wait(dut.diag_status==2);
        if(dut.cpu_count<20 || dut.host_fault)$fatal(1,"APF load/CPU inactive");
        command(16'h0010,0);
        if(!dut.cpu_reset)$fatal(1,"APF reset enter failed");
        // A second 0082 must revoke the latched release from the first load.
        // This detects a gate still wired to request-read even if writes ACK.
        command(16'h0082,0);
        if(dut.ready)$fatal(1,"0082 reload did not revoke Ready to Run");
        for(n=0;n<`DIAGNOSTIC_WORDS;n=n+1)
            write_bridge(32'h00400000+n*4,program_words[n]);
        command(16'h008f,0);
        repeat(400) @(negedge clk);
        read_command_word(32'hf8001000,response);
        if(!dut.ready || !dut.cpu_reset || response!==32'h636d0140)
            $fatal(1,"Reload fence/Ready to Run failed");
        write_bridge(32'hf8001000,swap(32'h6f6b0000));
        command(16'h0011,0);
        wait(!dut.cpu_reset);
        wait(dut.diag_status==2);
`ifdef LONG_APF_DIAGNOSTIC
        // Run the entire core_top after real APF loading and service its 0152
        // target requests while ARM, DMA and serialized video remain live.
        while(exported_frames<3 || success_bursts<2 || events%16!=0) begin
            read_command_word(32'hf8001000,response);
            if(response==32'h636d0152) begin
                read_command_word(32'hf8001020,parameter_word);
                if(events%2==0) begin
                    marker=(events%16)/2;
                    if(parameter_word!==32'hd1a60000+marker)$fatal(1,"Core debug event marker");
                end else begin
                    logged[marker]=parameter_word;
                    if(marker==7 && logged[0][31:16]==16'h600d) begin
                        if(logged[0]!==32'h600d0010 || logged[1]<=prior_cpu || logged[2]==0 || logged[3]==0 || logged[4]==0)
                            $fatal(1,"Core CPU/DMA snapshot inactive or failed");
                        if(logged[6][7:0]==prior_probe[7:0] || logged[6][15:8]==prior_probe[15:8] ||
                           logged[7][31:28]!==4'h9)$fatal(1,"Independent clock/reset probes inactive");
                        prior_probe=logged[6];prior_cpu=logged[1];success_bursts=success_bursts+1;
                    end
                end
                events=events+1;
                write_bridge(32'hf8001000,swap(32'h6f6b0000));
            end
            if(dut.diag_status[31:16]==16'hbad0 || dut.host_fault)$fatal(1,"Core execution/host failure");
        end
        $display("PASS sustained APF core: load/reload, ARM success/input, CPU/video/sound progress, coherent status and independent clock/reset probes through 0152 events=%0d, three frame boundaries at DDR pins with 320x256/gaps/blanking/19.992875ms checks",events);
`endif
        command(16'h0010,0);
        $display("PASS documented APF boot: BRIDGE status Setup/Idle, unsupported write ID rejected, 0082 %0d-byte load, 008f drain, 0140 Ready to Run handshake, reset-exit/ARM word/byte test/reset-enter, second 0082 reload revokes ready and re-executes ARM",4*`DIAGNOSTIC_WORDS);
        $finish;
    end
`ifdef LONG_APF_DIAGNOSTIC
    initial begin #150000000;$fatal(1,"Sustained APF timeout status=%x",dut.diag_status);end
`else
    initial begin #3000000; $fatal(1,"APF boot timeout status=%x",dut.diag_status);end
`endif
endmodule
