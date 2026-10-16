/*
    LaunchL's calculator: a small recursive-descent parser for what people type in a search field
    (12*7+3, 2^10, sqrt(2), 15% of 80, 80 + 15%, (3+4)/2, 5!, 2pi). No eval() or Function(): the text only
    ever becomes numbers through this grammar, so nothing typed can run as code.

        expr    := term (("+" | "-") term)*            a ± b%  →  a ± a·b/100
        term    := unary (("*" | "/" | "mod" | "of" | implicit) unary)*
        unary   := ("-" | "+") unary | power
        power   := postfix ("^" unary)?                right-associative, -2^2 = -4
        postfix := primary ("!" | "%")*
        primary := number | constant | function primary | "(" expr ")"

    SPDX-FileCopyrightText: 2026 cookedaj
    SPDX-License-Identifier: GPL-3.0-or-later
*/
.pragma library

const FUNCS = {
    sqrt: Math.sqrt, cbrt: Math.cbrt, abs: Math.abs, exp: Math.exp,
    ln: Math.log, log: Math.log10, log10: Math.log10, log2: Math.log2,
    sin: Math.sin, cos: Math.cos, tan: Math.tan, asin: Math.asin, acos: Math.acos, atan: Math.atan,
    sinh: Math.sinh, cosh: Math.cosh, tanh: Math.tanh,
    round: Math.round, floor: Math.floor, ceil: Math.ceil,
}
const CONSTS = { pi: Math.PI, "π": Math.PI, e: Math.E, tau: 2 * Math.PI, "τ": 2 * Math.PI }
const WORDS = { mod: "mod", of: "of" }
const MAX_LENGTH = 200

// Text → tokens ({t: "num", v} | {t: "op", v} | {t: "id", v}); throws on anything else.
// decimal: the locale's decimal point. With ",", both "," and "." are decimal points; with ".", a "," between
// digit groups of three is a thousands separator (1,000,000).
function tokens(text, decimal) {
    const out = []
    let i = 0
    while (i < text.length) {
        const c = text[i]
        if (/\s/.test(c)) {
            i++
        } else if (/[0-9.,]/.test(c) && !(c === "," && decimal !== ",")) {
            let j = i, digits = ""
            let seenPoint = false, seenExp = false
            while (j < text.length) {
                const d = text[j]
                if (/[0-9]/.test(d)) {
                    digits += d
                } else if ((d === "." || (d === "," && decimal === ",")) && !seenPoint && !seenExp) {
                    seenPoint = true
                    digits += "."
                } else if (d === "," && decimal !== "," && !seenPoint && /^[0-9]{3}(?![0-9])/.test(text.slice(j + 1))
                           && digits !== "") {
                    // grouping comma: skip it
                } else if ((d === "e" || d === "E") && !seenExp && digits !== "" && /^[+-]?[0-9]/.test(text.slice(j + 1))) {
                    seenExp = true
                    digits += "e"
                    if (text[j + 1] === "+" || text[j + 1] === "-") {
                        digits += text[++j]
                    }
                } else {
                    break
                }
                j++
            }
            if (digits === "." || digits === "") {
                throw new Error("bad number")
            }
            out.push({ t: "num", v: parseFloat(digits) })
            i = j
        } else if ("+-*/^()!%×÷·−–".includes(c)) {
            const map = { "×": "*", "·": "*", "÷": "/", "−": "-", "–": "-" }
            if (c === "*" && text[i + 1] === "*") {          // 2**10
                out.push({ t: "op", v: "^" })
                i += 2
            } else {
                out.push({ t: "op", v: map[c] || c })
                i++
            }
        } else if (/[A-Za-zπτ]/.test(c)) {
            let j = i
            while (j < text.length && /[A-Za-z0-9πτ]/.test(text[j])) {
                j++
            }
            const word = text.slice(i, j).toLowerCase()
            if (!(word in FUNCS) && !(word in CONSTS) && !(word in WORDS)) {
                throw new Error("unknown word")
            }
            out.push({ t: "id", v: word })
            i = j
        } else {
            throw new Error("bad character")
        }
    }
    return out
}

// Parses and evaluates; returns {value, ops} where ops counts the operations (0 for a bare number)
function evaluate(text, decimal) {
    const toks = tokens(text, decimal)
    let pos = 0
    let ops = 0
    const peek = () => toks[pos]
    const isOp = (v) => peek() && peek().t === "op" && peek().v === v
    const isWord = (v) => peek() && peek().t === "id" && peek().v === v

    function expr() {
        let left = term()
        while (isOp("+") || isOp("-")) {
            const op = toks[pos++].v
            const right = term()
            ops++
            const r = right.pct ? left.v * right.v : right.v          // 80 + 15% = 80 + 12
            left = { v: op === "+" ? left.v + r : left.v - r, pct: false }
        }
        return left
    }

    // implicit multiplication: 2pi, 3(4+1), 2 sqrt(2); never two numbers in a row ("12 7", "1.5.5")
    function startsImplicit() {
        const p = peek()
        return p && ((p.t === "op" && p.v === "(") || (p.t === "id" && !(p.v in WORDS)))
    }

    function term() {
        let left = unary()
        for (;;) {
            if (isOp("*") || isOp("/") || isWord("mod") || isWord("of")) {
                const op = toks[pos++].v
                const right = unary()
                ops++
                if (op === "*") {
                    left = { v: left.v * right.v, pct: false }
                } else if (op === "/") {
                    left = { v: left.v / right.v, pct: false }
                } else if (op === "mod") {
                    left = { v: ((left.v % right.v) + right.v) % right.v, pct: false }
                } else {                                               // "15% of 80"
                    if (!left.pct) {
                        throw new Error("of needs a percentage")
                    }
                    left = { v: left.v * right.v, pct: false }
                }
            } else if (startsImplicit()) {
                const right = unary()
                ops++
                left = { v: left.v * right.v, pct: false }
            } else {
                return left
            }
        }
    }

    function unary() {
        if (isOp("-") || isOp("+")) {
            const op = toks[pos++].v
            const inner = unary()
            return { v: op === "-" ? -inner.v : inner.v, pct: inner.pct }
        }
        return power()
    }

    function power() {
        const base = postfix()
        if (isOp("^")) {
            pos++
            const exp = unary()
            ops++
            return { v: Math.pow(base.v, exp.v), pct: false }
        }
        return base
    }

    function postfix() {
        let x = primary()
        for (;;) {
            if (isOp("!")) {
                pos++
                ops++
                if (x.v < 0 || x.v > 170 || !Number.isInteger(x.v)) {
                    throw new Error("factorial")
                }
                let f = 1
                for (let k = 2; k <= x.v; k++) {
                    f *= k
                }
                x = { v: f, pct: false }
            } else if (isOp("%")) {
                pos++
                ops++
                x = { v: x.v / 100, pct: true }
            } else {
                return x
            }
        }
    }

    function primary() {
        const p = toks[pos++]
        if (!p) {
            throw new Error("unexpected end")
        }
        if (p.t === "num") {
            return { v: p.v, pct: false }
        }
        if (p.t === "op" && p.v === "(") {
            const inner = expr()
            if (isOp(")")) {
                pos++
            } else if (pos < toks.length) {                         // a missing ")" at the very end is fine
                throw new Error("missing )")
            }
            return { v: inner.v, pct: inner.pct }
        }
        if (p.t === "id" && p.v in CONSTS) {
            // a constant alone isn't a sum: "e" or "pi" typed to find an app shows no result (2pi does)
            return { v: CONSTS[p.v], pct: false }
        }
        if (p.t === "id" && p.v in FUNCS) {
            const arg = power()                                     // sqrt(2), sqrt 2, sin pi/2 = sin(pi)/2
            ops++
            return { v: FUNCS[p.v](arg.v), pct: false }
        }
        throw new Error("unexpected token")
    }

    const result = expr()
    if (pos < toks.length) {
        throw new Error("trailing input")
    }
    return { value: result.v, ops: ops }
}

// A number as people write it: up to 12 significant digits, no trailing zeros, the locale's decimal point
function format(value, decimal) {
    if (Object.is(value, -0)) {
        value = 0
    }
    let s
    if (Number.isInteger(value) && Math.abs(value) < 1e15) {
        s = String(value)
    } else {
        s = String(parseFloat(value.toPrecision(12)))
    }
    return decimal === "," ? s.replace(".", ",") : s
}

// The result of a search text, or "" when it isn't a sum (plain numbers, words, unit conversions, errors).
// A leading "=" forces it (=42 shows 42).
function calculate(text, decimal) {
    let q = String(text).trim()
    let forced = false
    if (q.startsWith("=")) {
        q = q.slice(1).trim()
        forced = true
    }
    if (q === "" || q.length > MAX_LENGTH || !/[0-9πτ]|\b(pi|e|tau)\b/i.test(q)) {
        return ""
    }
    try {
        const r = evaluate(q, decimal)
        if ((r.ops < 1 && !forced) || !isFinite(r.value)) {
            return ""
        }
        return format(r.value, decimal)
    } catch (err) {
        return ""
    }
}

// The number a KRunner row shows ("87", "= 87", "1,5"), or NaN when the row isn't just a number
function numberIn(text, decimal) {
    let s = String(text || "").trim().replace(/^=\s*/, "").replace(/[\s  ']/g, "")
    if (decimal === ",") {
        s = s.replace(/\./g, "").replace(",", ".")
    } else {
        s = s.replace(/,/g, "")
    }
    return /^[-+]?(\d+\.?\d*|\.\d+)(e[-+]?\d+)?$/i.test(s) ? parseFloat(s) : NaN
}

// Whether a KRunner row shows the same number as our result (KRunner's calculator rounds differently)
function sameNumber(text, value, decimal) {
    const n = numberIn(text, decimal)
    if (isNaN(n) || isNaN(value)) {
        return false
    }
    return n === value || Math.abs(n - value) <= 1e-9 * Math.max(1, Math.abs(value))
}
