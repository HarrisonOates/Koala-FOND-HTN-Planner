#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Convert a JANI file (single automaton, MDP/DTMC) to probHDDL format.
Applies the FOND-to-FOND HTN compilation: wraps all actions inside a
recursive SOLVE compound task.

Usage:
    python3 jani2probhddl.py <file.jani> [--config config.py] [--out-dir DIR]
"""

import argparse
import sys
import os
import math
import json
import re
from sympy import Or, And, Not, Implies, to_dnf, Symbol


class Options:
    EQUAL = False
    LESS = False
    GREATER = False
    LESS_EQUAL = False
    GREATER_EQUAL = False
    SUM = False
    SUBTRACTION = False
    MULTIPLICATION = False
    DIVISION = False
    MAX = False
    MIN = False

    @staticmethod
    def load(f):
        import importlib.util
        spec = importlib.util.spec_from_file_location("config", f)
        config = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config)
        for attr in ["LESS", "EQUAL", "GREATER", "LESS_EQUAL", "GREATER_EQUAL",
                     "SUM", "SUBTRACTION", "MULTIPLICATION", "DIVISION", "MAX", "MIN"]:
            if hasattr(config, attr):
                setattr(Options, attr, getattr(config, attr))


def replace_special_characters(s):
    return re.sub(r"\W", "_", s)


# Global mutable state (mirrors jani2ppddl.py structure)
bool_vars: set = set()
num_dummy_vars: int = -1
helper_variables: set = set()
var_dict: dict = {}
loc_var_dict: dict = {}
loc_vars: list = []   # list of sets, one per automaton
data: dict = {}       # loaded JANI JSON
prec_num: dict = {}   # {varName: intValue} for preconditions of current action


def no_syncs() -> bool:
    """Return True if there are no non-trivial synchronisations."""
    system = data.get("system", {})
    syncs = system.get("syncs", [])
    if not syncs:
        return True
    for s in syncs:
        count = sum(1 for act in s.get("synchronise", []) if act is not None)
        if count > 1:
            return False
    return True


def is_boolean(var_name: str) -> bool:
    return var_name in bool_vars


def parse_arith(e) -> int:
    """Recursively evaluate a JANI arithmetic expression to an integer."""
    stack = []
    curr = e
    while isinstance(curr, dict):
        r = curr["right"]
        stack.append(parse_arith(r) if isinstance(r, dict) else r)
        stack.append(curr["op"])
        curr = curr["left"]
    curr_val = curr
    while stack:
        op = stack.pop()
        next_val = stack.pop()
        curr_val = eval(str(curr_val) + op + str(next_val))
    return curr_val


# ---------------------------------------------------------------------------
# Task 2: Expression translation
# ---------------------------------------------------------------------------

def run_tree(node, out_lines: list, auto_name: str = ""):
    """Write initial-state facts from a restrict-initial tree."""
    if node["op"] == "=":
        if is_boolean(node["left"]):
            if node["right"] is True:
                out_lines.append(f"\t\t(fulfiled {node['left']})")
        else:
            out_lines.append(f"\t\t(value {node['left']} n{node['right']})")
    elif node["op"] == "\u2227":
        run_tree(node["left"], out_lines, auto_name)
        run_tree(node["right"], out_lines, auto_name)


def run_tree_ri(node, res_init: set):
    """Collect variable names from a restrict-initial tree."""
    if isinstance(node, bool):
        return
    if node["op"] == "=":
        res_init.add(node["left"])
    elif node["op"] == "\u2227":
        run_tree_ri(node["left"], res_init)
        run_tree_ri(node["right"], res_init)


def print_tree(node) -> str:
    """Format a probability expression (usually just a float literal)."""
    if isinstance(node, dict):
        return print_tree(node["left"]) + node["op"] + print_tree(node["right"])
    return str(node)


def dec_exp(e, j: int) -> str:
    """Translate a JANI expression into an HDDL precondition string."""
    global num_dummy_vars, prec_num

    if isinstance(e, str):
        if e in bool_vars:
            if e in loc_vars[j]:
                return f"(fulfiled {e}_{data['automata'][j]['name']})"
            return f"(fulfiled {e})"
        elif e in loc_vars[j]:
            return f"(value {e}_{data['automata'][j]['name']} ?vl{e})"
        return f"(value {e} ?v{e})"
    elif isinstance(e, bool):
        return ""
    elif isinstance(e, (int, float)):
        return f"n{int(e)}"
    elif not isinstance(e, dict):
        return f"Error: unexpected type {type(e)}\n"

    # resolve left/right names for local vs global vars
    e_left_name = ""
    e_right_name = ""
    if "left" in e:
        if not isinstance(e["left"], dict):
            e_left_name = (f"{e['left']}_{data['automata'][j]['name']}"
                           if e["left"] in loc_vars[j] else e["left"])
        if not isinstance(e["right"], dict):
            e_right_name = (f"{e['right']}_{data['automata'][j]['name']}"
                            if isinstance(e.get("right"), str) and e["right"] in loc_vars[j]
                            else (e["right"] if isinstance(e.get("right"), str) else ""))

    op = e["op"]
    if op == "\u2227":    # AND
        return f"\t\t\t(and \n\t\t\t\t{dec_exp(e['left'], j)}\n\t\t\t\t{dec_exp(e['right'], j)}\n\t\t\t)\n"
    elif op == "\u2228":  # OR
        return f"\t\t\t(or \n\t\t\t\t{dec_exp(e['left'], j)}\n\t\t\t\t{dec_exp(e['right'], j)}\n\t\t\t)\n"
    elif op == "\u00AC":  # NOT
        return f"\t\t\t(not \n{dec_exp(e['exp'], j)}\n\t\t\t)\n"
    elif op == "=":
        if e["right"] is True:
            return f"\t\t\t(fulfiled {e_left_name})\n"
        elif e["right"] is False:
            return f"\t\t\t(not (fulfiled {e_left_name}))\n"
        elif isinstance(e["right"], int):
            prec_num[e_left_name] = e["right"]
            return f"\t\t\t(value {e_left_name} n{e['right']})\n"
        else:
            # var = var
            return f"\t\t\t(value {e_left_name} ?v{e_right_name})\n"
    elif op == "\u2260":  # !=
        return f"\t\t\t(not (value {e_left_name} ?v{e_right_name}))\n"
    elif op == "\u2264":  # <=
        if Options.LESS_EQUAL:
            left_str = f"?v{e_left_name}" if isinstance(e["left"], str) else f"n{e['left']}"
            right_str = f"?v{e_right_name}" if isinstance(e["right"], str) else f"n{e['right']}"
            return f"\t\t\t(leq {left_str} {right_str})\n"
        return ""
    elif op == "\u2265":  # >=
        if Options.GREATER_EQUAL:
            left_str = f"?v{e_left_name}" if isinstance(e["left"], str) else f"n{e['left']}"
            right_str = f"?v{e_right_name}" if isinstance(e["right"], str) else f"n{e['right']}"
            return f"\t\t\t(geq {left_str} {right_str})\n"
        return ""
    elif op == "\u003C":  # <
        if Options.LESS:
            left_str = f"?v{e_left_name}" if isinstance(e["left"], str) else f"n{e['left']}"
            right_str = f"?v{e_right_name}" if isinstance(e["right"], str) else f"n{e['right']}"
            return f"\t\t\t(less {left_str} {right_str})\n"
        return ""
    elif op == "\u003E":  # >
        if Options.GREATER:
            left_str = f"?v{e_left_name}" if isinstance(e["left"], str) else f"n{e['left']}"
            right_str = f"?v{e_right_name}" if isinstance(e["right"], str) else f"n{e['right']}"
            return f"\t\t\t(greater {left_str} {right_str})\n"
        return ""
    else:
        return f"Error: unsupported op '{op}'\n"


_sympy_var_counter = 0
_var_x_values: list = []


def bool_exp(e) -> object:
    """Encode a JANI guard as a SymPy boolean expression."""
    global _sympy_var_counter, _var_x_values
    if isinstance(e, bool):
        return e
    if isinstance(e, str):
        _sympy_var_counter += 1
        _var_x_values.append(e)
        return Symbol(f"x{_sympy_var_counter}")
    if not isinstance(e, dict):
        return e
    op = e["op"]
    if op == "\u2227":
        return And(bool_exp(e["left"]), bool_exp(e["right"]))
    elif op == "\u2228":
        return Or(bool_exp(e["left"]), bool_exp(e["right"]))
    elif op == "\u00AC":
        return Not(bool_exp(e["exp"]))
    else:
        _sympy_var_counter += 1
        _var_x_values.append(e)
        return Symbol(f"x{_sympy_var_counter}")


def get_o_clauses(expr) -> list:
    """Get OR clauses from a SymPy DNF expression."""
    if isinstance(expr, Or):
        return list(expr.args)
    return [expr]


def get_a_clauses(expr) -> list:
    """Get AND clauses from a SymPy conjunction."""
    if isinstance(expr, And):
        return list(expr.args)
    return [expr]
