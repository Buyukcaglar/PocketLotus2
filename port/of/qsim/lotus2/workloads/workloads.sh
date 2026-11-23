# Workloads for the Lotus core: the built-in scripted session: two lengths of the one-player
# session, and the linked two-player race.
#   attract  the title sequence and car screens (music, MODE 13 pictures)
#   race     the same, then the options menu and a race (engine sound, palette splits)
#   linked   a two-player race as one linked console draws it: player 2's own view
workload_names()       { echo "race attract linked"; }
workload_default_set() { echo "race attract"; }
workload_opts() {
    case "$1" in
        race)    printf '%s\n' --label race --args "bench 3000" ;;
        attract) printf '%s\n' --label attract --args "bench 440" ;;
        linked)  printf '%s\n' --label linked --args "bench 3000 view 2" ;;
        *) echo "unknown workload $1" >&2; return 1 ;;
    esac
}
workload_inputs_sha() { echo none; }
