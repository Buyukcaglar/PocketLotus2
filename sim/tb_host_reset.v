// SPDX-License-Identifier: GPL-3.0-or-later
`timescale 1ns/1ps
module tb_host_reset;
    reg bclk=0,sclk=0,pclk=0,reset=1;
    always #6.734007 bclk=~bclk;
    always #11.904762 sclk=~sclk;
    always #62.5 pclk=~pclk;
    reg [31:0] ba=0,bd=0;
    reg bw=0,br=0,apf=0,loading=0,complete=0;
    wire hv,hwe,ht,hd,idle,drained,fault,ready,cr,pr;
    wire [21:0] ha,pa;
    wire [31:0] hwd,hrd,hostq,statusq,pwd,pdata;
    wire [3:0] hsel,psel;
    wire preq,pwe,pbusy,pdone;
    wire [21:16] a;
    wire [15:0] dq;
    wire adv,ce0,ce1,oe,we,ub,lb,wait_pin;
    reg [31:0] seq_count=0;
    wire [191:0] snapshot_source={seq_count,seq_count,seq_count,seq_count,seq_count,seq_count};
    always @(posedge sclk) seq_count<=seq_count+1'b1;
    pocket_host host(.bridge_clk(bclk),.sys_clk(sclk),.reset(reset),
        .bridge_addr(ba),.bridge_wr(bw),.bridge_rd(br),.bridge_wdata(bd),
        .bridge_rdata(hostq),.status_data(statusq),.h_valid(hv),.h_we(hwe),
        .h_addr(ha),.h_wdata(hwd),.h_sel(hsel),.h_take(ht),.h_done(hd),
        .h_rdata(hrd),.mem_idle(idle),.drained(drained),.overflow(fault),.status_bus(snapshot_source));
    pocket_reset gate(.bridge_clk(bclk),.sys_clk(sclk),.pix_clk(pclk),.pll_locked(!reset),
        .apf_reset_n(apf),.loading(loading),.allcomplete(complete),.drained(drained),
        .fault(fault),.ready(ready),.cpu_reset(cr),.pix_reset(pr));
    memory_arbiter arb(.clk(sclk),.reset(reset),.g_cyc(1'b0),.g_stb(1'b0),
        .g_we(1'b0),.g_addr(22'b0),.g_wdata(32'b0),.g_sel(4'b0),.g_ack(),.g_rdata(),
        .h_valid(hv),.h_we(hwe),.h_addr(ha),.h_wdata(hwd),.h_sel(hsel),
        .h_take(ht),.h_done(hd),.h_rdata(hrd),.p_req(preq),.p_we(pwe),.p_addr(pa),
        .p_wdata(pwd),.p_sel(psel),.p_busy(pbusy),.p_done(pdone),.p_rdata(pdata),
        .idle(idle),.host_count(),.guest_count());
    psram_word ctl(.clk(sclk),.reset(reset),.req(preq),.we(pwe),.addr(pa),
        .wdata(pwd),.sel(psel),.busy(pbusy),.done(pdone),.rdata(pdata),
        .cram_a(a),.cram_dq(dq),.cram_wait(wait_pin),.cram_clk(),.cram_adv_n(adv),
        .cram_cre(),.cram_ce0_n(ce0),.cram_ce1_n(ce1),.cram_oe_n(oe),
        .cram_we_n(we),.cram_ub_n(ub),.cram_lb_n(lb));
    psram_model ram(a,dq,adv,ce0,ce1,oe,we,ub,lb,wait_pin);
    task bridge_word(input rd,input [31:0] addr,input [31:0] value);
        begin
            @(negedge bclk);ba=addr;bd=value;br=rd;bw=!rd;
            @(negedge bclk);br=0;bw=0;
            repeat(87) @(negedge bclk);
        end
    endtask
    integer n;
    initial begin
        repeat(10) @(negedge bclk);reset=0;
        apf=1;
        repeat(20) @(negedge bclk);
        if(!cr||!pr)$fatal(1,"Guest released before slot completion");
        loading=1;repeat(2)@(negedge bclk);loading=0;
        for(n=0;n<128;n=n+1) bridge_word(0,32'h00400000+n*4,32'hac000000+n);
        // APF completion is asserted immediately after the last request pulse.
        @(negedge bclk);ba=32'h00400400;bd=32'habcdef98;bw=1;
        @(negedge bclk);bw=0;complete=1;
        repeat(5)@(negedge bclk);
        if(!cr||!pr)$fatal(1,"Guest released with queued writes");
        wait(ready);wait(!cr && !pr);
        if(fault)$fatal(1,"Overrun at the APF 88-clock minimum interval");
        if(ram.memory[22'h200200]!==16'hef98 || ram.memory[22'h200201]!==16'habcd)
            $fatal(1,"Reset released before final PSRAM write committed");
        for(n=0;n<128;n=n+1) begin
            bridge_word(1,32'h00400000+n*4,0);
            if(hostq!==32'hac000000+n)$fatal(1,"Buffered bridge read n=%0d got=%x",n,hostq);
        end
        repeat(100)@(negedge bclk);
        if(host.snapshot[31:0] != host.snapshot[191:160])$fatal(1,"Torn status CDC");
        // Host reset assertion reaches the guest promptly in both domains.
        apf=0;#1;if(!cr||!pr)$fatal(1,"Reset assertion latency");
        apf=1;wait(!cr&&!pr);
        // Deliberately violate bridge rate to prove sticky fault/reset behavior.
        for(n=0;n<64;n=n+1) begin
            @(negedge bclk);ba=n*4;bw=1;bd=n;
        end
        @(negedge bclk);bw=0;
        repeat(20)@(negedge bclk);
        if(!fault||!cr||!pr)$fatal(1,"FIFO overflow did not hold guest reset");
        $display("PASS host CDC: 129 writes drained, 128 ordered reads at 88 clocks, coherent status, reset gating, sticky overrun");
        $finish;
    end
    initial begin #1000000;$fatal(1,"Host/reset timeout");end
endmodule
