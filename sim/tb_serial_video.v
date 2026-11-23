// SPDX-License-Identifier: GPL-3.0-or-later
// Decode the APF DDR pins using the installed Intel megafunction model.
// Covers serialization and alignment, not electrical board timing or scaler IP.
`timescale 1ns/1ps
module tb_serial_video;
    reg clk=0,clk90=0,reset=1;
    always #62.5 clk=~clk;
    initial begin #31.25;forever #62.5 clk90=~clk90;end
    reg hsync_n=1,vsync_n=1,active=0;
    reg [11:0] rgb=12'hfff;
    wire hs,vs,de;
    wire [23:0] pixels;
    pocket_video dut(clk,reset,hsync_n,vsync_n,active,rgb,hs,vs,de,pixels);
    wire [11:0] pins,controls,clock_pin;
    // Exact three DDR instances/word order used by pinned APF apf_top.v.
    mf_ddio_bidir_12 data_ddr(.datain_h(pixels[23:12]),.datain_l(pixels[11:0]),
        .outclock(clk),.oe(1'b1),.padio(pins));
    mf_ddio_bidir_12 control_ddr(.datain_h({8'b0,vs,hs,de,1'b0}),
        .datain_l({8'b0,vs,hs,de,1'b0}),.outclock(clk),.oe(1'b1),.padio(controls));
    mf_ddio_bidir_12 clock_ddr(.datain_h(12'hfff),.datain_l(12'b0),
        .outclock(clk90),.oe(1'b1),.padio(clock_pin));
    reg [23:0] expected=0;
    reg [3:0] expected_controls=0;
    always @(posedge clk) begin expected<=pixels;expected_controls<={vs,hs,de,1'b0};end
    reg [11:0] high_half;
    reg [3:0] first_control;
    reg [23:0] decoded;
    reg oldhs=0,oldvs=0,oldde=0;
    integer cycle=0,lastvs=-100,lasths=-100,lastde=-100;
    integer frames=0,count=0,lines=0,width=0,hs_count=0;
    time frame_start=0;
    always @(posedge clock_pin[0]) begin high_half=pins;first_control=controls[3:0];end
    always @(negedge clock_pin[0]) begin
        decoded={high_half,pins};
        if(!reset) begin
            if(decoded!==expected || first_control!==expected_controls || controls[3:0]!==first_control)
                $fatal(1,"DDR pixel/control alignment mismatch decoded=%x expected=%x ctrl=%x/%x expected=%x",decoded,expected,first_control,controls[3:0],expected_controls);
            cycle=cycle+1;
            if(!first_control[1] && decoded!==0)$fatal(1,"Serialized blanking RGB");
            if((first_control[2] && oldhs) || (first_control[3] && oldvs))$fatal(1,"Serialized sync width");
            if(first_control[3]) begin
                if(frames>0 && (count!=81920 || lines!=256 || hs_count!=313 || $time-frame_start!=19992875))
                    $fatal(1,"Serialized frame geometry/cadence: pixels=%0d lines=%0d HS=%0d",count,lines,hs_count);
                frames=frames+1;count=0;lines=0;hs_count=0;frame_start=$time;lastvs=cycle;
            end
            if(first_control[2]) begin
                if(first_control[1] || cycle-lastvs<4 || cycle-lastde<2)$fatal(1,"Serialized HS gap");
                lasths=cycle;hs_count=hs_count+1;
            end
            if(first_control[1]) begin
                if(cycle-lasths<2 || decoded!==24'hff00ff)$fatal(1,"Serialized active pixel");
                count=count+1;width=width+1;lastde=cycle;
            end
            if(oldde && !first_control[1]) begin
                if(width!=320)$fatal(1,"Serialized line width");
                lines=lines+1;width=0;
            end
            oldhs=first_control[2];oldvs=first_control[3];oldde=first_control[1];
        end
    end
    integer f,y,x;
    initial begin
        repeat(8) @(negedge clk);reset=0;
        for(f=0;f<3;f=f+1) for(y=0;y<313;y=y+1) for(x=0;x<511;x=x+1) begin
            @(negedge clk);hsync_n=!(x<25);vsync_n=!(y<3);
            active=(x>=96 && x<416 && y>=32 && y<288);rgb=active ? 12'hf0f : 12'hfff;
        end
        @(negedge clk);hsync_n=0;vsync_n=0;active=0;
        repeat(4) @(negedge clk);
        if(frames!=4)$fatal(1,"Missing serialized frames");
        $display("PASS Intel-model APF DDR pins: three 320x256 frames, RGB halves/control alignment, sync gaps, zero blank RGB, 19.992875ms cadence");
        $finish;
    end
    initial begin #70000000;$fatal(1,"Serialized video timeout");end
endmodule
