#!/usr/bin/env python3
"""
Generate prob_sequential_retry problem instances.

Domain: N phases executed in sequence. Each phase has R retry tokens;
each attempt succeeds with p=0.5. If the attempt succeeds, done(?s) is set
permanently and the gate passes. Otherwise retry with the next token.

Per-phase optimal success probability = 1 - 0.5^R.
Overall (N independent phases): answer = (1 - 0.5^R)^N.

  N=2, R=3:  (1-0.125)^2 = 0.765625
  N=3, R=2:  (1-0.25)^3  = 0.421875

Usage:
    python generate.py                            # N=1..5, R=1..5
    python generate.py --min-n 2 --max-n 3 --min-r 2 --max-r 3
"""
import os
import argparse

DOMAIN = "prob_sequential_retry"


def generate_problem(n: int, r: int, out_path: str) -> float:
    steps = [f"s{i}" for i in range(n)]
    rtokens = [f"s{i}r{j}" for i in range(n) for j in range(r)]

    objects_line = " ".join(steps) + " - step"
    if rtokens:
        objects_line += "\n        " + " ".join(rtokens) + " - rtoken"

    next_rtoken_facts = "\n".join(
        f"        (next_rtoken s{i}r{j} s{i}r{j+1})"
        for i in range(n) for j in range(r - 1)
    )

    subtask_lines = "\n".join(
        f"            (t{i} (do_phase s{i} s{i}r0))" for i in range(n)
    )
    ordering_lines = "\n".join(
        f"            (< t{i} t{i+1})" for i in range(n - 1)
    )

    htn_block = f"    (:htn\n        :parameters ()\n        :subtasks (and\n{subtask_lines}\n        )"
    if n > 1:
        htn_block += f"\n        :ordering (and\n{ordering_lines}\n        )"
    htn_block += "\n    )"

    if r > 1:
        init_block = f"    (:init\n{next_rtoken_facts}\n    )"
    else:
        init_block = "    (:init)"

    content = f"""\
(define
    (problem {DOMAIN}_n{n:02d}_r{r:02d})
    (:domain {DOMAIN})
    (:objects
        {objects_line}
    )
{htn_block}
{init_block}
)
"""
    with open(out_path, "w") as f:
        f.write(content)

    answer = (1.0 - 0.5 ** r) ** n
    return answer


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--min-n", type=int, default=1, help="Smallest N (default: 1)")
    parser.add_argument("--max-n", type=int, default=5, help="Largest N (default: 5)")
    parser.add_argument("--min-r", type=int, default=1, help="Smallest R (default: 1)")
    parser.add_argument("--max-r", type=int, default=5, help="Largest R (default: 5)")
    parser.add_argument("--out-dir", type=str, default=os.path.dirname(os.path.abspath(__file__)))
    args = parser.parse_args()

    print(f"Generating {DOMAIN} problems (p=0.5 per attempt):")
    print(f"  {'File':<42}  N  R   Answer")
    print(f"  {'-'*42}  -  -  --------")
    for n in range(args.min_n, args.max_n + 1):
        for r in range(args.min_r, args.max_r + 1):
            fname = f"{DOMAIN}_n{n:02d}_r{r:02d}.hddl"
            out_path = os.path.join(args.out_dir, fname)
            answer = generate_problem(n, r, out_path)
            print(f"  {fname:<42}  {n:>1}  {r:>1}  {answer:.6f}")


if __name__ == "__main__":
    main()
