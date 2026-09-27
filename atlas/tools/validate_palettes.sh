#!/usr/bin/env sh
# Re-validates the data palettes in core/css/tokens.css (spec 3.4) with the dataviz validator.
# Usage: VALIDATOR=/path/to/dataviz/scripts/validate_palette.js sh atlas/tools/validate_palettes.sh
# Re-run whenever a data hex changes; every block must PASS. ("Other" grey is a deliberate neutral, not validated.)
set -e
V="${VALIDATOR:?set VALIDATOR to dataviz/scripts/validate_palette.js}"
run() { echo "== $1"; shift; node "$V" "$@"; }
run "Tier · Paper (ordinal)"          "#004A2D,#1D6835,#478638,#6F9E45,#93B163" --ordinal --mode light --surface "#F1ECE1"
run "Tier · Night (ordinal)"          "#D7F96C,#A2DD50,#6FBF5D,#4E9F63,#407E5B" --ordinal --mode dark --surface "#0E1917"
run "TAM families · Paper (all pairs)" "#B07A1C,#0B7C55,#5A62CA" --pairs all --mode light --surface "#F1ECE1"
run "TAM families · Night (all pairs)" "#BF8834,#2A9E7A,#7F88E4" --pairs all --mode dark --surface "#0E1917"
run "Hydro · Paper (ordinal)"         "#15557E,#3F84AE,#7EADC7" --ordinal --mode light --surface "#F1ECE1"
run "Hydro · Night (ordinal)"         "#A5D2EA,#5E9EC3,#3A7596" --ordinal --mode dark --surface "#0E1917"
run "PPA series · Paper"              "#2A78D6,#EB6834" --mode light --surface "#FFFDF9"
run "PPA series · Night"              "#3987E5,#D95926" --mode dark --surface "#111C1A"
