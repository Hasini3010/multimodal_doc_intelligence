import pytest

from tools.calc import CalcError, evaluate_expression


def test_basic_arithmetic():
    out = evaluate_expression("delta", "q4 - q2", {"q4": 89.2, "q2": 84.0})
    assert out.result == pytest.approx(5.2)


def test_round():
    out = evaluate_expression("pct", "round(a * 100, 2)", {"a": 0.891})
    assert out.result == 89.1


def test_rejects_unknown_var():
    with pytest.raises(CalcError):
        evaluate_expression("x", "a + b", {"a": 1})
