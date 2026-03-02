
import streamlit as st

from crud import get_connection


def login(username, password):

    if not username or not password:
        return None

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, username, role
        FROM users
        WHERE username = %s
        AND password = %s
        AND (is_draft IS FALSE OR is_draft IS NULL)
    """, (username, password))

    row = cur.fetchone()

    cur.close()
    conn.close()

    if row:
        return {
            "id": row[0],
            "username": row[1],
            "role": row[2]
        }

    return None

