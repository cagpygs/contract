import psycopg2
import os
import streamlit as st
import datetime
import plotly.express as px
from auth import login
from crud import *

st.set_page_config(layout="wide")

st.markdown("""
<style>

/* Page background */
.block-container {
    padding-top: 2rem;
    padding-bottom: 2rem;
}

/* Premium form card */
.premium-card {
    background-color: #ffffff;
    padding: 25px;
    border-radius: 14px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.06);
    margin-bottom: 25px;
}

/* Tabs styling */
button[data-baseweb="tab"] {
    font-size: 16px;
    font-weight: 600;
    padding: 10px 20px;
}

button[data-baseweb="tab"][aria-selected="true"] {
    border-bottom: 3px solid #2563eb;
    color: #2563eb;
}


/* Custom Progress Bar Container */
.custom-progress {
    background-color: #e5e7eb;
    border-radius: 10px;
    height: 14px;
    width: 100%;
    margin-top: 10px;
}

/* Progress Fill */
.custom-progress-fill {
    height: 100%;
    border-radius: 10px;
    text-align: right;
    padding-right: 8px;
    font-size: 11px;
    font-weight: 600;
    color: white;
    line-height: 14px;
    
    
</style>
""", unsafe_allow_html=True)


# ================= SESSION =================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# ================= LOGIN =================
if not st.session_state.logged_in:

    st.title("Login")
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")

    if st.button("Login"):
        user = login(u, p)
        if user:
            st.session_state.logged_in = True
            st.session_state.user_id = user["id"]
            st.session_state.username = user["username"]
            st.session_state.role = user["role"]
            st.rerun()
        else:
            st.error("Invalid login")

    st.stop()

if "master_id" not in st.session_state:
    st.session_state.master_id = None
# ================= USER INFO =================
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
# ================= USER SIDE =================
# =====================================================

def is_section_complete(user_id, table):
    percentage, completed, total = get_user_progress(user_id, [table])
    return percentage == 100


if not is_admin:

    all_tables = get_all_tables()

    # Extract module prefixes dynamically
    modules = {}

    for table in all_tables:
        if "_" in table:
            module_prefix = "_".join(table.split("_")[:2])  # contract_management
            modules.setdefault(module_prefix, []).append(table)

    # Sidebar module selection
    module_display_map = {
        m: m.replace("_", " ").title()
        for m in modules.keys()
    }

    selected_module = st.sidebar.radio(
        "📂 Select Module",
        list(module_display_map.values())
    )

    # Reverse lookup
    module_name = [
        k for k, v in module_display_map.items()
        if v == selected_module
    ][0]

    tables = sorted(modules[module_name])
    prefix = module_name + "_"

    if st.session_state.master_id:
        can_edit = can_user_edit(st.session_state.master_id)
    else:
        can_edit = True  # No submission yet → allow editing

    st.title(f"📊 {selected_module}")
    st.markdown("---")

    # ===== Premium Card Start =====
    st.markdown('<div class="premium-card">', unsafe_allow_html=True)

    # Progress Section (Top)
    percentage, completed, total = get_user_progress(user_id, tables)

    # Decide color based on completion %
    if percentage < 40:
        color = "#ef4444"  # Red
    elif percentage < 75:
        color = "#f59e0b"  # Orange
    else:
        color = "#10b981"  # Green

    st.markdown(f"""
    <div class="custom-progress">
        <div class="custom-progress-fill" 
             style="width: {percentage}%; background-color: {color};">
            {percentage:.0f}%
        </div>
    </div>
    """, unsafe_allow_html=True)

    if percentage == 100:
        st.markdown("""
        <div style="
            margin-top:15px;
            padding:15px;
            border-radius:10px;
            background-color:#ecfdf5;
            border:1px solid #10b981;
            color:#065f46;
            font-weight:600;
            text-align:center;
            font-size:16px;
        ">
            🎉 All Sections Complete ✅<br>
            You can now submit your application.
        </div>
        """, unsafe_allow_html=True)



    st.caption(f"Sections Completed: {completed} / {total}")

    st.markdown("")

    # Tabs
    tab_labels = []

    for table in tables:

        section_name = table.replace(prefix, "").replace("_", " ").title()

        # Check completion using your progress logic
        is_complete = is_section_complete(user_id, table)

        if is_complete:
            label = f"🟢 {section_name}"
        else:
            label = f"⚪ {section_name}"

        tab_labels.append(label)

    tabs = st.tabs(tab_labels)

    for i, table in enumerate(tables):

        with tabs[i]:

            columns = get_table_columns(table, is_admin=False)

            restore_draft_to_session(table, columns, user_id)

            form_data = {}
            filled_fields = 0

            col1, col2 = st.columns(2)

            for index, col_info in enumerate(columns):

                col = col_info["column_name"]
                dtype = col_info["data_type"]
                key = f"{table}_{col}"

                target_col = col1 if index % 2 == 0 else col2

                with target_col:

                    if dtype in ("integer", "bigint", "smallint"):
                        value = st.number_input(col, step=1, key=key)
                    elif dtype in ("numeric", "double precision", "real"):
                        value = st.number_input(col, key=key)
                    elif dtype == "date":
                        value = st.date_input(col, key=key)
                    else:
                        value = st.text_input(col, key=key)

                form_data[col] = value

                if value not in ("", None):
                    filled_fields += 1

            if st.button("💾 Save Section", key=f"save_{table}"):

                if not can_edit:
                    st.warning("You cannot edit unless rejected.")
                elif filled_fields == 0:
                    st.warning("Section is empty.")
                else:
                    save_draft_record(table, form_data, user_id)
                    st.success("Section saved.")
                    st.rerun()

    # ---------- FINAL SUBMIT ----------
    st.markdown("---")
    st.subheader("Final Master Submission")
    st.markdown("---")

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

    # ---------- USER SUBMISSIONS ----------
    st.markdown("---")
    st.subheader("Your Submitted Applications")

    submissions = get_user_master_submissions(user_id, module_name)

    if submissions:
        for sub in submissions:
            module_label = (
                "Contract Management"
                if sub["module"] == "contract_management"
                else "Canal Performance"
            )

            status = sub["status"]

            if status == "APPROVED":
                badge = "🟢 APPROVED"
            elif status == "REJECTED":
                badge = "🔴 REJECTED"
            else:
                badge = "🟡 PENDING"

            with st.expander(f"{module_label} - {badge}"):
                full_data = get_full_submission_data(sub["id"])
                for section_name, df_section in full_data.items():
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
    selected_user = st.selectbox("Select User", users_df["username"])
    user_row = users_df[users_df["username"] == selected_user].iloc[0]
    selected_user_id = int(user_row["id"])

    approved, rejected, pending = get_user_master_status_counts(selected_user_id)

    c1, c2, c3 = st.columns(3)
    c1.metric("Approved", approved)
    c2.metric("Rejected", rejected)
    c3.metric("Pending", pending)

    submissions = get_user_master_submissions_admin(selected_user_id)

    if submissions:
        for sub in submissions:
            module_name = sub.get("module")

            if module_name:
                module_label = (sub.get("module") or "Unknown").replace("_", " ").title()
            else:
                module_label = "Unknown Module"

            status = sub["status"]

            if status == "APPROVED":
                badge = "🟢 APPROVED"
            elif status == "REJECTED":
                badge = "🔴 REJECTED"
            else:
                badge = "🟡 PENDING"

            with st.expander(f"{module_label} - {badge}"):
                full_data = get_full_submission_data(sub["id"])
                for section_name, df_section in full_data.items():
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
