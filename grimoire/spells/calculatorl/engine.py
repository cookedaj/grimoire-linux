# SPDX-License-Identifier: GPL-3.0-or-later
"""CalculatorL's math (no Qt): a recursive-descent parser, never eval(), the same grammar as LaunchL's search
calculator (contents/ui/calc.js) plus functions, constants, factorial, percent and `ans`.

    expr   := term (("+" | "-") term)*
    term   := unary (("*" | "/" | "×" | "÷" | "mod") unary | implicit power)*
    unary  := ("-" | "+") unary | "√" unary | power  so -2^2 = -4, as written on paper
    power  := postfix ("^" unary)?                  right-associative: 2^3^2 = 2^9, 2^-3 = 1/8
    postfix:= atom ("!" | "%")*
    atom   := number | constant | ans | name "(" args ")" | "(" expr ")" | "√" unary

Results are floats shown with up to 12 significant digits, so 0.1 + 0.2 reads 0.3. Angles follow `degrees`.
"""
import math
import re

MAX_LEN = 1000
MAX_FACT = 170                                        # 171! overflows a float


class CalcError(ValueError):
    pass


_TOKEN = re.compile(r"\s*(?:(\d+(?:[.,]\d*)?(?:[eE][+-]?\d+)?|[.,]\d+(?:[eE][+-]?\d+)?)|([A-Za-zπτ_][\w]*)|"
                    r"(\*\*|[-+*/×÷^()!%√,]))")
CONSTANTS = {"pi": math.pi, "π": math.pi, "e": math.e, "tau": math.tau, "τ": math.tau, "phi": (1 + 5 ** 0.5) / 2}


def _trig(fn, degrees):
    return (lambda x: fn(math.radians(x))) if degrees else fn


def _atrig(fn, degrees):
    return (lambda x: math.degrees(fn(x))) if degrees else fn


def functions(degrees: bool) -> dict:
    return {"sin": _trig(math.sin, degrees), "cos": _trig(math.cos, degrees), "tan": _trig(math.tan, degrees),
            "asin": _atrig(math.asin, degrees), "acos": _atrig(math.acos, degrees),
            "atan": _atrig(math.atan, degrees),
            "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
            "sqrt": math.sqrt, "cbrt": lambda x: math.copysign(abs(x) ** (1 / 3), x), "abs": abs,
            "ln": math.log, "log": math.log10, "log2": math.log2, "exp": math.exp,
            "floor": math.floor, "ceil": math.ceil, "round": round, "fact": _fact}


def _fact(x):
    if x != int(x) or x < 0:
        return math.gamma(x + 1)
    if x > MAX_FACT:
        raise CalcError("too big")
    return float(math.factorial(int(x)))


def tokens(text: str) -> list[tuple[str, str]]:
    out, i = [], 0
    text = text.strip()
    while i < len(text):
        m = _TOKEN.match(text, i)
        if not m or m.end() == i:
            raise CalcError(f"unexpected '{text[i]}'")
        num, name, op = m.groups()
        if num is not None:
            out.append(("num", num.replace(",", ".")))
        elif name is not None:
            out.append(("name", name))
        else:
            out.append(("op", "^" if op == "**" else op))
        i = m.end()
    return out


class _Parser:
    def __init__(self, toks, degrees, ans):
        self.t, self.i, self.fns, self.ans = toks, 0, functions(degrees), ans

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else (None, None)

    def take(self, value=None):
        kind, v = self.peek()
        if kind is None or (value is not None and v != value):
            raise CalcError(f"expected '{value}'" if value else "unexpected end")
        self.i += 1
        return kind, v

    def expr(self):
        x = self.term()
        while self.peek()[1] in ("+", "-"):
            op = self.take()[1]
            y = self.term()
            x = x + y if op == "+" else x - y
        return x

    def term(self):
        x = self.unary()
        while True:
            kind, v = self.peek()
            if v in ("*", "/", "×", "÷") or (kind == "name" and v == "mod"):
                self.take()
                y = self.unary()
                if v in ("/", "÷", "mod") and y == 0:
                    raise CalcError("division by zero")
                x = x * y if v in ("*", "×") else math.fmod(x, y) if v == "mod" else x / y
            elif kind == "num" or kind == "name" or v in ("(", "√"):     # 2π, 3(4+1), 2 sqrt(9)
                x = x * self.power()
            else:
                return x

    def power(self):
        x = self.postfix()
        if self.peek()[1] == "^":
            self.take()
            y = self.unary()
            try:
                x = math.pow(x, y)
            except (OverflowError, ValueError) as e:
                raise CalcError("out of range") from e
        return x

    def unary(self):
        if self.peek()[1] in ("-", "+"):
            sign = -1 if self.take()[1] == "-" else 1
            return sign * self.unary()
        if self.peek()[1] == "√":
            self.take()
            x = self.unary()
            if x < 0:
                raise CalcError("square root of a negative number")
            return math.sqrt(x)
        return self.power()

    def postfix(self):
        x = self.atom()
        while self.peek()[1] in ("!", "%"):
            op = self.take()[1]
            x = _fact(x) if op == "!" else x / 100
        return x

    def atom(self):
        kind, v = self.take()
        if kind == "num":
            return float(v)
        if v == "(":
            x = self.expr()
            self.take(")")
            return x
        if kind == "name":
            low = v.lower() if v not in ("π", "τ") else v
            if low in self.fns:
                self.take("(")
                x = self.expr()
                self.take(")")
                try:
                    return float(self.fns[low](x))
                except (ValueError, OverflowError) as e:
                    raise CalcError(f"{low}: out of range") from e
            if low in CONSTANTS:
                return CONSTANTS[low]
            if low == "ans":
                return self.ans
            raise CalcError(f"unknown '{v}'")
        raise CalcError(f"unexpected '{v}'")


def evaluate(text: str, degrees: bool = False, ans: float = 0.0) -> float:
    """The value of an expression, or CalcError with a short reason."""
    if not text.strip():
        raise CalcError("empty")
    if len(text) > MAX_LEN:
        raise CalcError("too long")
    toks = tokens(text)
    depth = 0
    for kind, v in toks:                               # unclosed brackets close at the end, like a phone calculator
        depth += (v == "(") - (v == ")")
    toks += [("op", ")")] * max(0, depth)
    p = _Parser(toks, degrees, ans)
    try:
        x = p.expr()
    except RecursionError as e:
        raise CalcError("too deeply nested") from e
    if p.i != len(toks):
        raise CalcError(f"unexpected '{toks[p.i][1]}'")
    if math.isnan(x) or math.isinf(x):
        raise CalcError("not a number" if math.isnan(x) else "infinite")
    return x


def fmt(x: float, digits: int = 12) -> str:
    """12 significant digits, no trailing zeros, exponent only for very large or small numbers."""
    if x == 0:
        return "0"
    if abs(x) >= 1e15 or abs(x) < 1e-9:
        return f"{x:.{digits}g}".replace("e+", "e")
    s = f"{x:.{digits}g}"
    if "e" in s:
        s = f"{x:.{max(0, digits - 1 - int(math.floor(math.log10(abs(x)))))}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s
