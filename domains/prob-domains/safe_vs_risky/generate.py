#!/usr/bin/env python3
"""
Generate prob_safe_vs_risky problem instances.

Domain: N phases executed in sequence. Each phase has R retry tokens.
At each token the planner chooses:
  - m_risky:       single risky_try (p=0.85), then gate. No retries.
  - m_safe_base:   single safe_try  (p=0.60), then gate. No retries.
  - m_safe_recurse: safe_try, then do_phase with next token (if it exists).

Optimal per-phase recurrence (k = tokens remaining after current, 0-indexed):
  P_0 = 0.85           (last token: risky beats safe 0.6)
  P_k = 0.6 + 0.4*P_{k-1}  (safe+recurse dominates since P_{k-1} >= 0.85 > 0.625)
  Closed form: P_k = 1 - 0.15 * 0.4^k

With R tokens: k = R-1 → P(one phase) = 1 - 0.15 * 0.4^(R-1)
Overall (N independent phases): answer = (1 - 0.15 * 0.4^(R-1))^N.

  N=3, R=1:  0.85^3          ≈ 0.614125  (risky only; R=1 means k=0)
  N=3, R=3:  (1-0.15*0.16)^3 ≈ 0.929714  (safe+recurse hybrid)

Usage:
    python generate.py                            # N=1..5, R=1..5
    python generate.py --min-n 3 --max-n 3 --min-r 1 --max-r 3
"""
import os
import argparse

DOMAIN = "prob_safe_vs_risky"


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

    # P_k = 1 - 0.15 * 0.4^k, k = R-1
    k = r - 1
    p_phase = 1.0 - 0.15 * (0.4 ** k)
    answer = p_phase ** n
    return answer


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--min-n", type=int, default=1, help="Smallest N (default: 1)")
    parser.add_argument("--max-n", type=int, default=5, help="Largest N (default: 5)")
    parser.add_argument("--min-r", type=int, default=1, help="Smallest R (default: 1)")
    parser.add_argument("--max-r", type=int, default=5, help="Largest R (default: 5)")
    parser.add_argument("--out-dir", type=str, default=os.path.dirname(os.path.abspath(__file__)))
    args = parser.parse_args()

    print(f"Generating {DOMAIN} problems:")
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
