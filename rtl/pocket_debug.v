// SPDX-License-Identifier: GPL-3.0-or-later
// Periodic coherent CPU/DMA snapshots through APF 0152 Debug Event Log.
// Markers D1A60000..D1A60007 precede six coherent words and two probe words.
// APF debug logging must be enabled. No guest memory access or execution stall.
`timescale 1ns/1ps
module pocket_debug #(parameter INTERVAL=37125000)(
    input clk,input reset,input running,input [255:0] snapshot,
    output event_valid,output [31:0] event_data,input event_ack
);
    localparam WAIT=0,MARK=1,DATA=2;
    reg [1:0] state=WAIT;
    reg [25:0] elapsed=0;
    reg [2:0] index=0;
    reg [255:0] captured=0;
    assign event_valid=state!=WAIT;
    assign event_data=state==MARK ? (32'hd1a60000 | {29'b0,index}) : captured[index*32 +: 32];
    always @(posedge clk) begin
        if(reset || !running) begin state<=WAIT;elapsed<=0;index<=0;captured<=0;end
        else case(state)
            WAIT: if(elapsed==INTERVAL-1) begin
                elapsed<=0;captured<=snapshot;index<=0;state<=MARK;
            end else elapsed<=elapsed+1'b1;
            MARK: if(event_ack) state<=DATA;
            DATA: if(event_ack) begin
                if(index==7) state<=WAIT;
                else begin index<=index+1'b1;state<=MARK;end
            end
        endcase
    end
endmodule
