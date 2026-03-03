import psycopg2
import os
import streamlit as st
import datetime
import plotly.express as px
from auth import login
from crud import *

st.set_page_config(layout="wide")

# ================= SESSION INIT =================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "master_id" not in st.session_state:
    st.session_state.master_id = None

# ================= LOGIN =================
if not st.session_state.logged_in:

    st.title("Login")

    username_input = st.text_input("Username")
    password_input = st.text_input("Password", type="password")

    if st.button("Login"):
        user = login(username_input, password_input)

        if user:
            st.session_state.logged_in = True
            st.session_state.user_id = user["id"]
            st.session_state.username = user["username"]
            st.session_state.role = user["role"]
            st.rerun()
        else:
            st.error("Invalid login")

    st.stop()

# ================= AFTER LOGIN =================
user_id = st.session_state.user_id
is_admin = st.session_state.role == "admin"

# ================= TOP BAR =================
col1, col2, col3 = st.columns([7, 2, 1])

with col1:
    st.markdown("## 🏗️ Canal Management Dashboard")
    st.caption("Application Submission System")

with col2:
    st.markdown(f"👤 **{st.session_state.username}**")

with col3:
    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()

# =====================================================
# ================= USER SIDE =========================
# =====================================================

if not is_admin:

    all_tables = get_all_tables()

    modules = {}
    for table in all_tables:
        if "_" in table:
            module_prefix = "_".join(table.split("_")[:2])
            modules.setdefault(module_prefix, []).append(table)

    # Safety check
    if not modules:
        st.error("No modules found. Check database connection.")
        st.stop()

    module_display_map = {
        m: m.replace("_", " ").title()
        for m in modules.keys()
    }

    selected_module = st.selectbox(
        "Select Module",
        options=list(module_display_map.keys()),
        format_func=lambda x: module_display_map[x]
    )

    if selected_module not in modules:
        st.error("Invalid module selection.")
        st.stop()

    module_name = selected_module
    tables = sorted(modules[module_name])
    prefix = module_name + "_"

    st.title(f"📊 {module_display_map[module_name]}")
    st.markdown("---")

    percentage, completed, total = get_user_progress(user_id, tables)

    st.progress(int(percentage))
    st.caption(f"Sections Completed: {completed} / {total}")

    tabs = st.tabs([
        table.replace(prefix, "").replace("_", " ").title()
        for table in tables
    ])

    for i, table in enumerate(tables):

        with tabs[i]:

            columns = get_table_columns(table, is_admin=False)
            restore_draft_to_session(table, columns, user_id)

            form_data = {}
            filled_fields = 0

            colA, colB = st.columns(2)

            for index, col_info in enumerate(columns):

                col_name = col_info["column_name"]
                dtype = col_info["data_type"]
                key = f"{table}_{col_name}"

                target_col = colA if index % 2 == 0 else colB

                with target_col:
                    if dtype in ("integer", "bigint", "smallint"):
                        value = st.number_input(col_name, step=1, key=key)
                    elif dtype in ("numeric", "double precision", "real"):
                        value = st.number_input(col_name, key=key)
                    elif dtype == "date":
                        value = st.date_input(col_name, key=key)
                    else:
                        value = st.text_input(col_name, key=key)

                form_data[col_name] = value

                if value not in ("", None):
                    filled_fields += 1

            if st.button("💾 Save Section", key=f"save_{table}"):

                if filled_fields == 0:
                    st.warning("Section is empty.")
                else:
                    save_draft_record(table, form_data, user_id)
                    st.success("Section saved.")
                    st.rerun()

    # ================= FINAL SUBMIT =================
    st.markdown("---")
    st.subheader("Final Master Submission")

    if st.button("🚀 Submit Complete Application"):

        incomplete_sections = get_incomplete_forms(user_id, tables)

        if incomplete_sections:
            st.error("The following sections are not completed:")
            for sec in incomplete_sections:
                clean_name = sec.replace(prefix, "").replace("_", " ").title()
                st.write(f"• {clean_name}")
        else:
            create_master_submission(user_id, module_name, tables)
            st.success("Application submitted successfully.")
            st.rerun()

    # ================= USER SUBMISSIONS =================
    st.markdown("---")
    st.subheader("Your Submitted Applications")

    submissions = get_user_master_submissions(user_id, module_name)

    if submissions:
        for sub in submissions:
            badge = sub["status"]
            with st.expander(f"{module_display_map[module_name]} - {badge}"):
                full_data = get_full_submission_data(sub["id"])
                for _, df_section in full_data.items():
                    st.dataframe(df_section, use_container_width=True)
    else:
        st.info("No submissions yet.")

# =====================================================
# ================= ADMIN SIDE ========================
# =====================================================

if is_admin:

    st.markdown("---")
    st.subheader("📋 Admin Panel")

    users_df = get_users_with_data()

    selected_user = st.selectbox(
        "Select User",
        users_df["username"]
    )

    user_row = users_df[
        users_df["username"] == selected_user
    ].iloc[0]

    selected_user_id = int(user_row["id"])

    approved, rejected, pending = get_user_master_status_counts(selected_user_id)

    c1, c2, c3 = st.columns(3)
    c1.metric("Approved", approved)
    c2.metric("Rejected", rejected)
    c3.metric("Pending", pending)

    submissions = get_user_master_submissions_admin(selected_user_id)

    if submissions:
        for sub in submissions:

            module_label = (sub.get("module") or "Unknown").replace("_", " ").title()
            status = sub["status"]

            with st.expander(f"{module_label} - {status}"):

                full_data = get_full_submission_data(sub["id"])
                for _, df_section in full_data.items():
                    st.dataframe(df_section, use_container_width=True)

                colA, colB = st.columns(2)

                if colA.button("Approve", key=f"a{sub['id']}"):
                    approve_master_submission(sub["id"])
                    st.rerun()

                reason = colB.text_input("Reason", key=f"r{sub['id']}")

                if colB.button("Reject", key=f"rej{sub['id']}"):
                    reject_master_submission(sub["id"], reason)
                    st.rerun()
    else:
        st.info("No submissions found.")
