// SPDX-License-Identifier: GPL-3.0-or-later
// Pocket APF interface declarations follow pinned PocketRiscV; implementation
// below is original PocketLotus integration. See source-manifest.json.
`timescale 1ns/1ps
`default_nettype none
module core_top (

//
// physical connections
//

///////////////////////////////////////////////////
// clock inputs 74.25mhz. not phase aligned, so treat these domains as asynchronous

input   wire            clk_74a, // mainclk1
input   wire            clk_74b, // mainclk1

///////////////////////////////////////////////////
// cartridge interface
// switches between 3.3v and 5v mechanically
// output enable for multibit translators controlled by pic32

// GBA AD[15:8]
inout   wire    [7:0]   cart_tran_bank2,
output  wire            cart_tran_bank2_dir,

// GBA AD[7:0]
inout   wire    [7:0]   cart_tran_bank3,
output  wire            cart_tran_bank3_dir,

// GBA A[23:16]
inout   wire    [7:0]   cart_tran_bank1,
output  wire            cart_tran_bank1_dir,

// GBA [7] PHI#
// GBA [6] WR#
// GBA [5] RD#
// GBA [4] CS1#/CS#
//     [3:0] unwired
inout   wire    [7:4]   cart_tran_bank0,
output  wire            cart_tran_bank0_dir,

// GBA CS2#/RES#
inout   wire            cart_tran_pin30,
output  wire            cart_tran_pin30_dir,
// when GBC cart is inserted, this signal when low or weak will pull GBC /RES low with a special circuit
// the goal is that when unconfigured, the FPGA weak pullups won't interfere.
// thus, if GBC cart is inserted, FPGA must drive this high in order to let the level translators
// and general IO drive this pin.
output  wire            cart_pin30_pwroff_reset,

// GBA IRQ/DRQ
inout   wire            cart_tran_pin31,
output  wire            cart_tran_pin31_dir,

// infrared
input   wire            port_ir_rx,
output  wire            port_ir_tx,
output  wire            port_ir_rx_disable,

// GBA link port
inout   wire            port_tran_si,
output  wire            port_tran_si_dir,
inout   wire            port_tran_so,
output  wire            port_tran_so_dir,
inout   wire            port_tran_sck,
output  wire            port_tran_sck_dir,
inout   wire            port_tran_sd,
output  wire            port_tran_sd_dir,

///////////////////////////////////////////////////
// cellular psram 0 and 1, two chips (64mbit x2 dual die per chip)

output  wire    [21:16] cram0_a,
inout   wire    [15:0]  cram0_dq,
input   wire            cram0_wait,
output  wire            cram0_clk,
output  wire            cram0_adv_n,
output  wire            cram0_cre,
output  wire            cram0_ce0_n,
output  wire            cram0_ce1_n,
output  wire            cram0_oe_n,
output  wire            cram0_we_n,
output  wire            cram0_ub_n,
output  wire            cram0_lb_n,

output  wire    [21:16] cram1_a,
inout   wire    [15:0]  cram1_dq,
input   wire            cram1_wait,
output  wire            cram1_clk,
output  wire            cram1_adv_n,
output  wire            cram1_cre,
output  wire            cram1_ce0_n,
output  wire            cram1_ce1_n,
output  wire            cram1_oe_n,
output  wire            cram1_we_n,
output  wire            cram1_ub_n,
output  wire            cram1_lb_n,

///////////////////////////////////////////////////
// sdram, 512mbit 16bit

output  wire    [12:0]  dram_a,
output  wire    [1:0]   dram_ba,
inout   wire    [15:0]  dram_dq,
output  wire    [1:0]   dram_dqm,
output  wire            dram_clk,
output  wire            dram_cke,
output  wire            dram_ras_n,
output  wire            dram_cas_n,
output  wire            dram_we_n,

///////////////////////////////////////////////////
// sram, 1mbit 16bit

output  wire    [16:0]  sram_a,
inout   wire    [15:0]  sram_dq,
output  wire            sram_oe_n,
output  wire            sram_we_n,
output  wire            sram_ub_n,
output  wire            sram_lb_n,

///////////////////////////////////////////////////
// vblank driven by dock for sync in a certain mode

input   wire            vblank,

///////////////////////////////////////////////////
// i/o to 6515D breakout usb uart

output  wire            dbg_tx,
input   wire            dbg_rx,

///////////////////////////////////////////////////
// i/o pads near jtag connector user can solder to

output  wire            user1,
input   wire            user2,

///////////////////////////////////////////////////
// RFU internal i2c bus

inout   wire            aux_sda,
output  wire            aux_scl,

///////////////////////////////////////////////////
// RFU, do not use
output  wire            vpll_feed,


//
// logical connections
//

///////////////////////////////////////////////////
// video, audio output to scaler
output  wire    [23:0]  video_rgb,
output  wire            video_rgb_clock,
output  wire            video_rgb_clock_90,
output  wire            video_de,
output  wire            video_skip,
output  wire            video_vs,
output  wire            video_hs,

output  wire            audio_mclk,
input   wire            audio_adc,
output  wire            audio_dac,
output  wire            audio_lrck,

///////////////////////////////////////////////////
// bridge bus connection
// synchronous to clk_74a
output  wire            bridge_endian_little,
input   wire    [31:0]  bridge_addr,
input   wire            bridge_rd,
output  reg     [31:0]  bridge_rd_data,
input   wire            bridge_wr,
input   wire    [31:0]  bridge_wr_data,

///////////////////////////////////////////////////
// controller data
//
// key bitmap:
//   [0]    dpad_up
//   [1]    dpad_down
//   [2]    dpad_left
//   [3]    dpad_right
//   [4]    face_a
//   [5]    face_b
//   [6]    face_x
//   [7]    face_y
//   [8]    trig_l1
//   [9]    trig_r1
//   [10]   trig_l2
//   [11]   trig_r2
//   [12]   trig_l3
//   [13]   trig_r3
//   [14]   face_select
//   [15]   face_start
//   [31:28] type
// joy values - unsigned
//   [ 7: 0] lstick_x
//   [15: 8] lstick_y
//   [23:16] rstick_x
//   [31:24] rstick_y
// trigger values - unsigned
//   [ 7: 0] ltrig
//   [15: 8] rtrig
//
input   wire    [31:0]  cont1_key,
input   wire    [31:0]  cont2_key,
input   wire    [31:0]  cont3_key,
input   wire    [31:0]  cont4_key,
input   wire    [31:0]  cont1_joy,
input   wire    [31:0]  cont2_joy,
input   wire    [31:0]  cont3_joy,
input   wire    [31:0]  cont4_joy,
input   wire    [15:0]  cont1_trig,
input   wire    [15:0]  cont2_trig,
input   wire    [15:0]  cont3_trig,
input   wire    [15:0]  cont4_trig

);

// Keep unused interfaces electrically inactive. No cartridge/link traffic is
// needed for this standalone target. All active RAM is on physical CRAM0.
assign port_ir_tx=0; assign port_ir_rx_disable=1;
assign cart_tran_bank3=8'hzz;assign cart_tran_bank3_dir=0;
assign cart_tran_bank2=8'hzz;assign cart_tran_bank2_dir=0;
assign cart_tran_bank1=8'hzz;assign cart_tran_bank1_dir=0;
assign cart_tran_bank0=4'hf;assign cart_tran_bank0_dir=1;
assign cart_tran_pin30=1'bz;assign cart_tran_pin30_dir=0;
assign cart_pin30_pwroff_reset=0;assign cart_tran_pin31=1'bz;assign cart_tran_pin31_dir=0;
assign port_tran_si=1'bz;assign port_tran_si_dir=0;
assign port_tran_so=1'bz;assign port_tran_so_dir=0;
assign port_tran_sck=1'bz;assign port_tran_sck_dir=0;
assign port_tran_sd=1'bz;assign port_tran_sd_dir=0;
assign cram1_a=0;assign cram1_dq=16'hzzzz;assign cram1_clk=0;
assign cram1_adv_n=1;assign cram1_cre=0;assign cram1_ce0_n=1;assign cram1_ce1_n=1;
assign cram1_oe_n=1;assign cram1_we_n=1;assign cram1_ub_n=1;assign cram1_lb_n=1;
assign dram_a=0;assign dram_ba=0;assign dram_dq=16'hzzzz;assign dram_dqm=3;
assign dram_clk=0;assign dram_cke=0;assign dram_ras_n=1;assign dram_cas_n=1;assign dram_we_n=1;
assign sram_a=0;assign sram_dq=16'hzzzz;assign sram_oe_n=1;assign sram_we_n=1;
assign sram_ub_n=1;assign sram_lb_n=1;
assign aux_sda=1'bz;assign aux_scl=1'bz;assign vpll_feed=0;
assign bridge_endian_little=1;

wire sys_clk,pix_clk,pix_clk90,aud_clk,pll_locked;
// Give both physical PLLs a real power-up reset pulse (16 reference clocks).
reg [4:0] pll_start=0;
always @(posedge clk_74a) if(!pll_start[4]) pll_start<=pll_start+1'b1;
pocket_pll pll(.refclk(clk_74a),.reset(!pll_start[4]),.sys_clk(sys_clk),.pix_clk(pix_clk),
    .pix_clk_90(pix_clk90),.audio_clk(aud_clk),.locked(pll_locked));
wire fabric_reset = !pll_locked;
wire bridge_reset,sys_reset;
reset_sync bridge_reset_sync(clk_74a,fabric_reset,bridge_reset);
reset_sync sys_reset_sync(sys_clk,fabric_reset,sys_reset);
wire apf_reset_n,allcomplete,load_read,load_write;
wire [15:0] load_id,write_id;
wire [31:0] cmd_rdata;
wire ready,cpu_reset,pix_reset,drained,host_fault;
wire debug_valid,debug_ack;
wire [31:0] debug_data;
wire [191:0] debug_snapshot;
wire [63:0] probe_snapshot;
// Reuse the existing coherent bridge-domain status mailbox for logging.
pocket_debug debug_events(.clk(clk_74a),.reset(bridge_reset),
    .running(apf_reset_n & ready),.snapshot({probe_snapshot,debug_snapshot}),
    .event_valid(debug_valid),.event_data(debug_data),.event_ack(debug_ack));
core_bridge_cmd commands(
    .clk(clk_74a),.reset_n(apf_reset_n),.bridge_endian_little(bridge_endian_little),
    .bridge_addr(bridge_addr),.bridge_rd(bridge_rd),.bridge_rd_data(cmd_rdata),
    .bridge_wr(bridge_wr),.bridge_wr_data(bridge_wr_data),
    .status_boot_done(pll_locked),.status_setup_done(ready),
    .status_running(apf_reset_n & ready),
    .debug_event_valid(debug_valid),.debug_event_data(debug_data),.debug_event_ack(debug_ack),
    .dataslot_requestread(load_read),.dataslot_requestread_id(load_id),
    .dataslot_requestread_ack(load_read),.dataslot_requestread_ok(load_id==0),
    .dataslot_requestwrite(load_write),.dataslot_requestwrite_id(write_id),
    // APF 0082 is a host WRITE into core RAM, used for asset loading.
    .dataslot_requestwrite_size(),.dataslot_requestwrite_ack(load_write),.dataslot_requestwrite_ok(write_id==0),
    .dataslot_update(),.dataslot_update_id(),.dataslot_update_size(),.dataslot_allcomplete(allcomplete),
    .rtc_epoch_seconds(),.rtc_date_bcd(),.rtc_time_bcd(),.rtc_valid(),
    .savestate_supported(1'b0),.savestate_addr(32'b0),.savestate_size(32'b0),.savestate_maxloadsize(32'b0),
    .osnotify_inmenu(),.savestate_start(),.savestate_start_ack(1'b0),.savestate_start_busy(1'b0),
    .savestate_start_ok(1'b0),.savestate_start_err(1'b0),.savestate_load(),
    .savestate_load_ack(1'b0),.savestate_load_busy(1'b0),.savestate_load_ok(1'b0),.savestate_load_err(1'b0),
    .target_dataslot_read(1'b0),.target_dataslot_write(1'b0),.target_dataslot_getfile(1'b0),
    .target_dataslot_openfile(1'b0),.target_dataslot_ack(),.target_dataslot_done(),.target_dataslot_err(),
    .target_dataslot_id(16'b0),.target_dataslot_slotoffset(32'b0),.target_dataslot_bridgeaddr(32'b0),
    .target_dataslot_length(32'b0),.target_buffer_param_struct(32'b0),.target_buffer_resp_struct(32'b0),
    .datatable_addr(10'b0),.datatable_wren(1'b0),.datatable_data(32'b0),.datatable_q());
pocket_reset reset_gate(.bridge_clk(clk_74a),.sys_clk(sys_clk),.pix_clk(pix_clk),
    .pll_locked(pll_locked),.apf_reset_n(apf_reset_n),.loading(load_write),
    .allcomplete(allcomplete),.drained(drained),.fault(host_fault),
    .ready(ready),.cpu_reset(cpu_reset),.pix_reset(pix_reset));

wire [21:0] ga,ha,pa;
wire gc,gs,gwe,gack,hv,hwe,ht,hd,preq,pwe,pbusy,pdone,mem_idle;
wire [3:0] gsel,hsel,psel;
wire [31:0] gwd,grd,hwd,hrd,pwd,prd,host_rdata,status_rdata;
wire [31:0] diag_status,cpu_count,video_count,sound_count,last_cpu_addr,peripheral_count;
wire [31:0] host_count,guest_count;
wire [3:0] arb_state;
wire [2:0] ram_state;
// Bits 15..0: locked, CPU reset, pixel reset, ready, MEMC cyc/stb/we/ack,
// RAM busy, arbiter armed/state[2:0], RAM state[2:0]. Two-stage independent
// flag capture is only interpreted as a state when it remains stable.
wire [15:0] probe_flags={pll_locked,cpu_reset,pix_reset,ready,gc,gs,gwe,gack,
                       pbusy,arb_state,ram_state};
pocket_probe probes(.bridge_clk(clk_74a),.sys_clk(sys_clk),.pix_clk(pix_clk),
    .reset(bridge_reset),.activity({peripheral_count[7],sound_count[3],video_count[7],cpu_count[7]}),
    .flags(probe_flags),.snapshot(probe_snapshot));
wire [191:0] status_bus = {last_cpu_addr,peripheral_count,sound_count,video_count,cpu_count,diag_status};
pocket_host host(.bridge_clk(clk_74a),.sys_clk(sys_clk),.reset(fabric_reset),
    .bridge_addr(bridge_addr),.bridge_wr(bridge_wr),.bridge_rd(bridge_rd),
    .bridge_wdata(bridge_wr_data),.bridge_rdata(host_rdata),.status_data(status_rdata),.status_snapshot(debug_snapshot),
    .h_valid(hv),.h_we(hwe),.h_addr(ha),.h_wdata(hwd),.h_sel(hsel),
    .h_take(ht),.h_done(hd),.h_rdata(hrd),.mem_idle(mem_idle),
    .drained(drained),.overflow(host_fault),.status_bus(status_bus));
always @(*) begin
    case(bridge_addr[31:24])
        8'hf8:bridge_rd_data=cmd_rdata;
        8'hf0:bridge_rd_data=status_rdata;
        default:bridge_rd_data=host_rdata;
    endcase
end
memory_arbiter arb(.clk(sys_clk),.reset(sys_reset),.g_cyc(gc & !cpu_reset),.g_stb(gs),
    .g_we(gwe),.g_addr(ga),.g_wdata(gwd),.g_sel(gsel),.g_ack(gack),.g_rdata(grd),
    .h_valid(hv),.h_we(hwe),.h_addr(ha),.h_wdata(hwd),.h_sel(hsel),
    .h_take(ht),.h_done(hd),.h_rdata(hrd),.p_req(preq),.p_we(pwe),.p_addr(pa),
    .p_wdata(pwd),.p_sel(psel),.p_busy(pbusy),.p_done(pdone),.p_rdata(prd),
    .idle(mem_idle),.host_count(host_count),.guest_count(guest_count),.debug_state(arb_state));
psram_word memory(.clk(sys_clk),.reset(sys_reset),.req(preq),.we(pwe),.addr(pa),
    .wdata(pwd),.sel(psel),.busy(pbusy),.done(pdone),.rdata(prd),.debug_state(ram_state),
    .cram_a(cram0_a),.cram_dq(cram0_dq),.cram_wait(cram0_wait),.cram_clk(cram0_clk),
    .cram_adv_n(cram0_adv_n),.cram_cre(cram0_cre),.cram_ce0_n(cram0_ce0_n),
    .cram_ce1_n(cram0_ce1_n),.cram_oe_n(cram0_oe_n),.cram_we_n(cram0_we_n),
    .cram_ub_n(cram0_ub_n),.cram_lb_n(cram0_lb_n));

// Controllers are related to 74a, not sys_clk. Sample stable values through a
// request/ack mailbox, avoiding torn multi-bit gamepad state.
reg key_req=0,key_ack=0;
reg [63:0] key_payload=0,keys=0;
(* async_reg="true" *) reg [1:0] key_req_sync=0,key_ack_sync=0;
always @(posedge clk_74a) begin
    if(bridge_reset) begin key_req_sync<=0;key_ack<=0;key_payload<=0;end
    else begin
        key_req_sync<={key_req_sync[0],key_req};
        if(key_req_sync[1]!=key_ack) begin key_payload<={cont2_key,cont1_key};key_ack<=key_req_sync[1];end
    end
end
always @(posedge sys_clk) begin
    if(sys_reset) begin key_req<=0;key_ack_sync<=0;keys<=0;end
    else begin
        key_ack_sync<={key_ack_sync[0],key_ack};
        if(key_ack_sync[1]==key_req) begin keys<=key_payload;key_req<=~key_req;end
    end
end

reg [2:0] auddiv=0;
always @(posedge pix_clk) if(pix_reset) auddiv<=0;else auddiv<=auddiv+1'b1;
wire hs,vs,de;
wire [11:0] rgb;
wire [15:0] audio_l,audio_r;
wire [1:0] pixel_select;
pocket_chipset chipset(.clk(sys_clk),.pix_clk(pix_clk),.aud_ce(auddiv==0),.reset(cpu_reset),.video_reset(pix_reset),
    .mem_addr(ga),.mem_cyc(gc),.mem_stb(gs),.mem_we(gwe),.mem_sel(gsel),
    .mem_wdata(gwd),.mem_rdata(grd),.mem_ack(gack),.keys(keys[31:0]),.keys2(keys[63:32]),
    .hs(hs),.vs(vs),.de(de),.rgb(rgb),.audio_l(audio_l),.audio_r(audio_r),
    .diag_status(diag_status),.cpu_count(cpu_count),.video_count(video_count),
    .sound_count(sound_count),.last_cpu_addr(last_cpu_addr),.peripheral_count(peripheral_count),
    .pixel_select(pixel_select),.kbd_data(8'b0),.kbd_strobe(1'b0),.kbd_out(),.kbd_out_strobe());
// The original VIDC RGB/palette stream drives APF directly. Metadata specifies
// 320x256; the diagnostic programs VIDC border to those same active dimensions.
// APF consumes event pulses, not the guest's analog sync widths. Its blank
// RGB words carry scaler commands, so they must be zero outside active pixels.
pocket_video video(.clk(pix_clk),.reset(pix_reset),.hsync_n(hs),.vsync_n(vs),
    .active(de),.rgb(rgb),.pixels(video_rgb),.de(video_de),.hs(video_hs),.vs(video_vs));
assign video_rgb_clock=pix_clk;assign video_rgb_clock_90=pix_clk90;
assign video_skip=0;
pocket_audio audio(.pix_clk(pix_clk),.audio_clk(aud_clk),.reset(cpu_reset | pix_reset),
    .left(audio_l),.right(audio_r),.mclk(audio_mclk),.dac(audio_dac),.lrck(audio_lrck));
// Observable CPU heartbeat plus exact failure flag. Both are derived from real
// transactions, so no permanently reset/disconnected chipset can substitute.
assign user1=diag_status[31:16]==16'hbad0;
assign dbg_tx=cpu_count[10];
endmodule
`default_nettype wire

