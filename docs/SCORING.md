# Scoring contract

Phase 4b defines the scoring contract only. Submission and grading behavior are Phase 5.

Dynamic challenge values use one of these formulas, based on the solve count:

- Linear: `value = max(minimum, initial - decay * (solves - 1))`
- Logarithmic: `value = max(minimum, ceil(((minimum - initial) / decay^2) * (solves - 1)^2 + initial))`

The solve-count hook is intentionally a stub until Phase 5:

```python
def get_solve_count(challenge_id: UUID) -> int:
    """Return the committed solve count for a challenge."""
    raise NotImplementedError
```

Recalculation runs inside the same database transaction as a solve. Score is always computed from events; a stored team total is not used.

Every score change is append-only in `ScoreEvent`:

`id, team_id, kind (solve|hint|award|adjustment), challenge_id (nullable), delta, created_at`

The tie-break is higher score first, then the earlier time of the last scoring event.

Hint unlocking is allowed even when a team has few points. Hint costs are applied in Phase 5, and the team total is floored at zero.
