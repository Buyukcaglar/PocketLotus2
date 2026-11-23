// SPDX-License-Identifier: GPL-3.0-or-later
// Receiver-side APF protocol assertions against width-programmed guest timing.
`timescale 1ns/1ps
module tb_video;
    reg clk=0,reset=1;
    always #62.5 clk=~clk;
    reg hsync_n=1,vsync_n=1,active=0;
    reg [11:0] rgb=12'hfff;
    wire hs,vs,de;
    wire [23:0] pixels;
`ifdef LEGACY_APF_VIDEO
    // Former core_top assignments, retained solely as a failing regression.
    assign hs=~hsync_n;assign vs=~vsync_n;assign de=active & !reset;
    assign pixels={{2{rgb[11:8]}},{2{rgb[7:4]}},{2{rgb[3:0]}}};
`else
    pocket_video dut(clk,reset,hsync_n,vsync_n,active,rgb,hs,vs,de,pixels);
`endif
    integer x,y,f,cycle=0,last_vs=-100,last_hs=-100,last_de=-100;
    integer frames=0,frame_pixels=0,lines=0,line_pixels=0,hs_count=0;
    reg was_hs=0,was_vs=0,was_de=0;
    time frame_start=0;
    always @(posedge clk) begin
        #1;
        if(!reset) begin
            cycle=cycle+1;
            if(!de && pixels!==0)$fatal(1,"APF blank RGB is a scaler command: %x",pixels);
            if(hs && was_hs)$fatal(1,"APF HS wider than one cycle");
            if(vs && was_vs)$fatal(1,"APF VS wider than one cycle");
            if(vs) begin
                if(frames>0) begin
                    if(frame_pixels!=81920 || lines!=256 || hs_count!=313)
                        $fatal(1,"APF frame shape pixels=%0d lines=%0d HS=%0d",frame_pixels,lines,hs_count);
                    if($time-frame_start!=19992875)$fatal(1,"APF guest frame timing changed");
                end
                frames=frames+1;frame_pixels=0;lines=0;hs_count=0;
                frame_start=$time;last_vs=cycle;
            end
            if(hs) begin
                if(de || cycle-last_vs<4 || cycle-last_de<2)$fatal(1,"APF HS gap violation");
                hs_count=hs_count+1;last_hs=cycle;
            end
            if(de) begin
                if(cycle-last_hs<2)$fatal(1,"APF DE gap violation");
                frame_pixels=frame_pixels+1;line_pixels=line_pixels+1;last_de=cycle;
                if(pixels!==24'hff00ff)$fatal(1,"Active VIDC pixels changed");
            end
            if(was_de && !de) begin
                if(line_pixels!=320)$fatal(1,"APF line width %0d",line_pixels);
                lines=lines+1;line_pixels=0;
            end
            was_hs=hs;was_vs=vs;was_de=de;
        end
    end
    initial begin
        repeat(8) @(negedge clk);reset=0;
        for(f=0;f<3;f=f+1) for(y=0;y<313;y=y+1) for(x=0;x<511;x=x+1) begin
            @(negedge clk);
            hsync_n=!(x<25);vsync_n=!(y<3);
            active=(x>=96 && x<416 && y>=32 && y<288);
            rgb=active ? 12'hf0f : 12'hfff;
        end
        @(negedge clk);hsync_n=0;vsync_n=0;active=0;
        repeat(2) @(negedge clk);
        if(frames!=4)$fatal(1,"Missing frames");
        $display("PASS APF video: three 320x256 frames, 511x313 timing, single-cycle HS/VS, VS/HS/DE gaps, zero blank RGB, unchanged active pixels");
        $finish;
    end
    initial begin #70000000;$fatal(1,"APF video timeout");end
endmodule
