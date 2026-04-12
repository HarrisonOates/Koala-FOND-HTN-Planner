#!/usr/bin/env python3
"""
Generate prob_method_select domain + problem instances.

Domain: one compound task 'solve' with K methods.
Method i uses action try_i with probability (i+1)/(K+1), so probabilities
are evenly spaced in (0, 1) and the best method is always the last one.

  K=2: probs = [0.333, 0.667]          answer = 0.667
  K=3: probs = [0.25,  0.50,  0.75]    answer = 0.750
  K=9: probs = [0.1, 0.2, ..., 0.9]    answer = 0.900

Optimal success probability = K / (K+1).

This is generated as a domain+problem pair (domain_k{K}.hddl + problem_k{K}.hddl)
because the methods are structural (not typed objects).

Usage:
    python generate.py                      # K=2..10
    python generate.py --max-k 20
    python generate.py --min-k 5 --max-k 5
"""
import os
import argparse

DOMAIN_PREFIX = "prob_method_select"


def make_probs(k: int) -> list[float]:
    """Probabilities evenly spaced in (0, 1): (i+1)/(k+1) for i in 0..k-1."""
    return [(i + 1) / (k + 1) for i in range(k)]


def generate_domain(k: int, probs: list[float], out_path: str):
    domain_name = f"{DOMAIN_PREFIX}_k{k:02d}"
    lines = [
        f"(define (domain {domain_name})",
        "    (:requirements :typing :hierarchy)",
        "    (:predicates (done))",
        "",
        "    (:task solve :parameters ())",
        "",
    ]

    for i, p in enumerate(probs):
        lines += [
            f"    (:method m_solve_{i}",
            f"        :parameters ()",
            f"        :task (solve)",
            f"        :subtasks (and",
            f"            (t0 (try_{i}))",
            f"            (t1 (gate))",
            f"        )",
            f"        :ordering (and (< t0 t1))",
            f"    )",
            "",
        ]

    for i, p in enumerate(probs):
        p_fail = round(1.0 - p, 8)
        p_str = f"{p:.8f}".rstrip("0").rstrip(".")
        pf_str = f"{p_fail:.8f}".rstrip("0").rstrip(".")
        lines += [
            f"    (:action try_{i}",
            f"        :parameters ()",
            f"        :precondition ()",
            f"        :effect (probabilistic",
            f"            {p_str} (done)",
            f"            {pf_str} ()",
            f"        )",
            f"    )",
            "",
        ]

    lines += [
        "    (:action gate",
        "        :parameters ()",
        "        :precondition (done)",
        "        :effect ()",
        "    )",
        ")",
    ]

    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")


def generate_problem(k: int, out_path: str):
    domain_name = f"{DOMAIN_PREFIX}_k{k:02d}"
    problem_name = f"{DOMAIN_PREFIX}_k{k:02d}"
    content = f"""\
(define
    (problem {problem_name})
    (:domain {domain_name})
    (:htn
        :parameters ()
        :subtasks (and (task0 (solve)))
    )
    (:init)
)
"""
    with open(out_path, "w") as f:
        f.write(content)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--min-k", type=int, default=2, help="Smallest K (default: 2)")
    parser.add_argument("--max-k", type=int, default=10, help="Largest K (default: 10)")
    parser.add_argument("--out-dir", type=str, default=os.path.dirname(os.path.abspath(__file__)))
    args = parser.parse_args()

    print(f"Generating {DOMAIN_PREFIX} domain+problem pairs:")
    print(f"  {'Domain file':<35}  K   Best prob  Answer")
    print(f"  {'-'*35}  --  ---------  --------")
    for k in range(args.min_k, args.max_k + 1):
        probs = make_probs(k)
        answer = max(probs)

        domain_fname = f"domain_k{k:02d}.hddl"
        problem_fname = f"problem_k{k:02d}.hddl"
        generate_domain(k, probs, os.path.join(args.out_dir, domain_fname))
        generate_problem(k, os.path.join(args.out_dir, problem_fname))

        best_i = k - 1
        print(f"  {domain_fname:<35}  {k:>2}  {answer:.6f}   {answer:.6f}")


if __name__ == "__main__":
    main()
