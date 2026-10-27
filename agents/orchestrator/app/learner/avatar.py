"""Profile pictures kept on the server, so other learners see them on
leaderboards. The browser crops and shrinks the picture (256px, plus a 64px
thumbnail) and sends both as image data URLs; only small JPEG, PNG or WebP
images are accepted."""
from __future__ import annotations

import base64
import binascii
import re

from app import db
from app.models import UserAvatar

_DATA_URL = re.compile(r"^data:image/(jpeg|png|webp);base64,([A-Za-z0-9+/=]+)$")
MAX_IMAGE_BYTES = 200_000
MAX_THUMB_BYTES = 20_000
# What each type's file starts with, so a data URL cannot carry anything else.
_MAGIC = {"jpeg": (b"\xff\xd8\xff",), "png": (b"\x89PNG\r\n\x1a\n",), "webp": (b"RIFF",)}


class AvatarError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _check(data_url: str, limit: int) -> str:
    match = _DATA_URL.match(data_url or "")
    if not match:
        raise AvatarError("Send a JPEG, PNG or WebP picture.")
    try:
        raw = base64.b64decode(match.group(2), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise AvatarError("That picture could not be read.") from exc
    if len(raw) > limit:
        raise AvatarError("That picture is too large.")
    if not raw.startswith(_MAGIC[match.group(1)]):
        raise AvatarError("That file is not the picture it says it is.")
    return data_url


def save(user_id: str, image: str, thumb: str) -> dict:
    image = _check(image, MAX_IMAGE_BYTES)
    thumb = _check(thumb, MAX_THUMB_BYTES)
    session = db.get_session()
    try:
        row = session.get(UserAvatar, user_id)
        if row is None:
            session.add(UserAvatar(user_id=user_id, image=image, thumb=thumb))
        else:
            row.image, row.thumb = image, thumb
        session.commit()
    finally:
        session.close()
    return {"saved": True}


def get(user_id: str) -> str | None:
    session = db.get_session()
    try:
        row = session.get(UserAvatar, user_id)
        return row.image if row else None
    finally:
        session.close()


def remove(user_id: str) -> None:
    session = db.get_session()
    try:
        session.query(UserAvatar).filter_by(user_id=user_id).delete()
        session.commit()
    finally:
        session.close()


def thumbs(user_ids: list[str]) -> dict[str, str]:
    """user id -> 64px picture, for the ones who have one."""
    if not user_ids:
        return {}
    session = db.get_session()
    try:
        return {uid: thumb for uid, thumb in session.query(UserAvatar.user_id, UserAvatar.thumb)
                .filter(UserAvatar.user_id.in_(user_ids)).all()}
    finally:
        session.close()
