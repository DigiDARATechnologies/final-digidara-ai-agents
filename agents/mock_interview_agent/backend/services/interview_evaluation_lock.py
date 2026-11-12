"""Cross-worker guard against duplicate final evaluations for one interview."""

from contextlib import contextmanager

from flask import current_app

import db


@contextmanager
def interview_evaluation_lock(interview_id):
    """Acquire a MySQL advisory lock for the full finalization request.

    MySQL releases named locks when the connection closes, including after a
    worker crash. Tests bypass this infrastructure boundary because their DB
    access is mocked; production fails closed if the lock cannot be acquired.
    """
    if current_app.testing:
        yield True
        return

    lock_name = f"mi_final_eval:{int(interview_id)}"
    connection = db.get_conn()
    cursor = connection.cursor()
    acquired = False
    try:
        cursor.execute("SELECT GET_LOCK(%s, 0)", (lock_name,))
        row = cursor.fetchone()
        acquired = bool(row and row[0] == 1)
        yield acquired
    finally:
        if acquired:
            try:
                cursor.execute("SELECT RELEASE_LOCK(%s)", (lock_name,))
                cursor.fetchone()
            finally:
                cursor.close()
                connection.close()
        else:
            cursor.close()
            connection.close()
