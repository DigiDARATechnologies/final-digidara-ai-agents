"""Small dependency-free request validation helpers."""

import re


class ValidationError(ValueError):
    pass


def boolean(value, field):
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be true or false.")
    return value


def positive_int(value, field):
    if isinstance(value, bool):
        raise ValidationError(f"{field} must be a positive integer.")
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{field} must be a positive integer.") from None
    if parsed <= 0:
        raise ValidationError(f"{field} must be a positive integer.")
    return parsed


def bounded_int(value, field, minimum, maximum):
    if isinstance(value, bool):
        raise ValidationError(
            f"{field} must be between {minimum} and {maximum}."
        )
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValidationError(
            f"{field} must be between {minimum} and {maximum}."
        ) from None
    if not minimum <= parsed <= maximum:
        raise ValidationError(
            f"{field} must be between {minimum} and {maximum}."
        )
    return parsed


def text(value, field, *, required=False, max_length=1000):
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be text.")
    cleaned = value.strip()
    if required and not cleaned:
        raise ValidationError(f"{field} is required.")
    if len(cleaned) > max_length:
        raise ValidationError(
            f"{field} must be {max_length} characters or fewer."
        )
    return cleaned


def email(value):
    cleaned = text(value, "email", required=True, max_length=150)
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", cleaned):
        raise ValidationError("email must be a valid email address.")
    return cleaned
