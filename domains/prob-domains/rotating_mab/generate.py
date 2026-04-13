#!/usr/bin/env python3
"""Generate rotating_mab problem files for varying N (rounds) and R (retries)."""

import os

ARMS = ["arm_a", "arm_b", "arm_c"]


def generate(n_rounds: int, r_retries: int) -> str:
    """Return the HDDL text for prob_rotating_mab_n{N}_r{R}."""
    round_objs = " ".join(f"r{i+1}" for i in range(n_rounds))
    arm_objs = " ".join(ARMS)

    # Token objects: for each round ri, tokens ri_t0 .. ri_t(R-1)
    token_lines = []
    for i in range(n_rounds):
        tokens = " ".join(f"r{i+1}t{j}" for j in range(r_retries))
        token_lines.append(tokens)
    token_objs = "  ".join(token_lines)

    # HTN subtasks
    subtasks = "\n".join(
        f"            (task{i} (do_round r{i+1} r{i+1}t0))" for i in range(n_rounds)
    )
    orderings = "\n".join(
        f"            (< task{i} task{i+1})" for i in range(n_rounds - 1)
    )
    ordering_block = (
        f"        :ordering (and\n{orderings}\n        )" if n_rounds > 1 else ""
    )

    # Init: winner facts + rtoken chains
    winner_facts = "\n".join(
        f"        (winner r{i+1} {ARMS[i % 3]})" for i in range(n_rounds)
    )
    rtoken_facts_lines = []
    for i in range(n_rounds):
        for j in range(r_retries - 1):
            rtoken_facts_lines.append(
                f"        (next_rtoken r{i+1}t{j} r{i+1}t{j+1})"
            )
    rtoken_facts = "\n".join(rtoken_facts_lines)

    # Expected probability comment
    per_round = round(1 - 0.2**r_retries, 6)
    overall = round(per_round**n_rounds, 6)

    return f""";; {n_rounds} rounds, {r_retries} retries per round
;; Winner rotation: {", ".join(f"round {i+1}→{ARMS[i%3]}" for i in range(n_rounds))}
;; Max success probability (optimal policy): {per_round}^{n_rounds} ≈ {overall}
(define
    (problem prob_rotating_mab_n{n_rounds:02d}_r{r_retries:02d})
    (:domain rotating_mab)
    (:objects
        {round_objs} - round
        {arm_objs} - arm
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
{winner_facts}
{rtoken_facts}
    )
)
"""


if __name__ == "__main__":
    out_dir = os.path.dirname(__file__)
    configs = [
        (2, 2),
        (3, 2),
        (4, 3),
        (5, 3),
    ]
    for n, r in configs:
        fname = f"prob_rotating_mab_n{n:02d}_r{r:02d}.hddl"
        path = os.path.join(out_dir, fname)
        with open(path, "w") as f:
            f.write(generate(n, r))
        print(f"Wrote {fname}")
