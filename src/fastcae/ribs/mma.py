"""The optimiser a rib network is moved by: the method of moving asymptotes with many rules held
at once, and the schedules a pass runs on - how widely a fin is drawn, how sharply its presence
counts and how much the lead weighs, step by step."""

from __future__ import annotations

import numpy as np

RADII = [1.5] * 12 + list(np.linspace(1.5, 0.87, 12)) + [0.87] * 56
"""The smooth step's half width, in cubes: wide while the plates find their places - every cube
near a plate feels it - then a cube's own."""

PRESENCE = [1.0] * 12 + list(np.linspace(1.0, 3.0, 12)) + [3.0] * 56
"""The presence's power: a plate half there costs half the metal but gives an eighth of the
stiffness, so a plate is kept whole or let go."""

LEAD_WEIGHTS = [0.0] * 10 + list(np.linspace(0.125, 1.0, 8)) + [1.0] * 62
"""How much of the gear mesh's lead the objective holds, step by step: none while the plates first
settle under the smooth largest displacement, then all of it."""

MOVE = 0.03
"""The most a number moves in one step, as a share of its range."""

ASYMPTOTE = 0.2

POLISH_RADIUS = 1.0
"""The smooth step's half width while polishing, in cubes: plates as crisp as the cubes allow."""


def _step(phi: np.ndarray, radius: float) -> tuple[np.ndarray, np.ndarray]:
    """The share of a ball of ``radius`` inside a face ``phi`` from its centre, and its slope."""
    z = np.clip(phi / radius, -1.0, 1.0)
    return 0.5 + 0.75 * z - 0.25 * z**3, np.where(
        np.abs(z) < 1.0, 0.75 * (1.0 - z**2) / radius, 0.0
    )


RELAX = 1e3
"""What one unit of a rule broken costs in :func:`_mma_many` - Svanberg's ``c``. Large, so a rule
is kept whenever it can be; finite, so a start that breaks one still has a step to take."""


def _mma_many(
    x: np.ndarray,
    df: np.ndarray,
    g: np.ndarray,
    dg: np.ndarray,
    low: np.ndarray,
    upp: np.ndarray,
    old1: np.ndarray | None,
    old2: np.ndarray | None,
    it: int,
    move: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """One MMA step for ``min f`` subject to **several** rules ``g_i <= 0``, ``0 <= x <= 1``.

    :func:`_mma` holds one rule - the budget - and anything else had to be a charge on the
    objective, which only discourages. Here each rule is held as a rule. The subproblem is
    Svanberg's: every number's best value is closed form for given multipliers, and the multipliers
    are found by maximising the dual, which is concave and smooth. A rule that cannot be met from
    where the run stands is relaxed at a cost of :data:`RELAX` a unit rather than leaving no step.
    """
    from scipy.optimize import minimize

    g = np.atleast_1d(np.asarray(g, float))
    dg = np.atleast_2d(np.asarray(dg, float))
    if it < 2 or old1 is None or old2 is None:
        low, upp = x - max(ASYMPTOTE * move / MOVE, 0.02), x + max(ASYMPTOTE * move / MOVE, 0.02)
    else:
        sign = (x - old1) * (old1 - old2)
        gamma = np.where(sign > 0, 1.2, np.where(sign < 0, 0.7, 1.0))
        low = np.clip(x - gamma * (old1 - low), x - 10.0, x - 0.01)
        upp = np.clip(x + gamma * (upp - old1), x + 0.01, x + 10.0)
    alpha = np.maximum.reduce([np.zeros_like(x), low + 0.1 * (x - low), x - move])
    beta = np.minimum.reduce([np.ones_like(x), upp - 0.1 * (upp - x), x + move])
    ux, xl = upp - x, x - low
    raa0 = 1e-5
    p0 = (1.001 * np.maximum(df, 0) + 0.001 * np.maximum(-df, 0) + raa0) * ux**2
    q0 = (0.001 * np.maximum(df, 0) + 1.001 * np.maximum(-df, 0) + raa0) * xl**2
    pc = np.maximum(dg, 0.0) * ux**2
    qc = np.maximum(-dg, 0.0) * xl**2
    rc = g - (pc / ux + qc / xl).sum(axis=1)

    def x_of(lam: np.ndarray) -> np.ndarray:
        sp, sq = np.sqrt(p0 + lam @ pc), np.sqrt(q0 + lam @ qc)
        return np.clip((sp * low + sq * upp) / (sp + sq), alpha, beta)

    def dual(lam: np.ndarray) -> tuple[float, np.ndarray]:
        y = x_of(lam)
        a, b = 1.0 / (upp - y), 1.0 / (y - low)
        rules = pc @ a + qc @ b + rc
        over = np.maximum(lam - RELAX, 0.0)
        value = float(p0 @ a + q0 @ b + lam @ rules - 0.5 * over @ over)
        return -value, -(rules - over)

    found = minimize(
        dual,
        np.zeros(len(g)),
        jac=True,
        method="L-BFGS-B",
        bounds=[(0.0, None)] * len(g),
        options={"maxiter": 500, "gtol": 1e-10},
    )
    return x_of(found.x), low, upp
