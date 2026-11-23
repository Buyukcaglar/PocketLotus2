# SPDX-License-Identifier: GPL-3.0-or-later
# Invoke in build/quartus with quartus_sta -t ../../tools/quartus_timing_audit.tcl.
# Reports, including failures and unconstrained I/O, are evidence, not waivers.
project_open pocketlotus
file mkdir audit
foreach {model temperature} {slow 85 slow 0 fast 85 fast 0} {
    set tag ${model}_${temperature}
    create_timing_netlist -model $model -temperature $temperature -voltage 1100
    read_sdc
    update_timing_netlist
    report_clocks -file audit/${tag}_clocks.rpt
    report_sdc -ignored -file audit/${tag}_sdc.rpt
    check_timing -include {no_clock multiple_clock generated_clock no_input_delay no_output_delay partial_input_delay partial_output_delay loops latches pll_cross_check partial_multicycle multicycle_consistency partial_min_max_delay} -file audit/${tag}_checks.rpt
    report_ucp -file audit/${tag}_unconstrained.rpt
    report_net_delay -nworst 20 -file audit/${tag}_net_delay.rpt
    report_max_skew -npaths 20 -detail full_path -file audit/${tag}_max_skew.rpt
    set matches [open audit/${tag}_collections.tsv w]
    puts $matches "collection\tmatched_objects"
    foreach {label patterns} {
        gray_source {*|wg[*] *|rg[*]}
        gray_first_capture {*|wg1[*] *|rg1[*]}
        status_source {*|status_payload[*]}
        status_capture {*|snapshot[*]}
        keys_source {*|key_payload[*]}
        keys_capture {*|keys[*]}
        audio_source {*|audio|payload[*]}
        audio_capture {*|audio|samples[*]}
        psram_capture {*|memory|rdata[*]}
        probe_first_capture {*|probes|tap_meta[*] *|probes|flag_meta[*]}
        probe_second_capture {*|probes|tap_sync[*] *|probes|flag_sync[*]}
    } {
        set collection [get_registers $patterns]
        set count [get_collection_size $collection]
        if {$count == 0} {error "Required SDC collection empty: $label"}
        puts $matches "$label\t$count"
    }
    # 56 Gray bits in each direction across six FIFOs, before duplicates.
    if {[get_collection_size [get_registers {*|wg[*] *|rg[*]}]] < 56} {
        error "Gray source bits were optimized out of the bounded collection"
    }
    close $matches
    foreach kind {setup hold recovery removal} {
        report_timing -$kind -npaths 20 -detail full_path -file audit/${tag}_${kind}.rpt
        report_clock_transfers -$kind -file audit/${tag}_${kind}_transfers.rpt
    }
    set file [open audit/${tag}_clocks.tsv w]
    puts $file "name\tperiod_ns\tfrequency_mhz\tphase_degrees\tpositive_edge_registers"
    foreach_in_collection clock [get_clocks *] {
        set period [get_clock_info -period $clock]
        puts $file "[get_clock_info -name $clock]\t$period\t[expr {1000.0/$period}]\t[get_clock_info -phase $clock]\t[get_clock_info -nreg_pos $clock]"
    }
    close $file
    delete_timing_netlist
}
project_close
