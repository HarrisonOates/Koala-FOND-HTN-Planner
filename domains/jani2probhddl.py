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
