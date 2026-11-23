// SPDX-License-Identifier: GPL-3.0-or-later
// Real APF target FSM, Ready-to-Run priority, delayed host, coherent snapshots.
`timescale 1ns/1ps
module tb_debug;
    reg clk=0,reset=1,running=0,setup=0;
    always #6.734 clk=~clk;
    reg [255:0] snapshot={32'd8,32'd7,32'd6,32'd5,32'd4,32'd3,32'd2,32'd1};
    wire valid,ack;
    wire [31:0] event_data;
    reg [31:0] addr=0,wdata=0;
    reg rd=0,wr=0;
    wire [31:0] rdata;
    pocket_debug #(.INTERVAL(8)) sender(clk,reset,running,snapshot,valid,event_data,ack);
    core_bridge_cmd cmd(.clk(clk),.bridge_endian_little(1'b0),.bridge_addr(addr),
        .bridge_rd(rd),.bridge_rd_data(rdata),.bridge_wr(wr),.bridge_wr_data(wdata),
        .status_boot_done(1'b1),.status_setup_done(setup),.status_running(running),
        .debug_event_valid(valid),.debug_event_data(event_data),.debug_event_ack(ack),
        .target_dataslot_read(1'b0),.target_dataslot_write(1'b0),
        .target_dataslot_getfile(1'b0),.target_dataslot_openfile(1'b0));
    task read_word(input [31:0] location,output [31:0] value);
        begin @(negedge clk);addr=location;rd=1;
        @(negedge clk);value=rdata;rd=0;end
    endtask
    task host_complete;
        begin @(negedge clk);addr=32'hf8001000;wdata=32'h6f6b0000;wr=1;
        @(negedge clk);wr=0;repeat(4) @(negedge clk);end
    endtask
    reg [31:0] value,parameter_word;
    integer seen=0,i;
    initial begin
        repeat(10) @(negedge clk);reset=0;setup=1;running=1;
        repeat(20) @(negedge clk);
        read_word(32'hf8001000,value);
        if(value!==32'h636d0140)$fatal(1,"Debug request displaced Ready to Run: %x",value);
        repeat(10) @(negedge clk);read_word(32'hf8001000,value);
        if(value!==32'h636d0140)$fatal(1,"Ready to Run not held until host completion");
        host_complete;
        for(seen=0;seen<32;seen=seen+1) begin
            value=0;
            for(i=0;i<100 && value!=32'h636d0152;i=i+1) read_word(32'hf8001000,value);
            if(value!==32'h636d0152)$fatal(1,"Missing debug event");
            read_word(32'hf8001020,parameter_word);
            if(seen%2==0) begin
                if(parameter_word!==(32'hd1a60000+((seen%16)/2)))$fatal(1,"Debug marker order");
            end else if(parameter_word!==(((seen%16)/2)+1+(seen>=16 ? 10 : 0)))
                $fatal(1,"Snapshot torn or wrong word: seen=%0d data=%x",seen,parameter_word);
            // Change the live mailbox mid-burst. The first burst must stay coherent.
            if(seen==2) snapshot={32'd18,32'd17,32'd16,32'd15,32'd14,32'd13,32'd12,32'd11};
            repeat(10) @(negedge clk);
            read_word(32'hf8001020,value);
            if(value!==parameter_word)$fatal(1,"Parameters changed before host completion");
            host_complete;
        end
        // Cancel an unacknowledged event during reset, then require a fresh
        // Ready to Run. A missing host log ACK must not deadlock a reload.
        value=0;
        for(i=0;i<100 && value!=32'h636d0152;i=i+1) read_word(32'hf8001000,value);
        if(value!==32'h636d0152)$fatal(1,"No pending event to test cancellation");
        running=0;setup=0;repeat(5) @(negedge clk);
        if(valid)$fatal(1,"Logging continued during guest reset");
        read_word(32'hf8001000,value);
        if(value!==0)$fatal(1,"Unacknowledged log not canceled by reset");
        setup=1;repeat(10) @(negedge clk);read_word(32'hf8001000,value);
        if(value!==32'h636d0140)$fatal(1,"Logging blocked Ready to Run after reload");
        $display("PASS APF debug: Ready-to-Run priority/host fence, 32 ordered events, delayed host, coherent eight-word burst captures, reset cancellation/reload");
        $finish;
    end
    initial begin #100000;$fatal(1,"Debug timeout");end
endmodule
