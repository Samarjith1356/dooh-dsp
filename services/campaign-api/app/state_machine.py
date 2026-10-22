ALLOWED = {
    "draft": {"pending_approval", "completed"},
    "pending_approval": {"active", "draft", "paused"},
    "active": {"paused", "completed"},
    "paused": {"active", "completed", "draft"},
    "completed": set(),
}

STATES = ("draft", "pending_approval", "active", "paused", "completed")


class InvalidTransition(ValueError):
    pass


def can_transition(current: str, target: str) -> bool:
    return target in ALLOWED.get(current, set())


def transition(current: str, target: str) -> str:
    if current == target:
        return current
    if not can_transition(current, target):
        raise InvalidTransition(f"cannot move campaign from {current} to {target}")
    return target


def compiles(state: str) -> bool:
    return state == "active"
