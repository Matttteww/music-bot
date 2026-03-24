"""Вспомогательные функции."""


def pluralize_likes(n: int) -> str:
    """Склонение: 1 лайк, 2 лайка, 5 лайков."""
    n = int(n)
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} лайк"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return f"{n} лайка"
    return f"{n} лайков"
