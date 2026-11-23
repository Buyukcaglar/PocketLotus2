# SPDX-License-Identifier: GPL-3.0-or-later
# Pocket APF clocks are asynchronous to each other and to the generated clocks.
create_clock -name clk_74a -period 13.468 [get_ports clk_74a]
create_clock -name clk_74b -period 13.468 [get_ports clk_74b]
create_clock -name bridge_spiclk -period 13.468 [get_ports bridge_spiclk]
derive_pll_clocks
derive_clock_uncertainty

# Explicit clocks selected by generated-clock source pin. No broad async clock
# group hides bundled-data paths: only first-stage synchronizers are false paths.
set_false_path -to [get_registers {*|req_sync[0] *|ack_sync[0] *|key_req_sync[0] *|key_ack_sync[0] *|drain_sync[0] *|reply_fault_sync[0]}]
# Only first-stage single-bit captures are asynchronous. The following stages
# keep ordinary setup/hold analysis. Synchronizer reset pins may release at any
# phase; their local shift chain, and all downstream reset sinks, remain timed.
set_false_path -to [get_registers {*|hs_sync[0] *|fly_sync[0]}]
# Independent liveness bits and stable-stall flags: only first captures waived.
set_false_path -to [get_registers {*|probes|tap_meta[*] *|probes|flag_meta[*]}]
set_false_path -to [get_pins -compatibility_mode {*|probes|sys_ticks[*]|clrn *|probes|pix_ticks[*]|clrn}]
set_false_path -to [get_pins -compatibility_mode {*|stages[*]|clrn *|reset_gate|cpu_sync[*]|clrn *|reset_gate|pix_sync[*]|clrn *|VIDEO_FIFO|wr_reset[*]|clrn *|VIDEO_FIFO|rd_reset[*]|clrn}]
# Gray pointers must arrive within one period of the faster clock. These paths
# are NOT false-pathed. The first capture uses the bounded physical delay below.
set_max_delay 13.468 -from [get_registers {*|wg[*] *|rg[*]}] -to [get_registers {*|wg1[*] *|rg1[*]}]
set_min_delay -100.0 -from [get_registers {*|wg[*] *|rg[*]}] -to [get_registers {*|wg1[*] *|rg1[*]}]
set_max_skew 13.468 -from [get_registers {*|wg[*] *|rg[*]}] -to [get_registers {*|wg1[*] *|rg1[*]}]
# Bundled-data mailboxes hold payload until the synchronized acknowledgement.
set_max_delay 13.468 -from [get_registers {*|status_payload[*]}] -to [get_registers {*|snapshot[*]}]
set_max_delay 13.468 -from [get_registers {*|key_payload[*]}] -to [get_registers {*|keys[*]}]
set_max_delay 81.38 -from [get_registers {*|audio|payload[*]}] -to [get_registers {*|audio|samples[*]}]
# Quartus Lite uses clock-relative set_max_delay, not -datapath_only. A loose
# minimum removes meaningless cross-domain hold-edge alignment; these are
# stable mailboxes and Gray captures. It does not waive their maximum delay.
set_min_delay -100.0 -from [get_registers {*|status_payload[*]}] -to [get_registers {*|snapshot[*]}]
set_min_delay -100.0 -from [get_registers {*|key_payload[*]}] -to [get_registers {*|keys[*]}]
set_min_delay -100.0 -from [get_registers {*|audio|payload[*]}] -to [get_registers {*|audio|samples[*]}]
# FIFO payload is held before a two-stage Gray pointer exposes the word. Bound
# every implemented register-array payload, including read mux logic. A FIFO
# mapped into true dual-clock RAM uses the primitive's separate port timing.
foreach instance {requests replies vidc_writes VIDEO_FIFO} {
    set payload [get_registers -nowarn *|${instance}|data*]
    if {[get_collection_size $payload] > 0} {
        set_max_delay 13.468 -from $payload -to [get_registers *]
        set_min_delay -100.0 -from $payload -to [get_registers *]
    }
}

# Async PSRAM is deliberately held for multiple system clocks. Constrain the
# external bus relative to the 42MHz source. Actual board input/output delay
# margins still require fitting plus hardware qualification.
set sys_clock {}
foreach_in_collection clock [get_clocks *] {
    set period [get_clock_info -period $clock]
    if {$period > 23.0 && $period < 25.0} {
        if {$sys_clock ne {}} {error "More than one 42MHz clock; review PLL constraints"}
        set sys_clock $clock
    }
}
if {$sys_clock eq {}} {error "42MHz PLL output not derived; do not run unconstrained"}
# 70ns asynchronous read access is sampled after six system clocks. This is
# an engineering budget, awaiting exact fitted pin/device timing validation.
set_input_delay -max 70.0 -clock $sys_clock [get_ports {cram0_dq[*]}]
set_input_delay -min 0.0 -clock $sys_clock [get_ports {cram0_dq[*]}]
set_multicycle_path -setup 6 -from [get_ports {cram0_dq[*]}] -to [get_registers {*|memory|rdata[*]}]
set_multicycle_path -hold 5 -from [get_ports {cram0_dq[*]}] -to [get_registers {*|memory|rdata[*]}]
set_output_delay -max 5.0 -clock $sys_clock [get_ports {cram0_a[*] cram0_dq[*] cram0_adv_n cram0_ce0_n cram0_ce1_n cram0_oe_n cram0_we_n cram0_ub_n cram0_lb_n}]
set_output_delay -min -2.0 -clock $sys_clock [get_ports {cram0_a[*] cram0_dq[*] cram0_adv_n cram0_ce0_n cram0_ce1_n cram0_oe_n cram0_we_n cram0_ub_n cram0_lb_n}]

# APF inherited SPI and controller CDC is retained from the pinned framework.
# Its external source timing and scaler DDR timing must be inspected in the
# first real TimeQuest run. Do not declare timing closed from these constraints.
