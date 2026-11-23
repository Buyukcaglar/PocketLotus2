// SPDX-License-Identifier: GPL-3.0-or-later
`timescale 1ns/1ps
module tb_audio;
    reg pix=0,audio=0,reset=1;
    always #62.5 pix=~pix;
    always #40.690104 audio=~audio;
    reg [15:0] left=16'h1234,right=16'habcd;
    wire mclk,dac,lrck;
    pocket_audio dut(pix,audio,reset,left,right,mclk,dac,lrck);
    reg [15:0] captured;
    integer i,n;
    time oldframe,period;
    task channel(input polarity,input [15:0] expected);
        begin
            if(polarity) @(posedge lrck);else @(negedge lrck);
            // LRCLK changes at the derived SCLK falling edge. The first MSB
            // arrives one SCLK later (four MCLK periods), followed by 15 bits.
            @(negedge mclk);captured=0;
            for(i=0;i<31;i=i+1) begin
                repeat(4) @(negedge mclk);
                if(i<16) captured={captured[14:0],dac};
                else if(dac!==0)$fatal(1,"Nonzero I2S padding");
            end
            if(captured!==expected)$fatal(1,"I2S channel %b got %x expected %x",polarity,captured,expected);
        end
    endtask
    initial begin
        repeat(10) @(negedge mclk);reset=0;
        repeat(4) @(negedge lrck);
        oldframe=$time;
        @(negedge lrck);period=$time-oldframe;
        if(period<20832 || period>20834)$fatal(1,"I2S frame period %0t",period);
        for(n=0;n<3;n=n+1) begin channel(0,16'h1234);channel(1,16'habcd);end
        @(negedge pix);left=16'hfedc;right=16'h8001;
        repeat(3) @(negedge lrck);
        channel(0,16'hfedc);channel(1,16'h8001);
        reset=1;#1;
        if(lrck!==0 || dac!==0)$fatal(1,"Audio reset failed");
        $display("PASS I2S: 48kHz stereo, one-bit delay, MSB order, padding, coherent changed samples, reset");
        $finish;
    end
    initial begin #1000000;$fatal(1,"Audio timeout");end
endmodule
