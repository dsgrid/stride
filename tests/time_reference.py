"""Reference calculations for tests of time labels.

These are written independently of the SQL that stride generates, so tests can compare the
two.
"""

from stride.api.utils import FALL_DAY_END, FALL_DAY_START, SPRING_DAY_END, SPRING_DAY_START


def season(day_of_year: int) -> str:
    """Return the season of a 1-based day of year, using stride's season boundaries."""
    if SPRING_DAY_START <= day_of_year < SPRING_DAY_END:
        return "Spring"
    if SPRING_DAY_END <= day_of_year < FALL_DAY_START:
        return "Summer"
    if FALL_DAY_START <= day_of_year < FALL_DAY_END:
        return "Fall"
    return "Winter"
