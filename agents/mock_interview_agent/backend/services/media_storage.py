"""Safe helpers for files managed by the application."""

import logging
from pathlib import Path

from http_context import log
from settings import (
    AUDIO_UPLOAD_DIR,
    AUDIO_URL_PREFIX,
    AVATAR_UPLOAD_DIR,
    AVATAR_URL_PREFIX,
)


def delete_managed_audio(audio_path):
    _delete_managed_file(
        audio_path,
        AUDIO_URL_PREFIX,
        AUDIO_UPLOAD_DIR,
        "audio_file_removal_failed",
        "Could not remove superseded answer recording",
    )


def delete_managed_avatar(avatar_url):
    _delete_managed_file(
        avatar_url,
        AVATAR_URL_PREFIX,
        AVATAR_UPLOAD_DIR,
        "avatar_file_removal_failed",
        "Could not remove old managed avatar file",
    )


def _delete_managed_file(value, url_prefix, directory, event, message):
    if not value or not value.startswith(url_prefix):
        return
    filename = value.removeprefix(url_prefix)
    if not filename or Path(filename).name != filename:
        return
    target = (directory / filename).resolve()
    if target.parent != directory:
        return
    try:
        target.unlink(missing_ok=True)
    except OSError:
        log(
            logging.WARNING,
            event,
            message,
            file_name=target.name,
            exc_info=True,
        )
