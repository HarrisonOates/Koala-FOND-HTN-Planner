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


# ---------------------------------------------------------------------------
# Task 3: Parameter tracking and precon_from_ass
# ---------------------------------------------------------------------------

leaves: set = set()
left_leaves: set = set()
pre_set_int: set = set()


def search_leaves(node, dest_count: int):
    """Collect variables that need parameters in the action signature."""
    global leaves, left_leaves, pre_set_int
    if isinstance(node, dict):
        if "op" in node:
            op = node["op"]
            if op == "=":
                if not isinstance(node["right"], int) and not isinstance(node["left"], bool):
                    leaves.add(node["left"])
                    left_leaves.add(node["left"] + str(dest_count))
                    if not isinstance(node["right"], dict):
                        leaves.add(node["right"])
                    return
                elif isinstance(node["right"], int) and not isinstance(node["left"], dict):
                    pre_set_int.add(node["left"])
                    return
            elif op == "\u2260":
                if not isinstance(node["right"], int):
                    search_leaves(node["left"], dest_count)
                    search_leaves(node["right"], dest_count)
                return
            elif op in {"\u003C", "\u003E", "\u2264", "\u2265"}:
                if not isinstance(node["right"], int):
                    leaves.add(node["right"])
                if not isinstance(node["left"], int):
                    leaves.add(node["left"])
                return
        if "left" in node:
            if not isinstance(node["right"], int):
                search_leaves(node["left"], dest_count)
                search_leaves(node["right"], dest_count)
            else:
                if not isinstance(node["left"], (int, dict)):
                    left_leaves.add(node["left"] + str(dest_count))
                else:
                    search_leaves(node["left"], dest_count)
        else:  # (not ...)
            search_leaves(node["exp"], dest_count)
    else:
        if not isinstance(node, int) and node not in bool_vars:
            leaves.add(node)


def precon_from_ass(ass_list: list, j: int, res_init: set,
                    curr_leaves: set, dest_count: int, precon_set: set):
    """
    Add preconditions required for arithmetic assignments.
    Mirrors preconFromAss() from jani2ppddl.py.
    This handles cases where an effect assignment is arithmetic (e.g. var = var+1),
    requiring the current value of the variable in the precondition.
    """
    for assign in ass_list:
        ref = str(assign["ref"])
        val = assign["value"]
        # Only process if assignment is arithmetic (dict) not a literal
        if isinstance(val, dict):
            if ref not in res_init:
                if ref in curr_leaves:
                    pass  # already captured via search_leaves
                else:
                    precon_set.add(f"\t\t\t(value {ref} ?v{ref})\n")


def build_param_string(
    curr_leaves: set,
    curr_left_leaves: set,
    auto_name: str,
) -> tuple[str, list[str]]:
    """
    Build the HDDL parameter string (for :parameters) and a list of
    parameter names (for the method subtask call).
    Returns (param_str, param_names).
    """
    param_str = ""
    param_names = []
    for lv in sorted(curr_leaves):
        if lv in var_dict:
            param_str += f"\n\t\t ?v{lv} - num"
            param_names.append(f"?v{lv}")
        elif auto_name in loc_var_dict and lv in loc_var_dict[auto_name]:
            param_str += f"\n\t\t ?v{lv}_{auto_name} - num"
            param_names.append(f"?v{lv}_{auto_name}")
        else:
            param_str += f"\n\t\t ?v{lv} - num"
            param_names.append(f"?v{lv}")
    for ll in sorted(curr_left_leaves):
        m = re.search(r'\d+$', ll)
        test_var = ll[:-1] if m else ll
        if test_var in var_dict:
            param_str += f"\n\t\t ?vl{ll} - num"
            param_names.append(f"?vl{ll}")
        elif auto_name in loc_var_dict and test_var in loc_var_dict[auto_name]:
            param_str += f"\n\t\t ?vl{ll}_{auto_name} - num"
            param_names.append(f"?vl{ll}_{auto_name}")
        else:
            param_str += f"\n\t\t ?vl{ll} - num"
            param_names.append(f"?vl{ll}")
    return param_str, param_names


# ---------------------------------------------------------------------------
# Task 4: Domain header generation
# ---------------------------------------------------------------------------

def write_domain_header(out: list):
    """Write (:types ...) (:constants ...) (:predicates ...) blocks."""
    global bool_vars, var_dict, loc_var_dict, loc_vars

    domain_name = replace_special_characters(data["name"])
    out.append(f"(define (domain {domain_name})")
    out.append(f"\t(:requirements :typing :hierarchy)")

    # --- types ---
    types = {"loc", "bool"}
    num_need = False
    for v in data.get("variables", []):
        t = v["type"]
        base = t["base"] if isinstance(t, dict) else t
        types.add(base)
        if base == "int":
            num_need = True
    for a in data.get("automata", []):
        for v in a.get("variables", []):
            t = v["type"]
            base = t["base"] if isinstance(t, dict) else t
            types.add(base)
            if base == "int":
                num_need = True
    if data.get("constants"):
        for c in data["constants"]:
            t = c["type"]
            base = t["base"] if isinstance(t, dict) else t
            types.add(base)
            if base == "int":
                num_need = True

    type_str = " ".join(types)
    out.append(f"\t(:types {type_str}{' num' if num_need else ''})")

    # --- constants ---
    min_var = sys.maxsize
    max_var = 0
    out.append("\t(:constants")
    out.append("\t\tgoal_condition - bool")

    for v in data.get("variables", []):
        t = v["type"]
        if isinstance(t, dict):
            out.append(f"\t\t{v['name']} - {t['base']}")
            var_dict[v["name"]] = t["base"]
            min_var = min(min_var, t.get("lower-bound", 0))
            max_var = max(max_var, t.get("upper-bound", 0))
        else:
            out.append(f"\t\t{v['name']} - {t}")
            var_dict[v["name"]] = t
            if t == "bool":
                bool_vars.add(v["name"])

    if data.get("constants"):
        for c in data["constants"]:
            t = c["type"]
            if isinstance(t, dict):
                out.append(f"\t\t{c['name']} - {t['base']}")
                var_dict[c["name"]] = t["base"]
            else:
                out.append(f"\t\t{c['name']} - {t}")
                var_dict[c["name"]] = t
                if t == "bool":
                    bool_vars.add(c["name"])

    for a in data["automata"]:
        aname = a["name"]
        loc_var_dict[aname] = {}
        for v in a.get("variables", []):
            t = v["type"]
            if isinstance(t, dict):
                out.append(f"\t\t{v['name']}_{aname} - {t['base']}")
                loc_var_dict[aname][v["name"]] = t["base"]
                min_var = min(min_var, t.get("lower-bound", 0))
                max_var = max(max_var, t.get("upper-bound", 0))
            else:
                out.append(f"\t\t{v['name']}_{aname} - {t}")
                loc_var_dict[aname][v["name"]] = t
                if t == "bool":
                    bool_vars.add(v["name"])
        for loc in a["locations"]:
            out.append(f"\t\t{loc['name']}_{aname} - loc")

    if num_need and min_var <= max_var:
        nums = " ".join(f"n{i}" for i in range(min_var, max_var + 1))
        out.append(f"\t\t{nums} - num")
    out.append("\t)")

    # --- predicates ---
    out.append("\t(:predicates")
    if "bool" in types:
        out.append("\t\t(fulfiled ?x - bool)")
    out.append("\t\t(at ?l - loc)")
    for t in types:
        if t not in ("bool", "loc"):
            out.append(f"\t\t(value ?v - {t} ?n - num)")
    if Options.EQUAL:         out.append("\t\t(equal ?n1 ?n2 - num)")
    if Options.LESS:          out.append("\t\t(less ?n1 ?n2 - num)")
    if Options.GREATER:       out.append("\t\t(greater ?n1 ?n2 - num)")
    if Options.LESS_EQUAL:    out.append("\t\t(leq ?n1 ?n2 - num)")
    if Options.GREATER_EQUAL: out.append("\t\t(geq ?n1 ?n2 - num)")
    if Options.SUM:           out.append("\t\t(add ?n1 ?n2 ?n3 - num)")
    if Options.SUBTRACTION:   out.append("\t\t(sub ?n1 ?n2 ?n3 - num)")
    if Options.MULTIPLICATION: out.append("\t\t(mult ?n1 ?n2 ?n3 - num)")
    if Options.DIVISION:      out.append("\t\t(mod ?n1 ?n2 ?n3 - num)")
    if Options.MAX:           out.append("\t\t(max ?n1 ?n2 ?n3 - num)")
    if Options.MIN:           out.append("\t\t(min ?n1 ?n2 ?n3 - num)")
    out.append("\t)")

    return min_var, max_var


def write_htn_task(out: list):
    """Write the (:task solve ...) declaration."""
    out.append("\n\t;; HTN task")
    out.append("\t(:task solve :parameters ())")


# ---------------------------------------------------------------------------
# Task 5: Action and method generation
# ---------------------------------------------------------------------------

def _unique_name(name: str, used: set) -> str:
    if name not in used:
        return name
    i = 1
    candidate = f"{name}_{i}"
    while candidate in used:
        i += 1
        candidate = f"{name}_{i}"
    return candidate


def _emit_action_and_method(
    out: list, methods: list,
    action_name: str, param_str: str, param_names: list,
    precon_body: str, effect_str: str,
):
    """Write one (:action ...) block and its corresponding SOLVE method."""
    # Action
    out.append(f"\t(:action {action_name}")
    out.append(f"\t\t:parameters ({param_str}\n\t\t)")
    out.append(f"\t\t:precondition ({precon_body})")
    out.append(f"\t\t{effect_str}")
    out.append("\t)\n")

    # Corresponding SOLVE method
    call_args = " ".join(param_names)
    methods.append(f"\t(:method m_solve_{action_name}")
    methods.append(f"\t\t:parameters ({param_str}\n\t\t)")
    methods.append(f"\t\t:task (solve)")
    methods.append(f"\t\t:subtasks (and")
    methods.append(f"\t\t\t(t0 ({action_name} {call_args}))")
    methods.append(f"\t\t\t(t1 (solve))")
    methods.append(f"\t\t)")
    methods.append(f"\t\t:ordering (and (< t0 t1))")
    methods.append(f"\t)\n")


def _rebuild_jani_expr(sympy_expr):
    """Rebuild a JANI expression dict from a SymPy term (looks up _var_x_values)."""
    if isinstance(sympy_expr, Not):
        idx = int(str(sympy_expr.args[0])[1:]) - 1
        inner = _var_x_values[idx]
        if isinstance(inner, dict):
            # flip comparison
            flip = {"\u2264": "\u003E", "\u2265": "\u003C",
                    "\u003E": "\u2264", "\u003C": "\u2265"}
            flipped_op = flip.get(inner["op"])
            if flipped_op:
                return {"op": flipped_op, "left": inner["left"], "right": inner["right"]}
        return {"op": "\u00AC", "exp": inner}
    elif isinstance(sympy_expr, And):
        clauses = get_a_clauses(sympy_expr)
        result = _rebuild_jani_expr(clauses[0])
        for c in clauses[1:]:
            result = {"op": "\u2227", "left": _rebuild_jani_expr(c), "right": result}
        return result
    elif isinstance(sympy_expr, Symbol):
        idx = int(str(sympy_expr)[1:]) - 1
        return _var_x_values[idx]
    return sympy_expr


def write_effect_block(e: dict, a: dict, j: int, curr_leaves: set) -> str:
    """Build the :effect string for a JANI edge."""
    lines = []
    lines.append("\n\t\t:effect (probabilistic")
    dest_count = 0
    for d in e["destinations"]:
        assignments = d.get("assignments", [])
        prob_str = print_tree(d["probability"]["exp"]) if "probability" in d else "1"
        if not assignments and e["location"] == d["location"]:
            lines.append(f"\t\t\t{prob_str} ()")
        else:
            lines.append(f"\t\t\t{prob_str}")
            parts = []
            if e["location"] != d["location"]:
                parts.append(f"(at {d['location']}_{a['name']})")
                parts.append(f"(not (at {e['location']}_{a['name']}))")
            for assign in assignments:
                ref = str(assign["ref"])
                val = assign["value"]
                ref_name = (f"{ref}_{a['name']}" if ref in loc_vars[j] else ref)
                if val is True:
                    parts.append(f"(fulfiled {ref_name})")
                elif val is False:
                    parts.append(f"(not (fulfiled {ref_name}))")
                elif isinstance(val, int):
                    if ref in curr_leaves:
                        parts.append(f"(not (value {ref_name} ?v{ref_name}))")
                    elif ref_name in prec_num:
                        parts.append(f"(not (value {ref_name} n{prec_num[ref_name]}))")
                    else:
                        parts.append(f"(not (value {ref_name} ?v{ref_name}))")
                    parts.append(f"(value {ref_name} n{val})")
                else:  # arithmetic
                    parts.append(f"(not (value {ref_name} ?v{ref_name}))")
                    parts.append(f"(value {ref_name} ?vl{ref_name}{dest_count})")
            if parts:
                effect_body = " ".join(parts)
                lines.append(f"\t\t\t\t(and {effect_body})")
        dest_count += 1
    lines.append("\t\t)")
    return "\n".join(lines)


def write_actions_and_methods(out: list, methods: list):
    """
    Generate all (:action ...) blocks and collect corresponding SOLVE methods.
    `methods` is a list of strings that will be written after the HTN task declaration.
    """
    global leaves, left_leaves, pre_set_int, helper_variables, prec_num, _sympy_var_counter, _var_x_values

    j = 0
    for a in data["automata"]:
        aname = a["name"]
        action_names_used = set()
        count_actions = 0

        for e in a["edges"]:
            count_actions += 1
            prec_num = {}
            helper_variables.clear()

            # --- build action name ---
            end_dest = "".join(f"_{d['location']}" for d in e["destinations"])
            if "action" in e:
                base_name = f"{replace_special_characters(e['action'])}_{aname}_{e['location']}_to{end_dest}"
            else:
                base_name = f"{aname}_{e['location']}_to{end_dest}"

            # --- collect parameters via search_leaves ---
            leaves = set()
            left_leaves = set()
            pre_set_int = set()
            dest_count = 0
            if "guard" in e:
                search_leaves(e["guard"]["exp"], dest_count)
            dest_count = 0
            for d in e["destinations"]:
                for asg in d.get("assignments", []):
                    val = asg["value"]
                    if not isinstance(val, (int, bool)):
                        left_leaves.add(str(asg["ref"]) + str(dest_count))
                        leaves.add(str(asg["ref"]))
                        search_leaves(val, dest_count)
                    else:
                        if str(asg["ref"]) not in pre_set_int and str(asg["ref"]) not in bool_vars:
                            leaves.add(str(asg["ref"]))
                dest_count += 1

            param_str, param_names = build_param_string(leaves, left_leaves, aname)

            # --- precondition: guard → DNF → list of parts ---
            parts = []
            precon_set = set()
            if "guard" in e:
                guard_exp = e["guard"]["exp"]
                if isinstance(guard_exp, bool):
                    # no guard
                    dest_count = 0
                    for d in e["destinations"]:
                        res_init = set()
                        if data.get("restrict-initial"):
                            run_tree_ri(data["restrict-initial"]["exp"], res_init)
                        precon_from_ass(d.get("assignments", []), j, res_init, leaves, dest_count, precon_set)
                        dest_count += 1
                else:
                    _sympy_var_counter = 0
                    _var_x_values.clear()
                    res = bool_exp(guard_exp)
                    if isinstance(res, (Or, And, Not, Implies)):
                        resDNF = to_dnf(res)
                        for o in get_o_clauses(resDNF):
                            parts.append(_rebuild_jani_expr(o))
                    else:
                        parts.append(_var_x_values[0] if _var_x_values else guard_exp)
                    # call dec_exp on the raw guard to populate prec_num
                    dec_exp(guard_exp, j)
                    dest_count = 0
                    for d in e["destinations"]:
                        res_init = set()
                        if data.get("restrict-initial"):
                            run_tree_ri(data["restrict-initial"]["exp"], res_init)
                        precon_from_ass(d.get("assignments", []), j, res_init, leaves, dest_count, precon_set)
                        dest_count += 1
            else:
                parts = []

            # --- effect block (shared across all DNF versions) ---
            effect_str = write_effect_block(e, a, j, leaves)

            # --- emit one action per DNF clause (or just one if no disjunction) ---
            pnum = 0
            if not parts:
                action_name = _unique_name(base_name + str(pnum), action_names_used)
                action_names_used.add(action_name)
                hvar_str = "".join(f"\n{hv} - num" for hv in helper_variables)
                loc_precon = f"\n\t\t\t(at {e['location']}_{aname})\n"
                extra_precon = "".join(precon_set)
                if extra_precon:
                    precon_body = f"\n\t\t\tand {loc_precon}{extra_precon}"
                else:
                    precon_body = loc_precon
                _emit_action_and_method(
                    out, methods, action_name,
                    param_str + hvar_str, param_names,
                    precon_body, effect_str
                )
                pnum += 1
            else:
                for part in parts:
                    action_name = _unique_name(base_name + str(pnum), action_names_used)
                    action_names_used.add(action_name)
                    helper_variables.clear()
                    guard_hddl = dec_exp(part, j)
                    hvar_str = "".join(f"\n{hv} - num" for hv in helper_variables)
                    loc_precon = f"\n\t\t\t(at {e['location']}_{aname})\n"
                    extra_precon = "".join(precon_set)
                    precon_body = f"\n\t\t\tand {loc_precon}{guard_hddl}{extra_precon}"
                    _emit_action_and_method(
                        out, methods, action_name,
                        param_str + hvar_str, param_names,
                        precon_body, effect_str
                    )
                    pnum += 1
        j += 1


# ---------------------------------------------------------------------------
# Task 6: Goal actions and termination method
# ---------------------------------------------------------------------------

def _find_goal_right(expr: dict):
    """Navigate JANI property expression tree to find the right-hand side of U/F."""
    op = expr.get("op")
    if op in ("U", "F"):
        return expr.get("right", expr)
    right = expr.get("right") or expr.get("exp")
    if right is None:
        return None
    if isinstance(right, dict):
        return _find_goal_right(right)
    return None


def write_goal_actions_and_method(out: list, methods: list):
    """
    For each goal clause in the JANI property, emit:
      1. An (:action achieveGoalN ...) that sets (fulfiled goal_condition)
      2. A corresponding SOLVE method
    Then emit the termination method m_solve_done.
    """
    global _sympy_var_counter, _var_x_values, leaves, left_leaves, pre_set_int

    if not data.get("properties"):
        # No goal: termination method with no precondition
        methods.insert(0, "\t(:method m_solve_done\n\t\t:parameters ()\n\t\t:task (solve)\n\t\t:subtasks ()\n\t)\n")
        return

    goal_disjuncts = []
    for prop in data["properties"]:
        _sympy_var_counter = 0
        _var_x_values = []
        goal_right = _find_goal_right(prop["expression"]["values"])
        if goal_right is None:
            continue
        res = bool_exp(goal_right)
        if isinstance(res, (Or, And, Not, Implies)):
            resDNF = to_dnf(res)
            for o in get_o_clauses(resDNF):
                goal_disjuncts.append(_rebuild_jani_expr(o))
        else:
            goal_disjuncts.append(_var_x_values[0] if _var_x_values else goal_right)

    goal_action_names = []
    for g, goal_clause in enumerate(goal_disjuncts):
        action_name = f"achieveGoal{g}"
        goal_action_names.append(action_name)
        leaves = set()
        left_leaves = set()
        pre_set_int = set()
        search_leaves(goal_clause, 0)
        param_str, param_names = build_param_string(leaves, left_leaves, "")
        precon_hddl = dec_exp(goal_clause, 0)
        out.append(f"\t(:action {action_name}")
        out.append(f"\t\t:parameters ({param_str}\n\t\t)")
        out.append(f"\t\t:precondition\n{precon_hddl}")
        out.append(f"\t\t:effect (fulfiled goal_condition)")
        out.append("\t)\n")

        # SOLVE method for this goal action
        call_args = " ".join(param_names)
        methods.append(f"\t(:method m_solve_{action_name}")
        methods.append(f"\t\t:parameters ({param_str}\n\t\t)")
        methods.append(f"\t\t:task (solve)")
        methods.append(f"\t\t:subtasks (and")
        methods.append(f"\t\t\t(t0 ({action_name} {call_args}))")
        methods.append(f"\t\t\t(t1 (solve))")
        methods.append(f"\t\t)")
        methods.append(f"\t\t:ordering (and (< t0 t1))")
        methods.append(f"\t)\n")

    # Termination method (inserted at beginning of methods list so it's tried first)
    methods.insert(0, "\t(:method m_solve_done\n\t\t:parameters ()\n\t\t:task (solve)\n\t\t:precondition (fulfiled goal_condition)\n\t\t:subtasks ()\n\t)\n")


# ---------------------------------------------------------------------------
# Task 7: Problem file generation
# ---------------------------------------------------------------------------

def write_problem_file(min_var: int, max_var: int) -> str:
    """Return HDDL problem file content as a string."""
    domain_name = replace_special_characters(data["name"])
    lines = []
    lines.append(f"(define (problem {domain_name})")
    lines.append(f"\t(:domain {domain_name})")
    lines.append("\t(:objects)")  # all objects declared as constants in domain

    # HTN initial task network
    lines.append("\t(:htn")
    lines.append("\t\t:parameters ()")
    lines.append("\t\t:subtasks (and (task0 (solve)))")
    lines.append("\t)")

    # Initial state
    lines.append("\t(:init")
    for a in data["automata"]:
        for loc in a["initial-locations"]:
            lines.append(f"\t\t(at {loc}_{a['name']})")
        if a.get("restrict-initial") and a["restrict-initial"]["exp"] is not True:
            ri_lines = []
            run_tree(a["restrict-initial"]["exp"], ri_lines, a["name"])
            lines.extend(ri_lines)
        for v in a.get("variables", []):
            if isinstance(v["type"], dict) and "initial-value" in v:
                iv = v["initial-value"]
                val = parse_arith(iv) if isinstance(iv, dict) else iv
                lines.append(f"\t\t(value {v['name']}_{a['name']} n{val})")

    for v in data.get("variables", []):
        if isinstance(v["type"], dict) and "initial-value" in v:
            iv = v["initial-value"]
            val = parse_arith(iv) if isinstance(iv, dict) else iv
            lines.append(f"\t\t(value {v['name']} n{val})")
        elif v["type"] == "bool" and v.get("initial-value") is True:
            lines.append(f"\t\t(fulfiled {v['name']})")

    for c in data.get("constants", []):
        if "value" in c:
            if isinstance(c["type"], dict):
                val = parse_arith(c["value"]) if isinstance(c["value"], dict) else c["value"]
                lines.append(f"\t\t(value {c['name']} n{val})")
            elif c["type"] == "bool" and c["value"] is True:
                lines.append(f"\t\t(fulfiled {c['name']})")

    if data.get("restrict-initial") and data["restrict-initial"]["exp"] is not True:
        ri_lines = []
        run_tree(data["restrict-initial"]["exp"], ri_lines)
        lines.extend(ri_lines)

    # Arithmetic facts
    if min_var <= max_var:
        for n1 in range(min_var, max_var + 1):
            for n2 in range(min_var, max_var + 1):
                if Options.SUM and n1 + n2 <= max_var:
                    lines.append(f"\t\t(add n{n1} n{n2} n{n1+n2})")
                if Options.SUBTRACTION and n1 - n2 >= min_var:
                    lines.append(f"\t\t(sub n{n1} n{n2} n{n1-n2})")
                if Options.MULTIPLICATION and n1 * n2 <= max_var:
                    lines.append(f"\t\t(mult n{n1} n{n2} n{n1*n2})")
                if Options.DIVISION and n2 != 0 and n1 % n2 >= min_var:
                    lines.append(f"\t\t(mod n{n1} n{n2} n{n1%n2})")
                if Options.MAX:
                    lines.append(f"\t\t(max n{n1} n{n2} n{max(n1,n2)})")
                if Options.MIN:
                    lines.append(f"\t\t(min n{n1} n{n2} n{min(n1,n2)})")
        for n1 in range(min_var, max_var + 1):
            if Options.EQUAL:
                lines.append(f"\t\t(equal n{n1} n{n1})")
            for n2 in range(n1 + 1, max_var + 1):
                if Options.LESS:       lines.append(f"\t\t(less n{n1} n{n2})")
                if Options.LESS_EQUAL: lines.append(f"\t\t(leq n{n1} n{n2})")
            if Options.LESS_EQUAL:     lines.append(f"\t\t(leq n{n1} n{n1})")
        for n1 in range(max_var, min_var - 1, -1):
            if Options.GREATER_EQUAL:  lines.append(f"\t\t(geq n{n1} n{n1})")
            for n2 in range(min_var, n1):
                if Options.GREATER:       lines.append(f"\t\t(greater n{n1} n{n2})")
                if Options.GREATER_EQUAL: lines.append(f"\t\t(geq n{n1} n{n2})")

    lines.append("\t)")
    lines.append(")")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Task 8: main() entrypoint
# ---------------------------------------------------------------------------

def main():
    global data, bool_vars, var_dict, loc_var_dict, loc_vars, \
           num_dummy_vars, helper_variables, prec_num

    arg_parser = argparse.ArgumentParser(description=__doc__)
    arg_parser.add_argument("jani", help="JANI input file")
    arg_parser.add_argument("--config", "-c", default=None, help="Options config file")
    arg_parser.add_argument("--out-dir", default=None,
                            help="Output directory (default: same as input)")
    args = arg_parser.parse_args()

    if args.config:
        Options.load(args.config)

    with open(args.jani, "rb") as f:
        data = json.load(f)

    # Reset global state
    bool_vars.clear()
    var_dict.clear()
    loc_var_dict.clear()
    helper_variables.clear()

    n_auto = len(data["automata"])
    if n_auto > 1 and not no_syncs():
        print(f"WARNING: {args.jani} has {n_auto} automata with synchronisation — skipping.", file=sys.stderr)
        sys.exit(1)

    if n_auto > 1:
        print(f"INFO: {n_auto} automata without synchronisation — treating as independent interleaving.")

    loc_vars[:] = [set() for _ in data["automata"]]
    for i, a in enumerate(data["automata"]):
        for v in a.get("variables", []):
            loc_vars[i].add(v["name"])

    # Determine output paths
    base = os.path.splitext(args.jani)[0]
    if args.out_dir:
        os.makedirs(args.out_dir, exist_ok=True)
        base_name = os.path.basename(base)
        base = os.path.join(args.out_dir, base_name)

    domain_path = base + "-domain.hddl"
    problem_path = base + "-problem.hddl"

    # Build domain content
    domain_lines = []
    methods = []  # collected separately, inserted after task declaration
    min_var, max_var = write_domain_header(domain_lines)
    write_htn_task(domain_lines)
    write_actions_and_methods(domain_lines, methods)
    write_goal_actions_and_method(domain_lines, methods)
    # Insert methods after (:task solve :parameters ()) line
    insert_idx = next(
        (i for i, ln in enumerate(domain_lines) if "(:task solve" in ln), len(domain_lines)
    ) + 1
    for m_line in reversed(methods):
        domain_lines.insert(insert_idx, m_line)
    domain_lines.append(")")

    with open(domain_path, "w") as f:
        f.write("\n".join(domain_lines) + "\n")
    print(f"Written: {domain_path}")

    # Build problem content
    problem_content = write_problem_file(min_var, max_var)
    with open(problem_path, "w") as f:
        f.write(problem_content + "\n")
    print(f"Written: {problem_path}")


if __name__ == "__main__":
    main()
