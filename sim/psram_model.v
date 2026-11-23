// SPDX-License-Identifier: GPL-3.0-or-later
// Pin-level asynchronous PSRAM model with address latch, tri-state turn-around
// and independent byte enables. Checks conservative cycle timing. It does not
// model analog SI, package delays, retention or undocumented WAIT behavior.
`timescale 1ns/1ps
module psram_model(
    input [21:16] a, inout [15:0] dq,
    input adv_n, ce0_n, ce1_n, oe_n, we_n, ub_n, lb_n,
    output wait_pin
);
    reg [15:0] memory[0:(1<<23)-1]; // both 8MiB dies on CRAM0
    reg [22:0] address;
    time latched_at, write_at;
    wire selected = !ce0_n | !ce1_n;
    assign wait_pin = 1;
    wire [15:0] read_data;
    assign #(70) read_data = memory[address]; // conservative asynchronous tAA
    assign dq = selected & adv_n & !oe_n & we_n ? read_data : 16'hzzzz;
    always @(posedge adv_n) if (selected) begin
        address = {ce0_n,a,dq};
        latched_at = $time;
        if (ce0_n == ce1_n) $fatal(1,"Both PSRAM dies selected");
        if (^dq === 1'bx) $fatal(1,"Unknown latched PSRAM address");
    end
    always @(negedge we_n) if (selected) write_at = $time;
    always @(posedge we_n) if (selected & adv_n) begin
        if ($time - write_at < 45) $fatal(1,"PSRAM tWP violated");
        if ($time - latched_at < 70) $fatal(1,"PSRAM tAW violated");
        if (!lb_n) memory[address][7:0] = dq[7:0];
        if (!ub_n) memory[address][15:8] = dq[15:8];
        if ((!lb_n || !ub_n) && (^dq === 1'bx)) $fatal(1,"Unknown PSRAM write data");
    end
endmodule
