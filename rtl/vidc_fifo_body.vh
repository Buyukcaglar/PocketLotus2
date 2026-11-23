// SPDX-License-Identifier: GPL-3.0-or-later
// Pocket CDC replacement; original FIFO notice is prepended by prepare_chipset.
module vidc_fifo #(parameter FIFO_SIZE=3)(
    input rst, wr_clk, wr_en, input [31:0] din,
    input rd_clk, rd_ce, rd_en, output reg [7:0] dout=0,
    output [FIFO_SIZE-1:0] wr_ptr, output [FIFO_SIZE-1:0] space,
    output full, output empty
);
    localparam DEPTH=1<<FIFO_SIZE;
    reg [31:0] data[0:DEPTH-1];
    reg [FIFO_SIZE:0] wp=0, rp=0;
    (* preserve, dont_merge *) reg [FIFO_SIZE:0] wg=0, rg=0;
    reg [1:0] byteptr=0;
    (* async_reg="true" *) reg [FIFO_SIZE:0] rg1=0,rg2=0,wg1=0,wg2=0;
    (* async_reg="true" *) reg [1:0] wr_reset=3,rd_reset=3;
    function [FIFO_SIZE:0] binary;
        input [FIFO_SIZE:0] gray;
        integer i;
        begin
            binary[FIFO_SIZE]=gray[FIFO_SIZE];
            for(i=FIFO_SIZE-1;i>=0;i=i-1) binary[i]=binary[i+1]^gray[i];
        end
    endfunction
    wire [FIFO_SIZE:0] used = wp - binary(rg2);
    wire [FIFO_SIZE:0] freewords = DEPTH - used;
    assign wr_ptr = wp[FIFO_SIZE-1:0];
    assign space = freewords[FIFO_SIZE-1:0];
    assign full = used == DEPTH;
    assign empty = rg == wg2;
    always @(posedge wr_clk or posedge rst)
        if(rst) wr_reset<=3; else wr_reset<={wr_reset[0],1'b0};
    always @(posedge rd_clk or posedge rst)
        if(rst) rd_reset<=3; else rd_reset<={rd_reset[0],1'b0};
    always @(posedge wr_clk) begin
        if(wr_reset[1]) begin wp<=0;wg<=0;rg1<=0;rg2<=0;end
        else begin
            rg1<=rg;rg2<=rg1;
            if(wr_en & !full) begin
                data[wp[FIFO_SIZE-1:0]]<=din;
                wp<=wp+1'b1;wg<=((wp+1'b1)>>1)^(wp+1'b1);
            end
        end
    end
    always @(posedge rd_clk) begin
        if(rd_reset[1]) begin rp<=0;rg<=0;wg1<=0;wg2<=0;byteptr<=0;dout<=0;end
        else begin
            wg1<=wg;wg2<=wg1;
            if(rd_ce & rd_en) begin
                dout <= empty ? 8'b0 : data[rp[FIFO_SIZE-1:0]][byteptr*8 +: 8];
                if(!empty) begin
                    byteptr<=byteptr+1'b1;
                    if(byteptr==3) begin
                        rp<=rp+1'b1;rg<=((rp+1'b1)>>1)^(rp+1'b1);
                    end
                end
            end
        end
    end
endmodule
