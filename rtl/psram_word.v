// SPDX-License-Identifier: GPL-3.0-or-later
// Conservative asynchronous CellularRAM controller, 42 MHz clock.
// Each 32-bit word uses two addressed 16-bit cycles. No guessed burst mode,
// refresh commands or reliance on WAIT in asynchronous mode. Byte masks are
// latched with each command and driven independently for both halfwords.
`timescale 1ns/1ps
module psram_word #(
    parameter ACCESS_CYCLES = 6, parameter RECOVERY_CYCLES = 2
)(
    input clk, input reset, input req, input we,
    input [21:0] addr, input [31:0] wdata, input [3:0] sel,
    output reg busy, output reg done, output reg [31:0] rdata,
    output [21:16] cram_a, inout [15:0] cram_dq, input cram_wait,
    output cram_clk, output reg cram_adv_n, output cram_cre,
    output reg cram_ce0_n, output reg cram_ce1_n,
    output reg cram_oe_n, output reg cram_we_n,
    output reg cram_ub_n, output reg cram_lb_n,
    output [2:0] debug_state
);
    localparam IDLE=0, ADDR=1, HOLD=2, DATA=3, ACCESS=4, RECOVER=5;
    reg [2:0] state = IDLE;
    assign debug_state=state;
    reg [21:0] lat_addr;
    reg [31:0] lat_data;
    reg [3:0] lat_sel;
    reg lat_we, half;
    reg [7:0] count;
    reg drive;
    reg [15:0] dq_out;
    wire [22:0] half_addr = {lat_addr,half};
    assign cram_a = half_addr[21:16];
    assign cram_dq = drive ? dq_out : 16'hzzzz;
    assign cram_clk = 0;
    assign cram_cre = 0;
    always @(posedge clk) begin
        done <= 0;
        if (reset) begin
            state <= IDLE; busy <= 0; drive <= 0; half <= 0; count <= 0;
            cram_adv_n <= 1; cram_ce0_n <= 1; cram_ce1_n <= 1;
            cram_oe_n <= 1; cram_we_n <= 1; cram_ub_n <= 1; cram_lb_n <= 1;
            rdata <= 0; lat_addr <= 0; lat_data <= 0; lat_sel <= 0; lat_we <= 0;
        end else case (state)
            IDLE: if (req) begin
                lat_addr <= addr; lat_data <= wdata; lat_sel <= sel; lat_we <= we;
                half <= 0; busy <= 1; state <= ADDR;
            end
            ADDR: begin
                cram_ce0_n <= half_addr[22]; cram_ce1_n <= ~half_addr[22];
                cram_adv_n <= 0; drive <= 1; dq_out <= half_addr[15:0];
                cram_oe_n <= 1; cram_we_n <= 1;
                cram_lb_n <= ~lat_sel[half ? 2 : 0];
                cram_ub_n <= ~lat_sel[half ? 3 : 1];
                count <= 1; state <= HOLD;
            end
            HOLD: if (count == 0) begin
                cram_adv_n <= 1; state <= DATA;
            end else count <= count - 1'b1;
            DATA: begin
                // Address remains driven for one full clock after ADV rises.
                drive <= lat_we;
                dq_out <= half ? lat_data[31:16] : lat_data[15:0];
                cram_oe_n <= lat_we; cram_we_n <= ~lat_we;
                count <= ACCESS_CYCLES - 1; state <= ACCESS;
            end
            ACCESS: if (count == 0) begin
                if (!lat_we) begin
                    if (half) rdata[31:16] <= cram_dq;
                    else rdata[15:0] <= cram_dq;
                end
                cram_we_n <= 1; cram_oe_n <= 1;
                count <= RECOVERY_CYCLES - 1; state <= RECOVER;
            end else count <= count - 1'b1;
            RECOVER: if (count == 0) begin
                cram_ce0_n <= 1; cram_ce1_n <= 1; drive <= 0;
                cram_ub_n <= 1; cram_lb_n <= 1;
                if (!half) begin half <= 1; state <= ADDR; end
                else begin busy <= 0; done <= 1; state <= IDLE; end
            end else count <= count - 1'b1;
        endcase
    end
endmodule
