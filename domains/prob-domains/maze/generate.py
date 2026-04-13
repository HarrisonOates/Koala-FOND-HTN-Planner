#!/usr/bin/env python3
"""Generate maze problem files for varying k (retry tokens per move step).

Layout is always the 5-cell linear corridor:
  c0 (start) — c1 — c2 (key) — c3 — c4 (exit)
with 4 move steps.
"""

import os

N_STEPS = 4        # number of advance steps
N_CELLS = 5        # c0..c4


def generate(k_retries: int) -> str:
    cell_objs = " ".join(f"c{i}" for i in range(N_CELLS))

    token_groups = []
    for step in range(N_STEPS):
        tokens = " ".join(f"m{step}t{j}" for j in range(k_retries))
        token_groups.append(tokens)
    token_objs = "\n        ".join(token_groups) + " - rtoken"

    subtasks = (
        "            (task0 (advance c0 c1 m0t0))\n"
        "            (task1 (advance c1 c2 m1t0))\n"
        "            (task2 (do_collect_key c2))\n"
        "            (task3 (advance c2 c3 m2t0))\n"
        "            (task4 (advance c3 c4 m3t0))\n"
        "            (task5 (do_enter_exit c4))"
    )

    adj_facts = " ".join(f"(adj c{i} c{i+1})" for i in range(N_CELLS - 1))

    rtoken_lines = []
    for step in range(N_STEPS):
        chain = " ".join(
            f"(next_rtoken m{step}t{j} m{step}t{j+1})" for j in range(k_retries - 1)
        )
        rtoken_lines.append(f"        {chain}")
    rtoken_facts = "\n".join(rtoken_lines)

    per_step = round(1 - 0.2**k_retries, 6)
    overall = round(per_step**N_STEPS, 6)

    return f""";; 5-cell corridor, k={k_retries} retry tokens per move step.
;; Per-step success: 1 − 0.2^{k_retries} = {per_step}
;; Overall ({N_STEPS} steps): {per_step}^{N_STEPS} ≈ {overall}
(define
    (problem prob_maze_k{k_retries:02d})
    (:domain maze)
    (:objects
        {cell_objs} - cell
        {token_objs}
    )
    (:htn
        :parameters ()
        :subtasks (and
{subtasks}
        )
        :ordering (and
            (< task0 task1)
            (< task1 task2)
            (< task2 task3)
            (< task3 task4)
            (< task4 task5)
        )
    )
    (:init
        (at c0)
        {adj_facts}
        (key_cell c2)
        (exit_cell c4)
{rtoken_facts}
    )
)
"""


if __name__ == "__main__":
    out_dir = os.path.dirname(__file__)
    for k in [2, 3, 5]:
        fname = f"prob_maze_k{k:02d}.hddl"
        path = os.path.join(out_dir, fname)
        with open(path, "w") as f:
            f.write(generate(k))
        print(f"Wrote {fname}")
