// SPDX-License-Identifier: GPL-3.0-or-later
// Directed queue-boundary probe. Full-chipset ARM execution is tested separately.
`timescale 1ns/1ps
module tb_vidc_writes;
    reg clk=0,pix=0,pix_enable=1,reset=1;
    always #11.904762 clk=~clk;
    always #62.5 if(pix_enable) pix=~pix;
    reg request=0,raw_ack=0;
    reg [31:0] word=0;
    pocket_chipset chip(.clk(clk),.pix_clk(pix),.aud_ce(1'b0),.reset(reset),
        .video_reset(reset),.mem_rdata(32'b0),.mem_ack(1'b0),
        .keys(32'b0),.keys2(32'b0),.kbd_data(8'b0),.kbd_strobe(1'b0));
    integer sent=0,received=0,i;
    // Drive the queue's actual CPU/MEMC boundary, retaining the VIDC consumer.
    initial begin
        force chip.vidwrite=request;force chip.cyc=request;force chip.stb=request;
        force chip.memc_ack=raw_ack;force chip.wdata=word;
        force chip.rdata=32'heafffffe; // harmless ARM branch in the probe
    end
    always @(posedge pix) if(!reset && !chip.write_empty) begin
        if(chip.pixel_write!==32'h00001000+received)
            $fatal(1,"VIDC write lost/torn/reordered: %x at %0d",chip.pixel_write,received);
        received=received+1;
    end
    task send;
        begin
            @(negedge clk);request=1;raw_ack=1;word=32'h00001000+sent;
            // Hold the same request after ACK; it must be queued exactly once.
            repeat(3) @(negedge clk);
            request=0;raw_ack=0;sent=sent+1;
            repeat(2) @(negedge clk);
        end
    endtask
    initial begin
        #1000;reset=0;repeat(8) @(negedge pix);
        pix_enable=0;
        for(i=0;i<16;i=i+1) send();
        if(!chip.write_full || chip.vidc_writes.wp!=16)$fatal(1,"Queue did not fill exactly once per request");
        @(negedge clk);request=1;raw_ack=1;word=32'h00001000+sent;
        @(negedge clk);raw_ack=0;
        repeat(6) begin
            @(negedge clk);
            if(chip.ack || chip.write_push)$fatal(1,"CPU ACK/write escaped full queue");
        end
        pix_enable=1;
        wait(chip.ack);@(negedge clk); // retained ACK accepts pending word
        repeat(3) @(negedge clk);
        request=0;sent=sent+1;
        wait(received==17);repeat(5) @(negedge pix);
        for(i=0;i<32;i=i+1) send();
        wait(received==49);repeat(5) @(negedge pix);
        if(!chip.write_empty)$fatal(1,"Queue not drained");
        $display("PASS VIDC register queue: 49 ordered complete words, held request deduplication, full backpressure, retained MEMC ACK, wrap and drain");
        $finish;
    end
    initial begin #100000;$fatal(1,"Queue timeout sent=%0d received=%0d",sent,received);end
endmodule
