def umdrehen(text: str) -> str:
    return text[::-1]


def woerter(text: str) -> str:
    return f"{len(text.split())} Woerter"


TOOLS = {"umdrehen": umdrehen, "woerter": woerter}
