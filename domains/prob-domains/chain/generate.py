#!/usr/bin/env python3
"""
Generate prob_chain problem instances.

Domain: N steps executed in sequence. Each step succeeds with p=0.9.
Optimal success probability = 0.9^N (exact, no approximation).

Usage:
    python generate.py                     # N=1..10
    python generate.py --max-n 20
    python generate.py --min-n 5 --max-n 5
"""
import os
import argparse

DOMAIN = "prob_chain"
P = 0.9


def generate_problem(n: int, out_path: str) -> float:
    steps = [f"s{i}" for i in range(n)]
    subtasks = "\n".join(f"            (task{i} (do_step s{i}))" for i in range(n))
    ordering_lines = "\n".join(f"            (< task{i} task{i+1})" for i in range(n - 1))

    htn_block = f"    (:htn\n        :parameters ()\n        :subtasks (and\n{subtasks}\n        )"
    if n > 1:
        htn_block += f"\n        :ordering (and\n{ordering_lines}\n        )"
    htn_block += "\n    )"

    content = f"""\
(define
    (problem {DOMAIN}_n{n:02d})
    (:domain {DOMAIN})
    (:objects
        {' '.join(steps)} - step
    )
{htn_block}
    (:init)
)
"""
    with open(out_path, "w") as f:
        f.write(content)

    answer = P ** n
    return answer


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--min-n", type=int, default=1, help="Smallest N (default: 1)")
    parser.add_argument("--max-n", type=int, default=10, help="Largest N (default: 10)")
    parser.add_argument("--out-dir", type=str, default=os.path.dirname(os.path.abspath(__file__)))
    args = parser.parse_args()

    print(f"Generating {DOMAIN} problems (p={P} per step):")
    print(f"  {'File':<30}  N   Answer")
    print(f"  {'-'*30}  --  --------")
    for n in range(args.min_n, args.max_n + 1):
        fname = f"{DOMAIN}_n{n:02d}.hddl"
        out_path = os.path.join(args.out_dir, fname)
        answer = generate_problem(n, out_path)
        print(f"  {fname:<30}  {n:>2}  {answer:.6f}")


if __name__ == "__main__":
    main()
