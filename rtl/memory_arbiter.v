// SPDX-License-Identifier: GPL-3.0-or-later
// MEMC and APF arbitration. Four-word wrapping reads are atomic because MEMC
// fills a cache line or DMA FIFO. Host and guest alternate at transaction
// boundaries under contention. Physical writes complete before acknowledgement.
`timescale 1ns/1ps
module memory_arbiter(
    input clk, input reset,
    input g_cyc, input g_stb, input g_we, input [21:0] g_addr,
    input [31:0] g_wdata, input [3:0] g_sel,
    output reg g_ack, output reg [31:0] g_rdata,
    input h_valid, input h_we, input [21:0] h_addr,
    input [31:0] h_wdata, input [3:0] h_sel,
    output reg h_take, output reg h_done, output reg [31:0] h_rdata,
    output reg p_req, output reg p_we, output reg [21:0] p_addr,
    output reg [31:0] p_wdata, output reg [3:0] p_sel,
    input p_busy, input p_done, input [31:0] p_rdata,
    output idle, output reg [31:0] host_count, output reg [31:0] guest_count,
    output [3:0] debug_state
);
    localparam IDLE=0, ISSUE=1, WAIT=2, DELIVER=3, GAP=4;
    reg [2:0] state;
    reg host, last_host, guest_armed;
    reg [1:0] beat;
    reg [21:0] base;
    reg [31:0] line[0:3];
    assign debug_state={guest_armed,state};
    assign idle = (state == IDLE) & ~h_valid;
    always @(posedge clk) begin
        p_req <= 0; g_ack <= 0; h_take <= 0; h_done <= 0;
        if (reset) begin
            state <= IDLE; host <= 0; last_host <= 0; guest_armed <= 1;
            beat <= 0; base <= 0; p_addr <= 0; p_we <= 0; p_sel <= 0; p_wdata <= 0;
            g_rdata <= 0; h_rdata <= 0; host_count <= 0; guest_count <= 0;
        end else begin
            if (!(g_cyc & g_stb)) guest_armed <= 1;
            case (state)
                IDLE: if (h_valid & (!(g_cyc & g_stb & guest_armed) | !last_host)) begin
                    host <= 1; last_host <= 1; h_take <= 1;
                    p_addr <= h_addr; p_we <= h_we; p_wdata <= h_wdata; p_sel <= h_sel;
                    state <= ISSUE;
                end else if (g_cyc & g_stb & guest_armed) begin
                    host <= 0; last_host <= 0; guest_armed <= 0;
                    base <= g_addr; beat <= 0; p_addr <= g_addr;
                    p_we <= g_we; p_wdata <= g_wdata; p_sel <= g_sel;
                    state <= ISSUE;
                end
                ISSUE: if (!p_busy) begin p_req <= 1; state <= WAIT; end
                WAIT: if (p_done) begin
                    if (host) begin
                        h_rdata <= p_rdata; h_done <= 1;
                        host_count <= host_count + 1'b1; state <= GAP;
                    end else begin
                        line[beat] <= p_rdata;
                        if(p_we | beat==3) begin beat<=0;state<=DELIVER;end
                        else begin
                            beat<=beat+1'b1;
                            p_addr<={base[21:2],base[1:0] + beat + 2'd1};
                            state<=ISSUE;
                        end
                    end
                end
                DELIVER: begin
                    // Baseline MEMC releases the CPU after beat three. Collect
                    // the line first, then deliver its four beats contiguously
                    // so a newly issued CPU access cannot corrupt cache fill.
                    g_rdata <= line[beat];
                    g_ack <= 1; guest_count <= guest_count + 1'b1;
                    if (p_we | beat == 3) state <= GAP;
                    else begin
                        beat <= beat + 1'b1;
                        state <= DELIVER;
                    end
                end
                GAP: state <= IDLE;
            endcase
        end
    end
endmodule
