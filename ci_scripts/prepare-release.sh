#!/bin/sh
do_or_fatal() {
    # Do CMD $1 with rest of parameters else exit fatally and verbosely.
    __do_or_fatal__cmd="$1"
    shift # "$@" is REST after this
    "$__do_or_fatal__cmd" "$@" || {
        printf "do_or_fatal: failed to %s %s\n" "$1" "$@" 1>&2
        exit 1
    }
}

do_or_fatal mkdir -p out

do_or_fatal cp wheel/* out
do_or_fatal cp shiv/bin/* out

do_or_fatal cd out
hash_filename="sha256sum.txt"
for file in *; do
    printf "%s %s\n" "$(do_or_fatal nix hash file --base16 "$file")" "$file"
done | {
    # shellcheck disable=SC2094
    grep -v "$hash_filename" > "$hash_filename" # this is OK, we are NOT reading and writing to a file in the same pipeline
}
