// SPDX-License-Identifier: GPL-3.0-or-later
// APF reset/loading gate. Reset assertion is asynchronous; release is separately
// synchronized into CPU and video domains. Data-slot completion alone is not
// sufficient: queued external-memory writes must also drain without overrun.
`timescale 1ns/1ps
module pocket_reset(
    input bridge_clk, input sys_clk, input pix_clk, input pll_locked,
    input apf_reset_n, input loading, input allcomplete, input drained, input fault,
    output ready, output cpu_reset, output pix_reset
);
    reg complete=0;
    reg [7:0] settle=0;
    reg released=0;
    always @(posedge bridge_clk) begin
        if(!pll_locked | loading | fault) begin complete<=0;settle<=0;released<=0;end
        else begin
            if(allcomplete) complete<=1;
            if(!released) begin
                if(complete & drained) begin
                    if(&settle) released<=1;
                    else settle<=settle+1'b1;
                end else settle<=0;
            end
        end
    end
    // CPU/DMA traffic makes memory non-idle after release. Drain is a loading
    // fence, not a continuing reset condition; only a new load/fault revokes it.
    assign ready = released & !fault & pll_locked;
    wire hold_reset = !apf_reset_n | !ready;
    (* async_reg="true" *) reg [2:0] cpu_sync=7,pix_sync=7;
    always @(posedge sys_clk or posedge hold_reset)
        if(hold_reset) cpu_sync<=7;else cpu_sync<={cpu_sync[1:0],1'b0};
    always @(posedge pix_clk or posedge hold_reset)
        if(hold_reset) pix_sync<=7;else pix_sync<={pix_sync[1:0],1'b0};
    assign cpu_reset=cpu_sync[2];
    assign pix_reset=pix_sync[2];
endmodule
