"""Проверка реквизитов: ИНН (10/12 цифр) и ОГРН/ОГРНИП по контрольным числам."""

from __future__ import annotations

_INN10 = (2, 4, 10, 3, 5, 9, 4, 6, 8)
_INN12_1 = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
_INN12_2 = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)


def _ctrl(digits: list[int], weights: tuple[int, ...]) -> int:
    return sum(d * w for d, w in zip(digits, weights, strict=False)) % 11 % 10


def is_valid_inn(inn: str | None) -> bool:
    if not inn or not inn.isdigit() or len(inn) not in (10, 12):
        return False
    d = [int(c) for c in inn]
    if len(inn) == 10:
        return _ctrl(d, _INN10) == d[9]
    return _ctrl(d, _INN12_1) == d[10] and _ctrl(d, _INN12_2) == d[11]


def legal_form_by_inn(inn: str) -> str:
    """10 цифр — юридическое лицо, 12 — индивидуальный предприниматель."""
    return "IP" if len(inn) == 12 else "LE"


def is_valid_ogrn(ogrn: str | None) -> bool:
    if not ogrn or not ogrn.isdigit():
        return False
    if len(ogrn) == 13:
        return int(ogrn[:12]) % 11 % 10 == int(ogrn[12])
    if len(ogrn) == 15:
        return int(ogrn[:14]) % 13 % 10 == int(ogrn[14])
    return False


def make_inn(prefix: str) -> str:
    """Дополнить префикс (9 или 10 цифр) контрольными разрядами — для синтетических данных."""
    d = [int(c) for c in prefix]
    if len(d) == 9:
        d.append(_ctrl(d, _INN10))
        return "".join(map(str, d))
    if len(d) == 10:
        d.append(_ctrl(d, _INN12_1))
        d.append(_ctrl(d, _INN12_2))
        return "".join(map(str, d))
    raise ValueError("prefix must have 9 (ЮЛ) or 10 (ИП) digits")


def make_ogrn(prefix: str) -> str:
    if len(prefix) == 12:
        return prefix + str(int(prefix) % 11 % 10)
    if len(prefix) == 14:
        return prefix + str(int(prefix) % 13 % 10)
    raise ValueError("prefix must have 12 (ОГРН) or 14 (ОГРНИП) digits")
