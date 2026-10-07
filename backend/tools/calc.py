"""Safe arithmetic evaluator — LLM must not do math directly."""

from __future__ import annotations

import ast
import math
from dataclasses import dataclass
from typing import Any


class CalcError(ValueError):
    pass


_ALLOWED_BINOPS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.Mod: lambda a, b: a % b,
    ast.Pow: lambda a, b: a**b,
}

_ALLOWED_UNARY = {
    ast.UAdd: lambda a: a,
    ast.USub: lambda a: -a,
}


def _num(x: Any) -> float:
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        s = x.strip().replace("%", "")
        return float(s)
    raise CalcError(f"Not a number: {x!r}")


def _eval_node(node: ast.AST, env: dict[str, float]) -> float:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, env)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.Name):
        if node.id not in env:
            raise CalcError(f"Unknown variable: {node.id}")
        return env[node.id]
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARY:
        return _ALLOWED_UNARY[type(node.op)](_eval_node(node.operand, env))
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
        return _ALLOWED_BINOPS[type(node.op)](
            _eval_node(node.left, env), _eval_node(node.right, env)
        )
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id == "round":
            args = [_eval_node(a, env) for a in node.args]
            if len(args) == 1:
                return float(round(args[0]))
            if len(args) == 2:
                return float(round(args[0], int(args[1])))
        raise CalcError("Only round() calls allowed")
    raise CalcError(f"Unsupported expression: {ast.dump(node)}")


@dataclass
class CalculationOutput:
    name: str
    formula: str
    inputs: dict[str, Any]
    result: float | int


def evaluate_expression(name: str, formula: str, inputs: dict[str, Any]) -> CalculationOutput:
    env = {k: _num(v) for k, v in inputs.items()}
    tree = ast.parse(formula, mode="eval")
    result = _eval_node(tree, env)
    if abs(result - round(result)) < 1e-9:
        result = int(round(result))
    else:
        result = round(float(result), 6)
    return CalculationOutput(name=name, formula=formula, inputs=inputs, result=result)
