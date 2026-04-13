#!/usr/bin/env python3
"""Generate cheat_mab problem files for varying N (rounds) and R (retries)."""

import os


def generate(n_rounds: int, r_retries: int) -> str:
    round_objs = " ".join(f"r{i+1}" for i in range(n_rounds))

    token_groups = []
    for i in range(n_rounds):
        token_groups.append(" ".join(f"r{i+1}t{j}" for j in range(r_retries)))
    token_objs = "  ".join(token_groups)

    subtasks = "\n".join(
        f"            (task{i} (do_round r{i+1} r{i+1}t0))" for i in range(n_rounds)
    )
    orderings = "\n".join(
        f"            (< task{i} task{i+1})" for i in range(n_rounds - 1)
    )
    ordering_block = (
        f"        :ordering (and\n{orderings}\n        )" if n_rounds > 1 else ""
    )

    rtoken_lines = []
    for i in range(n_rounds):
        chain = " ".join(
            f"(next_rtoken r{i+1}t{j} r{i+1}t{j+1})" for j in range(r_retries - 1)
        )
        rtoken_lines.append(f"        {chain}")
    rtoken_facts = "\n".join(rtoken_lines)

    return f""";; {n_rounds} rounds, {r_retries} retries per round; bonus_available starts true.
(define
    (problem prob_cheat_mab_n{n_rounds:02d}_r{r_retries:02d})
    (:domain cheat_mab)
    (:objects
        {round_objs} - round
        {token_objs} - rtoken
    )
    (:htn
        :parameters ()
        :subtasks (and
{subtasks}
        )
{ordering_block}
    )
    (:init
        (bonus_available)
{rtoken_facts}
    )
)
"""


if __name__ == "__main__":
    out_dir = os.path.dirname(__file__)
    configs = [(3, 2), (3, 3), (5, 2), (5, 3)]
    for n, r in configs:
        fname = f"prob_cheat_mab_n{n:02d}_r{r:02d}.hddl"
        path = os.path.join(out_dir, fname)
        with open(path, "w") as f:
            f.write(generate(n, r))
        print(f"Wrote {fname}")
