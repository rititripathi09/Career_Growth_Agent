"""Small Streamlit helpers shared by the pages."""
from __future__ import annotations

import streamlit as st

from core import db
from core.access import Access
from core.seed import seed
from core.taxonomy import load_catalog, load_taxonomy

TYPE_LABEL = {"mandatory": "Mandatory", "org_wide": "Org-wide", "good_to_have": "Good to have"}
TYPE_COLOR = {"mandatory": "red", "org_wide": "violet", "good_to_have": "blue"}


@st.cache_resource
def get_conn():
    conn = db.connect()
    if conn.execute("SELECT COUNT(*) FROM employee").fetchone()[0] == 0:
        seed(conn)
    return conn


def tax():
    return load_taxonomy()


def catalog():
    return load_catalog()


def access() -> Access:
    return Access(get_conn(), st.session_state.get("viewer_id", "priya"))


def type_badge(gap_type: str) -> str:
    return f":{TYPE_COLOR[gap_type]}-badge[{TYPE_LABEL[gap_type]}]"
