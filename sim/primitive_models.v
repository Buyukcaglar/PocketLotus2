// SPDX-License-Identifier: GPL-3.0-or-later
// Functional memory model for pinned Amber RAM wrappers. This models only the
// configuration used here and is NOT vendor timing/IP validation.
`timescale 1ns/1ps
module altsyncram #(
    parameter width_a=32, widthad_a=8, numwords_a=256, width_byteena_a=1,
    parameter width_b=32, widthad_b=8, numwords_b=256, width_byteena_b=1,
    parameter byte_size=8, clock_enable_input_a="BYPASS", clock_enable_output_a="BYPASS",
    parameter clock_enable_input_b="BYPASS", clock_enable_output_b="BYPASS",
    parameter intended_device_family="Cyclone V", lpm_hint="", lpm_type="altsyncram",
    parameter operation_mode="SINGLE_PORT", outdata_aclr_a="NONE", outdata_reg_a="CLOCK0",
    parameter outdata_aclr_b="NONE", outdata_reg_b="CLOCK1", power_up_uninitialized="FALSE",
    parameter read_during_write_mode_port_a="NEW_DATA_NO_NBE_READ",
    parameter read_during_write_mode_port_b="NEW_DATA_NO_NBE_READ",
    parameter address_reg_b="CLOCK1", indata_reg_b="CLOCK1", init_file="UNUSED",
    parameter wrcontrol_wraddress_reg_b="CLOCK1"
)(
    input clock0, clock1, aclr0, aclr1, clocken0, clocken1, clocken2, clocken3,
    input addressstall_a, addressstall_b, rden_a, rden_b, wren_a, wren_b,
    input [widthad_a-1:0] address_a, input [widthad_b-1:0] address_b,
    input [width_a-1:0] data_a, input [width_b-1:0] data_b,
    input [width_byteena_a-1:0] byteena_a, input [width_byteena_b-1:0] byteena_b,
    output reg [width_a-1:0] q_a, output reg [width_b-1:0] q_b,
    output [2:0] eccstatus
);
    reg [width_a-1:0] mem[0:numwords_a-1];
    integer i, j;
    initial for (i=0;i<numwords_a;i=i+1) mem[i]=0;
    always @(posedge clock0) begin
        if (wren_a) begin
            for (j=0;j<width_byteena_a;j=j+1)
                if (byteena_a[j]) mem[address_a][j*(width_a/width_byteena_a) +: width_a/width_byteena_a] =
                                 data_a[j*(width_a/width_byteena_a) +: width_a/width_byteena_a];
        end
        q_a <= mem[address_a];
    end
    always @(posedge clock1) if (operation_mode == "BIDIR_DUAL_PORT") begin
        if (wren_b) mem[address_b] = data_b;
        q_b <= mem[address_b];
    end
    assign eccstatus = 0;
endmodule

// Upstream's translate_off hook references a VHDL file-writing CPU tracer.
// Icarus is Verilog-only: keep the hook as an optional trace here. This has no
// synthesized instance and supplies no CPU functional behavior.
module cpu_export(input clk, rst, new_export,
    input [31:0] R0,R1,R2,R3,R4,R5,R6,R7,R8,R9,R10,R11,R12,R13,R14,R15);
    integer fd=0;
    initial if ($test$plusargs("cpu_trace")) fd=$fopen("build/sim/cpu-trace.txt","w");
    always @(posedge clk) if (fd && !rst && new_export)
        $fdisplay(fd,"%t pc=%x r0=%x r1=%x r2=%x r3=%x",$time,R15,R0,R1,R2,R3);
endmodule

// Functional DDR model for APF elaboration, without analog timing guarantees.
module altddio_bidir #(
    parameter width=12, extend_oe_disable="OFF", implement_input_in_lcell="OFF",
    parameter intended_device_family="Cyclone V", invert_output="OFF", lpm_hint="UNUSED",
    parameter lpm_type="altddio_bidir", oe_reg="UNREGISTERED", power_up_high="OFF"
)(
    input [width-1:0] datain_h,datain_l,
    input inclock,outclock,oe,aclr,aset,inclocken,outclocken,sclr,sset,
    output reg [width-1:0] dataout_h,dataout_l,
    inout [width-1:0] padio,
    output [width-1:0] combout,dqsundelayedout,output oe_out
);
    // Intel altddio_out captures both halves at the rising edge, retaining
    // the low half for the following falling edge. Sampling live datain_l
    // at that falling edge incorrectly mixes two registered core pixels.
    reg [width-1:0] out=0,low_half=0;
    always @(posedge outclock) begin out<=datain_h;low_half<=datain_l;end
    always @(negedge outclock) out<=low_half;
    always @(posedge inclock) dataout_h<=padio;
    always @(negedge inclock) dataout_l<=padio;
    assign padio=oe?out:{width{1'bz}};
    assign combout=out;assign dqsundelayedout=out;assign oe_out=oe;
endmodule
