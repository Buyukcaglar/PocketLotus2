// SPDX-License-Identifier: GPL-3.0-or-later
`timescale 1ns/1ps
module tb_psram;
    reg clk=0,reset=1,req=0,wr=0;
    always #11.904762 clk=~clk;
    reg [21:0] address=0;
    reg [31:0] data=0;
    reg [3:0] mask=15;
    wire busy,done;
    wire [31:0] q;
    wire [21:16] a;
    wire [15:0] dq;
    wire adv,ce0,ce1,oe,we,ub,lb,wait_pin;
    psram_word ctl(.clk(clk),.reset(reset),.req(req),.we(wr),.addr(address),
        .wdata(data),.sel(mask),.busy(busy),.done(done),.rdata(q),
        .cram_a(a),.cram_dq(dq),.cram_wait(wait_pin),.cram_clk(),.cram_adv_n(adv),
        .cram_cre(),.cram_ce0_n(ce0),.cram_ce1_n(ce1),.cram_oe_n(oe),
        .cram_we_n(we),.cram_ub_n(ub),.cram_lb_n(lb));
    psram_model ram(a,dq,adv,ce0,ce1,oe,we,ub,lb,wait_pin);
    task access(input writing,input [21:0] addr,input [31:0] value,input [3:0] lanes);
        integer cycles;
        begin
            @(negedge clk);req=1;wr=writing;address=addr;data=value;mask=lanes;
            @(negedge clk);req=0;
            if(!busy)$fatal(1,"PSRAM command not captured");
            // Bus inputs may change once accepted. All physical halves/masks
            // must still use the latched command, not these new values.
            address=~addr;data=~value;mask=~lanes;
            cycles=0;
            while(!done) begin @(negedge clk);cycles=cycles+1;
                if(cycles>100)$fatal(1,"PSRAM handshake timeout");end
            if(busy || !ce0 || !ce1 || !we || !oe)$fatal(1,"Done before physical recovery");
        end
    endtask
    initial begin
        repeat(8)@(negedge clk);reset=0;
        access(1,0,32'h11223344,15);
        access(1,22'h200000,32'h55667788,15);
        access(0,0,0,15);if(q!==32'h11223344)$fatal(1,"Die address alias");
        access(0,22'h200000,0,15);if(q!==32'h55667788)$fatal(1,"Die 1 read");
        access(1,22'h200000,32'haaffffbb,9);
        access(0,22'h200000,0,15);if(q!==32'haa6677bb)$fatal(1,"Independent low/high byte lanes");
        access(1,22'h1fffff,32'habcdef98,15);
        access(0,22'h1fffff,0,15);if(q!==32'habcdef98)$fatal(1,"Die 0 boundary read");
        access(1,22'h200000,0,0);
        access(0,22'h200000,0,15);if(q!==32'haa6677bb)$fatal(1,"Zero mask modified RAM");
        $display("PASS physical PSRAM: both dies, boundary, no alias, latched address/data/masks, byte lanes, 70ns reads, commit/recovery acknowledgement");
        $finish;
    end
    initial begin #100000;$fatal(1,"PSRAM timeout");end
endmodule
