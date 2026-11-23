// SPDX-License-Identifier: GPL-3.0-or-later
// Assert asynchronously, release after two local clock edges.
module reset_sync(input clk,input async_reset,output reset);
    (* async_reg="true" *) reg [1:0] stages=3;
    always @(posedge clk or posedge async_reset)
        if(async_reset) stages<=3;else stages<={stages[0],1'b0};
    assign reset=stages[1];
endmodule
