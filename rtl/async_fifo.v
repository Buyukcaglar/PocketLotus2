// SPDX-License-Identifier: GPL-3.0-or-later
// Dual-clock FIFO with Gray pointers. Reset both domains together; do not reset
// this FIFO for guest reset. Bundled payload is stable before synchronized
// write pointer exposes it to the reader.
`timescale 1ns/1ps
module async_fifo #(parameter WIDTH=59, parameter LGDEPTH=4)(
    input wclk, input rclk, input reset,
    input push, input [WIDTH-1:0] wdata, output full,
    input pop, output [WIDTH-1:0] rdata, output empty
);
    wire wr_reset,rd_reset;
    reset_sync wr_reset_sync(wclk,reset,wr_reset);
    reset_sync rd_reset_sync(rclk,reset,rd_reset);
    reg [WIDTH-1:0] data[0:(1<<LGDEPTH)-1];
    reg [LGDEPTH:0] wp=0, rp=0;
    // Keep Gray MSBs distinct from binary MSBs so timing bounds cover every bit.
    (* preserve, dont_merge *) reg [LGDEPTH:0] wg=0, rg=0;
    (* async_reg = "true" *) reg [LGDEPTH:0] rg1=0, rg2=0, wg1=0, wg2=0;
    wire [LGDEPTH:0] wnext = wp + 1'b1;
    wire [LGDEPTH:0] wnextg = (wnext >> 1) ^ wnext;
    // Full compares current pointer, allowing the final free entry to be used.
    assign full = wg == {~rg2[LGDEPTH:LGDEPTH-1],rg2[LGDEPTH-2:0]};
    assign empty = rg == wg2;
    assign rdata = data[rp[LGDEPTH-1:0]];
    always @(posedge wclk or posedge wr_reset) begin
        if (wr_reset) begin wp<=0; wg<=0; rg1<=0; rg2<=0; end
        else begin
            rg1 <= rg; rg2 <= rg1;
            if (push & !full) begin
                data[wp[LGDEPTH-1:0]] <= wdata;
                wp <= wnext; wg <= wnextg;
            end
        end
    end
    always @(posedge rclk or posedge rd_reset) begin
        if (rd_reset) begin rp<=0; rg<=0; wg1<=0; wg2<=0; end
        else begin
            wg1 <= wg; wg2 <= wg1;
            if (pop & !empty) begin
                rp <= rp + 1'b1;
                rg <= ((rp + 1'b1) >> 1) ^ (rp + 1'b1);
            end
        end
    end
endmodule
