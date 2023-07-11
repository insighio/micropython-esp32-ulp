#!/bin/bash

# export PYTHONPATH=.:$PYTHONPATH

set -e

LIST=${1:-opcodes opcodes_s2 assemble link util preprocess definesdb decode decode_s2}

for file in $LIST; do
    echo testing $file...
    micropython $file.py
done
