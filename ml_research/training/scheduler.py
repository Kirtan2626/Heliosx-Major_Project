"""
City rotation and date sampling for training.

Handles round-robin city scheduling and random date selection,
ensuring held-out evaluation dates are excluded from training.
"""

import random
from datetime import datetime


class CityScheduler:
    """Round-robin city scheduler."""

    def __init__(self, cities: list[str]):
        self.cities = list(cities)
        self.index = 0

    def next_city(self) -> str:
        """Return next city in round-robin order."""
        city = self.cities[self.index % len(self.cities)]
        self.index += 1
        return city

    def reset(self):
        self.index = 0


class DateSampler:
    """Random date sampler with holdout exclusion."""

    def __init__(
        self,
        available_dates: dict[str, list[datetime]],
        eval_dates: dict[str, list[datetime]] = None,
        seed: int = 42,
    ):
        """
        Args:
            available_dates: {city_name: [list of available dates]}
            eval_dates: {city_name: [dates held out for evaluation]}
            seed: Random seed
        """
        self.rng = random.Random(seed)
        self.eval_dates = eval_dates or {}

        # Build training dates (exclude eval dates)
        self.train_dates = {}
        for city, dates in available_dates.items():
            eval_set = set()
            if city in self.eval_dates:
                eval_set = {d.date() if hasattr(d, 'date') else d
                            for d in self.eval_dates[city]}

            self.train_dates[city] = [
                d for d in dates
                if (d.date() if hasattr(d, 'date') else d) not in eval_set
            ]

    def sample_date(self, city: str) -> datetime:
        """Sample a random training date for a city."""
        dates = self.train_dates.get(city, [])
        if not dates:
            # Fallback: generate synthetic dates
            month = self.rng.randint(1, 12)
            day = self.rng.randint(1, 28)
            return datetime(2023, month, day)

        return self.rng.choice(dates)

    def get_eval_dates(self, city: str) -> list[datetime]:
        """Get held-out evaluation dates for a city."""
        return self.eval_dates.get(city, [])


def select_eval_dates(
    available_dates: dict[str, list[datetime]],
    n_per_city: int = 5,
    seed: int = 42,
) -> dict[str, list[datetime]]:
    """
    Select held-out evaluation dates for each city.

    Selects dates spread across seasons for diversity.

    Args:
        available_dates: {city_name: [available dates]}
        n_per_city: Number of dates to hold out per city
        seed: Random seed

    Returns:
        {city_name: [eval dates]}
    """
    rng = random.Random(seed)
    eval_dates = {}

    for city, dates in available_dates.items():
        if len(dates) <= n_per_city:
            eval_dates[city] = dates
            continue

        # Try to spread across months
        by_month = {}
        for d in dates:
            m = d.month if hasattr(d, 'month') else d.date().month
            if m not in by_month:
                by_month[m] = []
            by_month[m].append(d)

        selected = []
        months = sorted(by_month.keys())

        # Round-robin across months
        while len(selected) < n_per_city and months:
            for m in months:
                if by_month[m] and len(selected) < n_per_city:
                    date = rng.choice(by_month[m])
                    selected.append(date)
                    by_month[m].remove(date)
            months = [m for m in months if by_month[m]]

        eval_dates[city] = selected

    return eval_dates
