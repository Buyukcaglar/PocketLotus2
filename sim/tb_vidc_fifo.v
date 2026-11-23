// SPDX-License-Identifier: GPL-3.0-or-later
`timescale 1ns/1ps
module tb_vidc_fifo;
    reg wc=0,rc=0,reset=1,wen=0,ren=0,ce=0;
    always #11.904762 wc=~wc;
    always #62.5 rc=~rc;
    reg [31:0] din=0;
    wire [7:0] dout;
    wire [1:0] space;
    wire full,empty;
    vidc_fifo #(.FIFO_SIZE(2)) dut(.rst(reset),.wr_clk(wc),.wr_en(wen),.din(din),
        .rd_clk(rc),.rd_ce(ce),.rd_en(ren),.dout(dout),.space(space),.full(full),.empty(empty),.wr_ptr());
    function [31:0] word_value(input integer n);
        word_value=32'h30201000+n*32'h01010101;
    endfunction
    integer round,n,b;
    reg [31:0] expected;
    task write_word(input [31:0] value);
        begin @(negedge wc);din=value;wen=1;@(negedge wc);wen=0;end
    endtask
    initial begin
        repeat(6) @(negedge rc);reset=0;
        repeat(6) @(negedge rc);
        if(!empty || full)$fatal(1,"FIFO reset with read enable stopped");
        for(round=0;round<32;round=round+1) begin
            for(n=0;n<4;n=n+1) write_word(word_value(round*4+n));
            repeat(4)@(negedge wc);
            if(!full || space!=0)$fatal(1,"FIFO full accounting");
            write_word(32'hdeadbeef); // rejected, must not overwrite oldest data
            repeat(4)@(negedge rc);
            for(n=0;n<4;n=n+1) begin
                expected=word_value(round*4+n);
                for(b=0;b<4;b=b+1) begin
                    @(negedge rc);ce=1;ren=1;
                    @(negedge rc);ce=0;ren=0;
                    if(dout!==expected[b*8+:8])$fatal(1,"FIFO byte ordering/wrap round=%0d word=%0d byte=%0d got=%x",round,n,b,dout);
                    repeat(b%3) @(negedge rc);
                end
            end
            repeat(4)@(negedge wc);
            if(!empty || full)$fatal(1,"FIFO empty accounting");
            @(negedge rc);ce=1;ren=1;@(negedge rc);ce=0;ren=0;
            if(dout!==0)$fatal(1,"FIFO underflow must output silence");
        end
        reset=1;repeat(4)@(negedge rc);
        if(!empty || full || dout!==0)$fatal(1,"FIFO reset failed");
        $display("PASS VIDC CDC FIFO: 128 words / 512 ordered bytes, wrap/full, ignored overflow, empty silence, CE stalls, reset");
        $finish;
    end
    initial begin #1000000;$fatal(1,"VIDC FIFO timeout");end
endmodule
