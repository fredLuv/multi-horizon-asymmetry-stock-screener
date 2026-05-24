from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from math import log, sqrt
from statistics import mean

from .models import Bar


class FormulaParseError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class _NumberNode:
    value: float


@dataclass(frozen=True, slots=True)
class _VarNode:
    name: str


@dataclass(frozen=True, slots=True)
class _CallNode:
    func: str
    args: tuple[_AstNode, ...]


_AstNode = _NumberNode | _VarNode | _CallNode


class FactorDslEngine:
    def evaluate(self, expression: str, bars: list[Bar]) -> list[float | None]:
        if not bars:
            return []
        parser = _Parser(expression)
        ast = parser.parse()
        return self._eval(ast, bars)

    def _eval(self, node: _AstNode, bars: list[Bar]) -> list[float | None]:
        if isinstance(node, _NumberNode):
            return [node.value for _ in bars]
        if isinstance(node, _VarNode):
            return _field_series(node.name, bars)
        return self._eval_call(node, bars)

    def _eval_call(self, node: _CallNode, bars: list[Bar]) -> list[float | None]:
        fn = node.func.lower()
        args = [self._eval(arg, bars) for arg in node.args]

        if fn in {"add", "sub", "mul", "div"}:
            if len(args) != 2:
                raise FormulaParseError(f"{node.func} expects 2 arguments")
            return _binary(args[0], args[1], fn)
        if fn == "log":
            return _unary(args, node.func, lambda x: log(x) if x > 0 else None)
        if fn == "abs":
            return _unary(args, node.func, abs)
        if fn == "sign":
            return _unary(args, node.func, lambda x: 1.0 if x > 0 else (-1.0 if x < 0 else 0.0))

        if fn in {"mean", "std", "var", "sum", "max", "min", "rank"}:
            if len(args) != 2:
                raise FormulaParseError(f"{node.func} expects 2 arguments")
            window = _as_window(args[1], node.func)
            return _rolling(args[0], window, fn)

        if fn in {"ref", "delta"}:
            if len(args) != 2:
                raise FormulaParseError(f"{node.func} expects 2 arguments")
            lag = _as_window(args[1], node.func)
            if fn == "ref":
                return _ref(args[0], lag)
            return _binary(args[0], _ref(args[0], lag), "sub")

        if fn == "corr":
            if len(args) != 3:
                raise FormulaParseError("Corr expects 3 arguments")
            window = _as_window(args[2], node.func)
            return _rolling_corr(args[0], args[1], window)

        if fn in {"gt", "lt", "ge", "le", "eq", "ne"}:
            if len(args) != 2:
                raise FormulaParseError(f"{node.func} expects 2 arguments")
            return _compare(args[0], args[1], fn)

        if fn == "if":
            if len(args) != 3:
                raise FormulaParseError("If expects 3 arguments")
            return _if_expr(args[0], args[1], args[2])

        raise FormulaParseError(f"Unsupported function: {node.func}")


def _field_series(name: str, bars: list[Bar]) -> list[float | None]:
    out: list[float | None] = []
    for bar in bars:
        close = bar.close
        if name == "$close":
            out.append(close)
        elif name == "$open":
            out.append(bar.open if bar.open is not None else close)
        elif name == "$high":
            out.append(bar.high if bar.high is not None else close)
        elif name == "$low":
            out.append(bar.low if bar.low is not None else close)
        elif name == "$volume":
            out.append(bar.volume if bar.volume is not None else 0.0)
        elif name == "$vwap":
            out.append(bar.vwap if bar.vwap is not None else close)
        elif name == "$amount":
            if bar.amount is not None:
                out.append(bar.amount)
            else:
                volume = bar.volume if bar.volume is not None else 0.0
                out.append(close * volume)
        else:
            raise FormulaParseError(f"Unknown field: {name}")
    return out


def _binary(
    left: list[float | None], right: list[float | None], op: str
) -> list[float | None]:
    out: list[float | None] = []
    for a, b in zip(left, right):
        if a is None or b is None:
            out.append(None)
            continue
        if op == "add":
            out.append(a + b)
        elif op == "sub":
            out.append(a - b)
        elif op == "mul":
            out.append(a * b)
        else:
            if abs(b) < 1e-12:
                out.append(None)
            else:
                out.append(a / b)
    return out


def _unary(
    args: list[list[float | None]], name: str, fn: Callable[[float], float | None]
) -> list[float | None]:
    if len(args) != 1:
        raise FormulaParseError(f"{name} expects 1 argument")
    out: list[float | None] = []
    for value in args[0]:
        if value is None:
            out.append(None)
            continue
        result = fn(value)
        if result is None:
            out.append(None)
        else:
            out.append(float(result))
    return out


def _rolling(series: list[float | None], window: int, op: str) -> list[float | None]:
    out: list[float | None] = [None] * len(series)
    if window <= 0:
        return out
    for i in range(len(series)):
        if i + 1 < window:
            continue
        bucket = [v for v in series[i - window + 1 : i + 1] if v is not None]
        if len(bucket) < window:
            continue
        if op == "mean":
            out[i] = mean(bucket)
        elif op == "sum":
            out[i] = sum(bucket)
        elif op == "max":
            out[i] = max(bucket)
        elif op == "min":
            out[i] = min(bucket)
        elif op == "std":
            out[i] = _std(bucket)
        elif op == "var":
            s = _std(bucket)
            out[i] = s * s
        elif op == "rank":
            out[i] = _rank(bucket)
    return out


def _rolling_corr(
    left: list[float | None], right: list[float | None], window: int
) -> list[float | None]:
    out: list[float | None] = [None] * len(left)
    if window <= 1:
        return out
    for i in range(len(left)):
        if i + 1 < window:
            continue
        lx = left[i - window + 1 : i + 1]
        rx = right[i - window + 1 : i + 1]
        x: list[float] = []
        y: list[float] = []
        for a, b in zip(lx, rx):
            if a is None or b is None:
                continue
            x.append(a)
            y.append(b)
        if len(x) < window:
            continue
        out[i] = _pearson(x, y)
    return out


def _ref(series: list[float | None], lag: int) -> list[float | None]:
    out: list[float | None] = [None] * len(series)
    for i in range(lag, len(series)):
        out[i] = series[i - lag]
    return out


def _compare(
    left: list[float | None], right: list[float | None], op: str
) -> list[float | None]:
    out: list[float | None] = []
    for a, b in zip(left, right):
        if a is None or b is None:
            out.append(None)
            continue
        if op == "gt":
            out.append(1.0 if a > b else 0.0)
        elif op == "lt":
            out.append(1.0 if a < b else 0.0)
        elif op == "ge":
            out.append(1.0 if a >= b else 0.0)
        elif op == "le":
            out.append(1.0 if a <= b else 0.0)
        elif op == "eq":
            out.append(1.0 if a == b else 0.0)
        else:
            out.append(1.0 if a != b else 0.0)
    return out


def _if_expr(
    cond: list[float | None], when_true: list[float | None], when_false: list[float | None]
) -> list[float | None]:
    out: list[float | None] = []
    for c, t, f in zip(cond, when_true, when_false):
        if c is None:
            out.append(None)
            continue
        out.append(t if c > 0 else f)
    return out


def _as_window(series: list[float | None], name: str) -> int:
    for value in series:
        if value is not None:
            window = int(round(value))
            if window > 0:
                return window
            break
    raise FormulaParseError(f"{name} requires a positive integer window")


def _std(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    mu = mean(values)
    var = sum((x - mu) ** 2 for x in values) / (len(values) - 1)
    if var <= 0:
        return 0.0
    return sqrt(var)


def _rank(values: list[float]) -> float:
    current = values[-1]
    sorted_vals = sorted(values)
    rank = sorted_vals.index(current) + 1
    return rank / len(values)


def _pearson(x: list[float], y: list[float]) -> float:
    if len(x) != len(y) or len(x) < 2:
        return 0.0
    mx = mean(x)
    my = mean(y)
    cov = sum((a - mx) * (b - my) for a, b in zip(x, y))
    vx = sum((a - mx) ** 2 for a in x)
    vy = sum((b - my) ** 2 for b in y)
    if vx <= 1e-12 or vy <= 1e-12:
        return 0.0
    return cov / sqrt(vx * vy)


class _Parser:
    def __init__(self, text: str) -> None:
        self._text = text.strip()
        self._idx = 0

    def parse(self) -> _AstNode:
        node = self._parse_expr()
        self._skip_ws()
        if self._idx != len(self._text):
            raise FormulaParseError(f"Unexpected token near: {self._text[self._idx:]}")
        return node

    def _parse_expr(self) -> _AstNode:
        self._skip_ws()
        if self._idx >= len(self._text):
            raise FormulaParseError("Unexpected end of expression")
        ch = self._text[self._idx]
        if ch == "$":
            return self._parse_var()
        if ch.isdigit() or ch in {"-", "."}:
            return self._parse_number()
        if ch.isalpha() or ch == "_":
            return self._parse_call()
        raise FormulaParseError(f"Unexpected character: {ch}")

    def _parse_var(self) -> _VarNode:
        start = self._idx
        self._idx += 1
        while self._idx < len(self._text) and (
            self._text[self._idx].isalnum() or self._text[self._idx] == "_"
        ):
            self._idx += 1
        return _VarNode(self._text[start : self._idx])

    def _parse_number(self) -> _NumberNode:
        start = self._idx
        if self._text[self._idx] == "-":
            self._idx += 1
        has_dot = False
        while self._idx < len(self._text):
            ch = self._text[self._idx]
            if ch.isdigit():
                self._idx += 1
                continue
            if ch == "." and not has_dot:
                has_dot = True
                self._idx += 1
                continue
            break
        raw = self._text[start : self._idx]
        try:
            value = float(raw)
        except ValueError as exc:
            raise FormulaParseError(f"Invalid number: {raw}") from exc
        return _NumberNode(value)

    def _parse_call(self) -> _CallNode:
        start = self._idx
        while self._idx < len(self._text) and (
            self._text[self._idx].isalnum() or self._text[self._idx] == "_"
        ):
            self._idx += 1
        name = self._text[start : self._idx]
        self._skip_ws()
        if self._idx >= len(self._text) or self._text[self._idx] != "(":
            raise FormulaParseError(f"Expected '(' after function name: {name}")
        self._idx += 1
        args: list[_AstNode] = []
        while True:
            self._skip_ws()
            if self._idx < len(self._text) and self._text[self._idx] == ")":
                self._idx += 1
                break
            args.append(self._parse_expr())
            self._skip_ws()
            if self._idx < len(self._text) and self._text[self._idx] == ",":
                self._idx += 1
                continue
            if self._idx < len(self._text) and self._text[self._idx] == ")":
                self._idx += 1
                break
            raise FormulaParseError("Expected ',' or ')' in argument list")
        return _CallNode(func=name, args=tuple(args))

    def _skip_ws(self) -> None:
        while self._idx < len(self._text) and self._text[self._idx].isspace():
            self._idx += 1
