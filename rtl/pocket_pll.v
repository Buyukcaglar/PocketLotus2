// SPDX-License-Identifier: GPL-3.0-or-later
// Requested clocks: baseline IOC/CPU 42MHz, MODE9 diagnostic pixel 8MHz,
// 90-degree scaler phase, and 12.288MHz audio MCLK. Actual achieved frequencies
// must be read from Quartus PLL/fitter reports; these requests are not results.
`timescale 1ns/1ps
module pocket_pll(input refclk, input reset,
    output sys_clk, output pix_clk, output pix_clk_90,
    output audio_clk, output locked);
`ifdef SIMULATION
    reg sim_sys=0,sim_pix=0,sim_pix90=0,sim_audio=0,sim_lock=0;
    always #11.904762 sim_sys=~sim_sys;
    always #62.5 sim_pix=~sim_pix;
    initial begin #31.25; forever #62.5 sim_pix90=~sim_pix90;end
    always #40.690104 sim_audio=~sim_audio;
    initial begin #500;sim_lock=1;end
    assign sys_clk=sim_sys;assign pix_clk=sim_pix;assign pix_clk_90=sim_pix90;
    assign audio_clk=sim_audio;assign locked=sim_lock & !reset;
`else
    wire machine_locked,audio_locked;
    // Audio has an incompatible VCO divisor family; give it its own PLL.
    // 42/8 MHz can share 840 MHz (C=20/105), unlike 12.288 MHz.
    altera_pll #(.fractional_vco_multiplier("true"),
        .reference_clock_frequency("74.25 MHz"),.operation_mode("normal"),
        .number_of_clocks(3),.output_clock_frequency0("42.0 MHz"),
        .phase_shift0("0 ps"),.duty_cycle0(50),
        .output_clock_frequency1("8.0 MHz"),.phase_shift1("0 ps"),.duty_cycle1(50),
        .output_clock_frequency2("8.0 MHz"),.phase_shift2("31250 ps"),.duty_cycle2(50),
        .pll_type("General"),.pll_subtype("General")) clocks(
        .refclk(refclk),.rst(reset),.outclk({pix_clk_90,pix_clk,sys_clk}),
        .locked(machine_locked),.fbclk(1'b0),.fboutclk());
    altera_pll #(.fractional_vco_multiplier("true"),
        .reference_clock_frequency("74.25 MHz"),.operation_mode("normal"),
        .number_of_clocks(1),.output_clock_frequency0("12.288 MHz"),
        .phase_shift0("0 ps"),.duty_cycle0(50),
        .pll_type("General"),.pll_subtype("General")) audio_clocks(
        .refclk(refclk),.rst(reset),.outclk(audio_clk),
        .locked(audio_locked),.fbclk(1'b0),.fboutclk());
    assign locked = machine_locked & audio_locked;
`endif
endmodule
