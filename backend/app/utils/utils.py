from typing import Final

INDIAN_MOBILE_LENGTH: Final[int] = 10


def clean_indian_number(number: str) -> str:
    raw = number.strip()
    raw = raw.replace(" ", "")
    if raw.startswith("+"):
        raw = raw[1:]
    if raw.startswith("91"):
        raw = raw[2:]
    if not raw.isdigit():
        raise ValueError("Phone number must contain digits only.")
    if len(raw) != INDIAN_MOBILE_LENGTH:
        raise ValueError("Phone number must be exactly 10 digits after normalization.")
    return f"+91{raw}"

