# Design: Commercial Impact Service Refactoring

Refactor `commercial_impact.py` for maintainability and robustness.

## Requirements

- Use `Enum` for `MaintenanceUrgency`.
- Define constants for thresholds (10.0, 1.0) and divisor (1000.0).
- Add type hints and docstrings.
- Add input validation (positive values for `wh_loss` and `tariff`).
- Update tests for boundaries and edge cases.

## Proposed Design

### 1. Enum Definition
```python
from enum import Enum

class MaintenanceUrgency(Enum):
    CRITICAL = "Schedule within 48 hours"
    MONITOR = "Monitor performance"
    HEALTHY = "System Healthy"
```

### 2. Constants
```python
HIGH_IMPACT_THRESHOLD = 10.0
LOW_IMPACT_THRESHOLD = 1.0
WH_TO_KWH_DIVISOR = 1000.0
```

### 3. Logic Improvements
- Input validation: `raise ValueError` if `wh_loss < 0` or `tariff < 0`.
- Use inclusive thresholds `>=` if confirmed (feedback suggested inclusive might be appropriate).

### 4. Test Expansion
- Test `wh_loss=0`.
- Test `financial_loss=10.0` (boundary).
- Test `financial_loss=1.0` (boundary).
- Test negative values.

## Verification Plan
- Run `pytest tests/test_commercial_impact.py`.
