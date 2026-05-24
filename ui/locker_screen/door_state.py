"""Estado compartido de lockers sin cerrar — persiste entre pantallas."""

_open_lockers: set[int] = set()


def add_open_locker(locker_id: int) -> None:
    _open_lockers.add(int(locker_id))


def remove_open_locker(locker_id: int) -> None:
    _open_lockers.discard(int(locker_id))


def get_open_lockers() -> frozenset[int]:
    return frozenset(_open_lockers)


def has_open_lockers() -> bool:
    return bool(_open_lockers)
