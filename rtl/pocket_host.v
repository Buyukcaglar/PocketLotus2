// SPDX-License-Identifier: GPL-3.0-or-later
// APF bus has no backpressure: its specified minimum interval is 88 bridge
// clocks. Requests queue across domains. Overrun is sticky and prevents guest
// reset release. Loading/readback is qualified with the guest held in reset;
// running status uses a separate coherent snapshot rather than slow RAM reads.
`timescale 1ns/1ps
module pocket_host(
    input bridge_clk, input sys_clk, input reset,
    input [31:0] bridge_addr, input bridge_wr, input bridge_rd,
    input [31:0] bridge_wdata, output reg [31:0] bridge_rdata=0,
    output h_valid, output h_we, output [21:0] h_addr,
    output [31:0] h_wdata, output [3:0] h_sel,
    input h_take, input h_done, input [31:0] h_rdata,
    input mem_idle, output drained, output reg overflow=0,
    output [31:0] status_data, output [191:0] status_snapshot,
    input [191:0] status_bus
);
    wire bridge_reset,sys_reset;
    reset_sync bridge_reset_sync(bridge_clk,reset,bridge_reset);
    reset_sync sys_reset_sync(sys_clk,reset,sys_reset);
    wire memory_select = bridge_addr[31:23] == 0;
    wire reqfull, reqempty;
    wire [58:0] request;
    wire push = memory_select & (bridge_wr | bridge_rd);
    async_fifo #(.WIDTH(59)) requests(
        .wclk(bridge_clk),.rclk(sys_clk),.reset(reset),
        .push(push),.wdata({bridge_wr,bridge_addr[23:2],bridge_wdata,4'hf}),
        .full(reqfull),.pop(h_take),.rdata(request),.empty(reqempty));
    assign {h_we,h_addr,h_wdata,h_sel} = request;
    assign h_valid = !reqempty;
    reg read_inflight=0;
    always @(posedge sys_clk) begin
        if(sys_reset) read_inflight<=0;
        else begin
            if(h_take) read_inflight<=!h_we;
            if(h_done) read_inflight<=0;
        end
    end
    wire replyfull,replyempty;
    wire [31:0] reply;
    async_fifo #(.WIDTH(32)) replies(
        .wclk(sys_clk),.rclk(bridge_clk),.reset(reset),
        .push(h_done & read_inflight),.wdata(h_rdata),.full(replyfull),
        .pop(!replyempty),.rdata(reply),.empty(replyempty));
    wire drained_sys = reqempty & mem_idle;
    (* async_reg="true" *) reg [1:0] drain_sync=0;
    assign drained = drain_sync[1];
    reg reply_overflow=0;
    (* async_reg="true" *) reg [1:0] reply_fault_sync=0;
    always @(posedge sys_clk) begin
        if(sys_reset) reply_overflow<=0;
        else if(h_done & read_inflight & replyfull) reply_overflow<=1;
    end
    // Coherent status mailbox. Request and acknowledgement toggles are
    // synchronized; status_payload stays unchanged until the next request.
    reg request_toggle=0, ack_toggle=0;
    reg [191:0] status_payload=0, snapshot=0;
    reg [5:0] refresh=0;
    (* async_reg="true" *) reg [1:0] req_sync=0,ack_sync=0;
    always @(posedge sys_clk) begin
        if(sys_reset) begin req_sync<=0;ack_toggle<=0;status_payload<=0;end
        else begin
            req_sync<={req_sync[0],request_toggle};
            if(req_sync[1]!=ack_toggle) begin
                status_payload<=status_bus;
                ack_toggle<=req_sync[1];
            end
        end
    end
    always @(posedge bridge_clk) begin
        if(bridge_reset) begin
            overflow<=0;bridge_rdata<=0;drain_sync<=0;reply_fault_sync<=0;
            request_toggle<=0;ack_sync<=0;refresh<=0;snapshot<=0;
        end else begin
            drain_sync<={drain_sync[0],drained_sys};
            reply_fault_sync<={reply_fault_sync[0],reply_overflow};
            if((push & reqfull) | reply_fault_sync[1]) overflow<=1;
            if(!replyempty) bridge_rdata<=reply;
            ack_sync<={ack_sync[0],ack_toggle};
            refresh<=refresh+1'b1;
            if(refresh==0 && ack_sync[1]==request_toggle) begin
                snapshot<=status_payload;
                request_toggle<=~request_toggle;
            end
        end
    end
    // Register reads always return an already synchronized snapshot. External
    // RAM returns the prior prefetched word per io_bridge_peripheral protocol.
    wire [31:0] status_word = bridge_addr[4:2] == 0 ? snapshot[31:0] :
                               bridge_addr[4:2] == 1 ? snapshot[63:32] :
                               bridge_addr[4:2] == 2 ? snapshot[95:64] :
                               bridge_addr[4:2] == 3 ? snapshot[127:96] :
                               bridge_addr[4:2] == 4 ? snapshot[159:128] : snapshot[191:160];
    // Expose the snapshot on a separate port mux in core_top (see status_data).
    assign status_data = status_word;
    assign status_snapshot = snapshot;
endmodule
