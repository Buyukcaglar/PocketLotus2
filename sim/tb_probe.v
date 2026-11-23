// SPDX-License-Identifier: GPL-3.0-or-later
// Independent observability while ACKs or generated clocks stop. No mailbox.
`timescale 1ns/1ps
module tb_probe;
    reg bridge_clk=0,sys_clk=0,pix_clk=0,reset=1;
    reg sys_run=1,pix_run=1,ack_run=1;
    reg [3:0] activity=0;
    reg [15:0] flags=0;
    always #5 bridge_clk=~bridge_clk;
    always #12 if(sys_run) sys_clk=~sys_clk;
    always #31 if(pix_run) pix_clk=~pix_clk;
    always @(negedge sys_clk) if(ack_run) activity<=activity+1'b1;
    wire [63:0] snapshot;
    pocket_probe #(.SYS_BIT(2),.PIX_BIT(1)) dut(bridge_clk,sys_clk,pix_clk,reset,activity,flags,snapshot);
    reg [63:0] first,second;
    initial begin
        repeat(10) @(negedge bridge_clk);reset=0;flags=16'h1234;
        repeat(200) @(negedge bridge_clk);first=snapshot;
        repeat(200) @(negedge bridge_clk);second=snapshot;
        if(second[63:48]!==16'h1234)$fatal(1,"Stable probe flags not captured");
        if(first[7:0]==second[7:0] || first[15:8]==second[15:8] ||
           first[31:16]==second[31:16] || first[47:32]==second[47:32])
            $fatal(1,"Live clocks/ACK transitions not independently observable");
        ack_run=0;repeat(20) @(negedge bridge_clk);first=snapshot;
        repeat(200) @(negedge bridge_clk);second=snapshot;
        if(first[47:16]!==second[47:16] || first[15:0]==second[15:0])
            $fatal(1,"Stopped ACKs not distinguished from live clocks");
        sys_run=0;pix_run=0;repeat(20) @(negedge bridge_clk);first=snapshot;
        flags=16'habcd;repeat(200) @(negedge bridge_clk);second=snapshot;
        if(first[47:0]!==second[47:0] || second[63:48]!==16'habcd)
            $fatal(1,"Bridge probe failed while generated clocks stopped");
        reset=1;repeat(10) @(negedge bridge_clk);
        if(snapshot!==0)$fatal(1,"Probe reset failed with stopped clocks");
        $display("PASS independent probes: live clocks/ACKs, stalled ACKs with clocks live, stopped generated clocks with bridge flags updating, reset while stopped");
        $finish;
    end
endmodule
