// SPDX-License-Identifier: GPL-3.0-or-later
// Independent bridge-domain liveness probes bypass the coherent status mailbox.
// Only divided-clock/count bits cross domains. Edge observations wrap modulo
// 256 and are NOT transaction counts. Flags use two individual capture stages;
// they describe stable stalls, not coherent state during an active transition.
`timescale 1ns/1ps
module pocket_probe #(parameter SYS_BIT=17, PIX_BIT=14)(
    input bridge_clk, input sys_clk, input pix_clk, input reset,
    input [3:0] activity, input [15:0] flags,
    output [63:0] snapshot
);
    reg [SYS_BIT:0] sys_ticks=0;
    reg [PIX_BIT:0] pix_ticks=0;
    always @(posedge sys_clk or posedge reset)
        if(reset) sys_ticks<=0; else sys_ticks<=sys_ticks+1'b1;
    always @(posedge pix_clk or posedge reset)
        if(reset) pix_ticks<=0; else pix_ticks<=pix_ticks+1'b1;
    wire [5:0] taps={activity,pix_ticks[PIX_BIT],sys_ticks[SYS_BIT]};
    (* async_reg="true" *) reg [5:0] tap_meta=0,tap_sync=0;
    (* async_reg="true" *) reg [15:0] flag_meta=0,flag_sync=0;
    reg [5:0] prior=0;
    reg [7:0] observations[0:5];
    integer i;
    initial for(i=0;i<6;i=i+1) observations[i]=0;
    always @(posedge bridge_clk) begin
        if(reset) begin
            tap_meta<=0;tap_sync<=0;flag_meta<=0;flag_sync<=0;prior<=0;
            for(i=0;i<6;i=i+1) observations[i]<=0;
        end else begin
            tap_meta<=taps;tap_sync<=tap_meta;
            flag_meta<=flags;flag_sync<=flag_meta;
            prior<=tap_sync;
            for(i=0;i<6;i=i+1)
                if(tap_sync[i]!=prior[i]) observations[i]<=observations[i]+1'b1;
        end
    end
    // Word 6 bytes LSB first: sys clock, pixel clock, CPU ACK, video ACK.
    // Word 7 bytes LSB first: sound ACK, peripheral ACK, flags low, flags high.
    assign snapshot={flag_sync,observations[5],observations[4],
                     observations[3],observations[2],observations[1],observations[0]};
endmodule
