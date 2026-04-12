#!/bin/bash
# Auto-generated runner script for probabilistic delivery benchmarks

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo '=== Threshold: 0.5 ==='
python3 "$ROOT_DIR/solve.py" "domains/prob_delivery/domain.hddl" "domains/prob_delivery/prob_delivery_01.hddl" "--fixed" "--threshold" "0.5"
python3 "$ROOT_DIR/solve.py" "domains/prob_delivery/domain.hddl" "domains/prob_delivery/prob_delivery_02.hddl" "--fixed" "--threshold" "0.5"
python3 "$ROOT_DIR/solve.py" "domains/prob_delivery/domain.hddl" "domains/prob_delivery/prob_delivery_03.hddl" "--fixed" "--threshold" "0.5"
python3 "$ROOT_DIR/solve.py" "domains/prob_delivery/domain.hddl" "domains/prob_delivery/prob_delivery_04.hddl" "--fixed" "--threshold" "0.5"
python3 "$ROOT_DIR/solve.py" "domains/prob_delivery/domain.hddl" "domains/prob_delivery/prob_delivery_05.hddl" "--fixed" "--threshold" "0.5"

echo '=== Threshold: 0.7 ==='
python3 "$ROOT_DIR/solve.py" "domains/prob_delivery/domain.hddl" "domains/prob_delivery/prob_delivery_01.hddl" "--fixed" "--threshold" "0.7"
python3 "$ROOT_DIR/solve.py" "domains/prob_delivery/domain.hddl" "domains/prob_delivery/prob_delivery_02.hddl" "--fixed" "--threshold" "0.7"
python3 "$ROOT_DIR/solve.py" "domains/prob_delivery/domain.hddl" "domains/prob_delivery/prob_delivery_03.hddl" "--fixed" "--threshold" "0.7"
python3 "$ROOT_DIR/solve.py" "domains/prob_delivery/domain.hddl" "domains/prob_delivery/prob_delivery_04.hddl" "--fixed" "--threshold" "0.7"
python3 "$ROOT_DIR/solve.py" "domains/prob_delivery/domain.hddl" "domains/prob_delivery/prob_delivery_05.hddl" "--fixed" "--threshold" "0.7"

echo '=== Threshold: 0.9 ==='
python3 "$ROOT_DIR/solve.py" "domains/prob_delivery/domain.hddl" "domains/prob_delivery/prob_delivery_01.hddl" "--fixed" "--threshold" "0.9"
python3 "$ROOT_DIR/solve.py" "domains/prob_delivery/domain.hddl" "domains/prob_delivery/prob_delivery_02.hddl" "--fixed" "--threshold" "0.9"
python3 "$ROOT_DIR/solve.py" "domains/prob_delivery/domain.hddl" "domains/prob_delivery/prob_delivery_03.hddl" "--fixed" "--threshold" "0.9"
python3 "$ROOT_DIR/solve.py" "domains/prob_delivery/domain.hddl" "domains/prob_delivery/prob_delivery_04.hddl" "--fixed" "--threshold" "0.9"
python3 "$ROOT_DIR/solve.py" "domains/prob_delivery/domain.hddl" "domains/prob_delivery/prob_delivery_05.hddl" "--fixed" "--threshold" "0.9"

echo '=== Threshold: 1.0 ==='
python3 "$ROOT_DIR/solve.py" "domains/prob_delivery/domain.hddl" "domains/prob_delivery/prob_delivery_01.hddl" "--fixed" "--threshold" "1.0"
python3 "$ROOT_DIR/solve.py" "domains/prob_delivery/domain.hddl" "domains/prob_delivery/prob_delivery_02.hddl" "--fixed" "--threshold" "1.0"
python3 "$ROOT_DIR/solve.py" "domains/prob_delivery/domain.hddl" "domains/prob_delivery/prob_delivery_03.hddl" "--fixed" "--threshold" "1.0"
python3 "$ROOT_DIR/solve.py" "domains/prob_delivery/domain.hddl" "domains/prob_delivery/prob_delivery_04.hddl" "--fixed" "--threshold" "1.0"
python3 "$ROOT_DIR/solve.py" "domains/prob_delivery/domain.hddl" "domains/prob_delivery/prob_delivery_05.hddl" "--fixed" "--threshold" "1.0"

