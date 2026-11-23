// SPDX-License-Identifier: GPL-3.0-or-later
// VIDC stereo output sampled through a request/ack mailbox at the 48kHz I2S
// frame rate. Audio MCLK=12.288MHz, SCLK=MCLK/4. The APF scaler transmits it on
// the audio pin at MCLK; data and LRCLK match PocketDoom's I2S framing reference.
`timescale 1ns/1ps
module pocket_audio(
    input pix_clk, input audio_clk, input reset,
    input [15:0] left, input [15:0] right,
    output mclk, output dac, output lrck
);
    wire pix_reset,audio_reset;
    reset_sync pix_reset_sync(pix_clk,reset,pix_reset);
    reset_sync audio_reset_sync(audio_clk,reset,audio_reset);
    reg [7:0] count=0;
    reg request=0,ack=0;
    reg [31:0] payload=0,samples=0;
    (* async_reg="true" *) reg [1:0] req_sync=0,ack_sync=0;
    always @(posedge pix_clk or posedge pix_reset) begin
        if(pix_reset) begin req_sync<=0;ack<=0;payload<=0;end
        else begin
            req_sync<={req_sync[0],request};
            if(req_sync[1]!=ack) begin payload<={left,right};ack<=req_sync[1];end
        end
    end
    reg serial=0;
    always @(posedge audio_clk or posedge audio_reset) begin
        if(audio_reset) begin count<=0;request<=0;ack_sync<=0;samples<=0;serial<=0;end
        else begin
            count<=count+1'b1;ack_sync<={ack_sync[0],ack};
            if(count==0 && ack_sync[1]==request) begin
                samples<=payload;request<=~request;
            end
            // One bit delay after LRCLK edge, then 16 bits and sixteen padding.
            if(count[1:0]==2'b11) begin
                if(count[6:2]<16)
                    serial<=count[7] ? samples[15-count[6:2]] : samples[31-count[6:2]];
                else serial<=0;
            end
        end
    end
    assign mclk=audio_clk;
    assign dac=serial;
    assign lrck=count[7];
endmodule
