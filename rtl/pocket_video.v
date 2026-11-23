// SPDX-License-Identifier: GPL-3.0-or-later
// Translate VIDC active-low, width-programmed syncs to APF event pulses.
// Preserve the guest's active pixels and timing; blank RGB is APF control data.
`timescale 1ns/1ps
module pocket_video(
    input clk, input reset,
    input hsync_n, input vsync_n, input active, input [11:0] rgb,
    output reg hs=0, output reg vs=0, output reg de=0,
    output reg [23:0] pixels=0
);
    reg previous_hs=0,previous_vs=0;
    reg pending_hs=0;
    reg [2:0] hs_delay=0;
    wire hs_event = !hsync_n & !previous_hs;
    wire vs_event = !vsync_n & !previous_vs;
    always @(posedge clk) begin
        if(reset) begin
            previous_hs<=0;previous_vs<=0;pending_hs<=0;hs_delay<=0;
            hs<=0;vs<=0;de<=0;pixels<=0;
        end else begin
            previous_hs<=!hsync_n;previous_vs<=!vsync_n;
            vs<=vs_event;hs<=0;
            de<=active;
            pixels<=active ? {{2{rgb[11:8]}},{2{rgb[7:4]}},{2{rgb[3:0]}}} : 24'b0;
            // VIDC begins HS and VS together. APF requires at least three
            // cycles after VS before HS; emit that first HS at cycle four.
            if(vs_event) begin
                pending_hs<=hs_event;hs_delay<=4;
            end else if(pending_hs) begin
                if(hs_delay==1) begin hs<=1;pending_hs<=0;hs_delay<=0;end
                else hs_delay<=hs_delay-1'b1;
            end else hs<=hs_event;
        end
    end
endmodule
