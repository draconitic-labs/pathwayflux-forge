"""Deterministic rate-law evaluations for pathway ODEs."""

from __future__ import annotations

import ast
import math
from typing import Callable

from app.models.schema import (
    Inhibitor,
    PathwayProject,
    RateLawType,
    RateParameters,
    Reaction,
)


def _safe(x: float) -> float:
    if not math.isfinite(x):
        return 0.0
    return max(x, 0.0)


def substrate_product_conc(
    reaction: Reaction,
    conc: dict[str, float],
) -> tuple[list[float], list[float], list[float], list[float]]:
    """Return substrate concs, substrate stoichs, product concs, product stoichs."""
    s_c, s_n, p_c, p_n = [], [], [], []
    for s in reaction.substrates:
        s_c.append(_safe(conc.get(s.metabolite_id, 0.0)))
        s_n.append(abs(s.stoichiometry) if s.stoichiometry != 0 else 1.0)
    for p in reaction.products:
        p_c.append(_safe(conc.get(p.metabolite_id, 0.0)))
        p_n.append(abs(p.stoichiometry) if p.stoichiometry != 0 else 1.0)
    return s_c, s_n, p_c, p_n


def mass_action_rate(
    reaction: Reaction,
    conc: dict[str, float],
    params: RateParameters,
) -> float:
    s_c, s_n, p_c, p_n = substrate_product_conc(reaction, conc)
    forward = params.kf
    for c, n in zip(s_c, s_n):
        forward *= c**n
    reverse = 0.0
    if reaction.reversible or params.kr > 0:
        reverse = params.kr
        for c, n in zip(p_c, p_n):
            reverse *= c**n
    return forward - reverse


def michaelis_menten_rate(
    reaction: Reaction,
    conc: dict[str, float],
    params: RateParameters,
    enzyme_amount: float = 1.0,
) -> float:
    s_c, s_n, p_c, p_n = substrate_product_conc(reaction, conc)
    if not s_c:
        return 0.0
    # Multi-substrate: use first substrate for MM; product of others as mass-action factor
    S = s_c[0]
    extra = 1.0
    for c in s_c[1:]:
        extra *= c
    Vmax = params.Vmax * enzyme_amount
    Km = max(params.Km, 1e-15)
    if reaction.reversible and p_c:
        P = p_c[0]
        # Uni-uni reversible MM (Haldane simplified)
        return Vmax * (S / Km - P / max(params.Km_product, 1e-15)) / (
            1.0 + S / Km + P / max(params.Km_product, 1e-15)
        ) * extra
    return Vmax * S / (Km + S) * extra


def competitive_inhibition_rate(
    reaction: Reaction,
    conc: dict[str, float],
    params: RateParameters,
    inhibitor_conc: float,
    enzyme_amount: float = 1.0,
) -> float:
    s_c, _, _, _ = substrate_product_conc(reaction, conc)
    if not s_c:
        return 0.0
    S = s_c[0]
    Vmax = params.Vmax * enzyme_amount
    Km = max(params.Km, 1e-15)
    Ki = max(params.Ki, 1e-15)
    I = max(inhibitor_conc, 0.0)
    return Vmax * S / (Km * (1.0 + I / Ki) + S)


def noncompetitive_inhibition_rate(
    reaction: Reaction,
    conc: dict[str, float],
    params: RateParameters,
    inhibitor_conc: float,
    enzyme_amount: float = 1.0,
) -> float:
    s_c, _, _, _ = substrate_product_conc(reaction, conc)
    if not s_c:
        return 0.0
    S = s_c[0]
    Vmax = params.Vmax * enzyme_amount
    Km = max(params.Km, 1e-15)
    Ki = max(params.Ki, 1e-15)
    I = max(inhibitor_conc, 0.0)
    return (Vmax / (1.0 + I / Ki)) * S / (Km + S)


def uncompetitive_inhibition_rate(
    reaction: Reaction,
    conc: dict[str, float],
    params: RateParameters,
    inhibitor_conc: float,
    enzyme_amount: float = 1.0,
) -> float:
    s_c, _, _, _ = substrate_product_conc(reaction, conc)
    if not s_c:
        return 0.0
    S = s_c[0]
    Vmax = params.Vmax * enzyme_amount
    Km = max(params.Km, 1e-15)
    Ki = max(params.Ki, 1e-15)
    I = max(inhibitor_conc, 0.0)
    return Vmax * S / (Km + S * (1.0 + I / Ki))


def hill_rate(
    reaction: Reaction,
    conc: dict[str, float],
    params: RateParameters,
    enzyme_amount: float = 1.0,
) -> float:
    s_c, _, _, _ = substrate_product_conc(reaction, conc)
    if not s_c:
        return 0.0
    S = s_c[0]
    n = params.n_hill
    K = max(params.K_half, 1e-15)
    Vmax = params.Vmax * enzyme_amount
    Sn = S**n if S > 0 else 0.0
    Kn = K**n
    return Vmax * Sn / (Kn + Sn)


def custom_rate(
    reaction: Reaction,
    conc: dict[str, float],
    params: RateParameters,
    name_to_id: dict[str, str],
    id_to_name: dict[str, str],
) -> float:
    """Evaluate a restricted arithmetic expression with metabolite names and params."""
    expr = (params.custom_expression or "").strip()
    if not expr:
        return mass_action_rate(reaction, conc, params)

    # Build safe namespace: param symbols + metabolite symbols by name
    ns: dict[str, float] = {
        "kf": params.kf,
        "kr": params.kr,
        "Vmax": params.Vmax,
        "Km": params.Km,
        "Km_product": params.Km_product,
        "Ki": params.Ki,
        "n_hill": params.n_hill,
        "K_half": params.K_half,
    }
    for mid, c in conc.items():
        name = id_to_name.get(mid, mid)
        # Allow alphanumeric names only
        safe_name = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in name)
        ns[safe_name] = _safe(c)
        ns[mid] = _safe(c)

    if len(expr) > MAX_EXPRESSION_LENGTH:
        raise ValueError(f"Custom rate expression is longer than {MAX_EXPRESSION_LENGTH} characters")
    try:
        tree = ast.parse(expr, mode="eval")
    except (SyntaxError, RecursionError, MemoryError) as exc:
        raise ValueError(f"Custom rate expression is not valid: {exc}") from exc
    try:
        return float(_eval_node(tree.body, ns))
    except (ArithmeticError, TypeError, RecursionError) as exc:
        raise ValueError(f"Custom rate evaluation failed: {exc}") from exc


MAX_EXPRESSION_LENGTH = 500


_BIN_OPS: dict[type, Callable[[float, float], float]] = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.Pow: lambda a, b: a**b,
}


def _eval_node(node: ast.AST, ns: dict[str, float]) -> float:
    """Evaluate numbers, known names, + - * / ** and unary signs; reject everything else."""
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return float(node.value)
    if isinstance(node, ast.Name):
        if node.id not in ns:
            raise ValueError(f"Unknown symbol in custom rate: {node.id}")
        return ns[node.id]
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        return _BIN_OPS[type(node.op)](_eval_node(node.left, ns), _eval_node(node.right, ns))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _eval_node(node.operand, ns)
        return value if isinstance(node.op, ast.UAdd) else -value
    raise ValueError(f"Disallowed construct in custom rate: {type(node).__name__}")


def resolve_inhibitor_conc(
    project: PathwayProject,
    reaction: Reaction,
    params: RateParameters,
    conc: dict[str, float],
    inhibitor_overrides: dict[str, float] | None = None,
) -> float:
    inhibitor_overrides = inhibitor_overrides or {}
    # Explicit param link
    if params.inhibitor_id:
        for inh in project.inhibitors:
            if inh.id == params.inhibitor_id:
                if inh.id in inhibitor_overrides:
                    return inhibitor_overrides[inh.id]
                if inh.metabolite_id and inh.metabolite_id in conc:
                    return conc[inh.metabolite_id]
                return inh.concentration
    # Any inhibitor targeting this reaction
    total = 0.0
    for inh in project.inhibitors:
        if reaction.id in inh.target_reaction_ids:
            if inh.id in inhibitor_overrides:
                total += inhibitor_overrides[inh.id]
            elif inh.metabolite_id and inh.metabolite_id in conc:
                total += conc[inh.metabolite_id]
            else:
                total += inh.concentration
    if total > 0:
        return total
    # Fall back to params.Ki used with zero free inhibitor unless set via reaction
    return 0.0


def enzyme_amount(
    project: PathwayProject,
    reaction: Reaction,
    params: RateParameters,
    enzyme_scale: dict[str, float] | None = None,
) -> float:
    enzyme_scale = enzyme_scale or {}
    eid = reaction.enzyme_id or params.enzyme_id
    if not eid:
        return 1.0
    for enz in project.enzymes:
        if enz.id == eid:
            conc = enzyme_scale.get(enz.id, enz.concentration)
            # Effective activity ~ concentration * (kcat relative to reference 1)
            kcat = enzyme_scale.get(f"{enz.id}__kcat", enz.kcat)
            return conc * kcat
    return 1.0


RateFn = Callable[[], float]


def make_rate_function(
    project: PathwayProject,
    reaction: Reaction,
    name_to_id: dict[str, str],
    id_to_name: dict[str, str],
    enzyme_scale: dict[str, float] | None = None,
    inhibitor_overrides: dict[str, float] | None = None,
    param_overrides: dict[str, float] | None = None,
) -> Callable[[dict[str, float]], float]:
    """Return flux(reaction) given concentration map."""
    params = reaction.parameters.model_copy(deep=True)
    if param_overrides:
        for k, v in param_overrides.items():
            if hasattr(params, k):
                setattr(params, k, v)

    # Pull Ki from linked inhibitor if present
    if params.inhibitor_id:
        for inh in project.inhibitors:
            if inh.id == params.inhibitor_id and params.Ki == 1.0:
                params.Ki = inh.ki

    law = reaction.rate_law

    def rate(conc: dict[str, float]) -> float:
        enz = enzyme_amount(project, reaction, params, enzyme_scale)
        I = resolve_inhibitor_conc(
            project, reaction, params, conc, inhibitor_overrides
        )
        if law == RateLawType.MASS_ACTION:
            return mass_action_rate(reaction, conc, params)
        if law == RateLawType.MICHAELIS_MENTEN:
            return michaelis_menten_rate(reaction, conc, params, enz)
        if law == RateLawType.COMPETITIVE_INHIBITION:
            return competitive_inhibition_rate(reaction, conc, params, I, enz)
        if law == RateLawType.NONCOMPETITIVE_INHIBITION:
            return noncompetitive_inhibition_rate(reaction, conc, params, I, enz)
        if law == RateLawType.UNCOMPETITIVE_INHIBITION:
            return uncompetitive_inhibition_rate(reaction, conc, params, I, enz)
        if law == RateLawType.HILL:
            return hill_rate(reaction, conc, params, enz)
        if law == RateLawType.CUSTOM:
            return custom_rate(reaction, conc, params, name_to_id, id_to_name)
        return mass_action_rate(reaction, conc, params)

    return rate


def rate_law_latex(reaction: Reaction) -> str:
    """Human-readable rate equation for the inspector."""
    p = reaction.parameters
    substrates = " · ".join(
        f"[{s.metabolite_id}]" + (f"^{abs(s.stoichiometry):g}" if abs(s.stoichiometry) != 1 else "")
        for s in reaction.substrates
    ) or "1"
    products = " · ".join(
        f"[{s.metabolite_id}]" + (f"^{abs(s.stoichiometry):g}" if abs(s.stoichiometry) != 1 else "")
        for s in reaction.products
    ) or "1"

    law = reaction.rate_law
    if law == RateLawType.MASS_ACTION:
        if reaction.reversible or p.kr > 0:
            return f"v = k_f · {substrates} − k_r · {products}"
        return f"v = k_f · {substrates}"
    if law == RateLawType.MICHAELIS_MENTEN:
        return f"v = V_max · [S] / (K_m + [S])"
    if law == RateLawType.COMPETITIVE_INHIBITION:
        return f"v = V_max · [S] / (K_m (1 + [I]/K_i) + [S])"
    if law == RateLawType.NONCOMPETITIVE_INHIBITION:
        return f"v = (V_max / (1 + [I]/K_i)) · [S] / (K_m + [S])"
    if law == RateLawType.UNCOMPETITIVE_INHIBITION:
        return f"v = V_max · [S] / (K_m + [S](1 + [I]/K_i))"
    if law == RateLawType.HILL:
        return f"v = V_max · [S]^n / (K_{{1/2}}^n + [S]^n)"
    if law == RateLawType.CUSTOM:
        return f"v = {p.custom_expression or '(empty)'}"
    return "v = ?"


def rate_law_params_display(reaction: Reaction) -> dict[str, float | str]:
    p = reaction.parameters
    law = reaction.rate_law
    out: dict[str, float | str] = {}
    if law == RateLawType.MASS_ACTION:
        out = {"kf": p.kf, "kr": p.kr}
    elif law == RateLawType.MICHAELIS_MENTEN:
        out = {"Vmax": p.Vmax, "Km": p.Km, "Km_product": p.Km_product}
    elif law in (
        RateLawType.COMPETITIVE_INHIBITION,
        RateLawType.NONCOMPETITIVE_INHIBITION,
        RateLawType.UNCOMPETITIVE_INHIBITION,
    ):
        out = {"Vmax": p.Vmax, "Km": p.Km, "Ki": p.Ki}
    elif law == RateLawType.HILL:
        out = {"Vmax": p.Vmax, "K_half": p.K_half, "n_hill": p.n_hill}
    elif law == RateLawType.CUSTOM:
        out = {
            "kf": p.kf,
            "kr": p.kr,
            "Vmax": p.Vmax,
            "Km": p.Km,
            "expression": p.custom_expression,
        }
    if p.enzyme_id:
        out["enzyme_id"] = p.enzyme_id
    if p.inhibitor_id:
        out["inhibitor_id"] = p.inhibitor_id
    return out
