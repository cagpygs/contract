import streamlit as st
import datetime
import plotly.express as px
from auth import login
from crud import *

st.set_page_config(layout="wide")


st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

html, body, [class*="css"]  {
    font-family: 'Inter', sans-serif;
}
h1, h2, h3 {
    font-family: 'Inter', sans-serif;
    font-weight: 700;
}
/* Background */
.stApp {
    background-color:#f8fafc;
}

/* Container spacing */
.block-container {
    padding-top: 2rem;
    padding-bottom: 3rem;
}

/* Dashboard header */
h1, h2, h3 {
    font-weight:600;
}

/* Card style */
.dashboard-card {
    background:white;
    padding:20px;
    border-radius:14px;
    box-shadow:0 8px 25px rgba(0,0,0,0.06);
    margin-bottom:20px;
}

/* Timeline */
.timeline {
    border-left: 3px solid #2563eb;
    margin-left: 15px;
    padding-left: 20px;
}

.timeline-item {
    position: relative;
    margin-bottom: 18px;
}

.timeline-item::before {
    content: "";
    position: absolute;
    left: -27px;
    top: 5px;
    width: 14px;
    height: 14px;
    border-radius: 50%;
}

/* Timeline colors */
.submitted::before { background:#3b82f6; }
.approved::before { background:#10b981; }
.rejected::before { background:#ef4444; }
.pending::before { background:#f59e0b; }

/* Progress bar */
.custom-progress {
    background:#e5e7eb;
    border-radius:10px;
    height:14px;
    width:100%;
    margin-top:10px;
}

.custom-progress-fill {
    height:100%;
    border-radius:10px;
    text-align:right;
    padding-right:8px;
    font-size:11px;
    font-weight:600;
    color:white;
    line-height:14px;
}



/* Tables */
[data-testid="stDataFrame"] {
    border-radius:12px;
    overflow:hidden;
}

/* Expanders */
.streamlit-expanderHeader {
    font-size:16px;
    font-weight:600;
}

/* Tabs */
button[data-baseweb="tab"] {
    font-size:20px;
    font-weight:600;
}

button[data-baseweb="tab"][aria-selected="true"] {
    color:#2563eb;
    border-bottom:3px solid #2563eb;
    box-shadow: 0 4px 12px rgba(37,99,235,0.3);
    font-weight:700;
}
.stButton > button {
    height: 50px;
    font-size: 28px;
    font-weight: 800;
    border-radius: 14px;
    background: white;
    border: none;
    box-shadow: 0 8px 24px rgba(0,0,0,0.08);
    letter-spacing: 1px;
    font-family: 'Inter', sans-serif;
}

/* Hover animation */
.stButton > button:hover {
    transform: translateY(-6px);
    transition: 0.6s;
}

/* Card spacing */
.row-widget.stButton {
    margin-bottom: 10px;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>

/* Page background */
.block-container {
    padding-top: 3rem;
    padding-bottom: 3rem;
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

    # 🔥 Read estimate fields from first tab draft (DB-based, persistent)
    first_table = tables[0]
    first_table_draft = get_user_draft(first_table, user_id)

    first_table = tables[0]

    for i, table in enumerate(tables):

        with tabs[i]:

            is_master_form = (table == first_table)

            columns = get_table_columns(table, is_admin=False)
            restore_draft_to_session(table, columns, user_id)

            form_data = {}
            filled_fields = 0

            # 🔥 USE FORM ONLY FOR ADMIN FINANCIAL SANCTION
            if table == first_table:

                with st.form(f"form_{table}"):

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

                    submitted = st.form_submit_button("💾 Save Section")

                # 🔥 VALIDATION OUTSIDE FORM
                if submitted:

                    estimate_number = form_data.get("estimate_number")
                    year_of_estimate = form_data.get("year_of_estimate")

                    if not estimate_number:
                        st.error("Estimate Number is mandatory")
                        st.stop()

                    if not year_of_estimate:
                        st.error("Year of Estimate is mandatory")
                        st.stop()

                    save_draft_record(table, form_data, user_id)
                    st.success("Admin Financial Sanction saved successfully ✅")
                    st.rerun()

            else:
                # 🔹 OTHER SECTIONS (keep old logic)

                col1, col2 = st.columns(2)

                for index, col_info in enumerate(columns):

                    col = col_info["column_name"]
                    dtype = col_info["data_type"]
                    key = f"{table}_{col}"

                    target_col = col1 if index % 2 == 0 else col2

                    with target_col:

                        # 🔥 Auto-fill estimate fields from first tab
                        if table != first_table and col in ["estimate_number", "year_of_estimate"]:

                            value = None

                            if first_table_draft:
                                value = first_table_draft.get(col)

                            if value is not None:
                                st.session_state[key] = value

                            # 🔥 Render based on datatype
                            if dtype in ("integer", "bigint", "smallint"):
                                st.number_input(col, step=1, disabled=True, key=key)

                            elif dtype in ("numeric", "double precision", "real"):
                                st.number_input(col, disabled=True, key=key)

                            elif dtype == "date":
                                st.date_input(col, disabled=True, key=key)

                            else:
                                st.text_input(col, disabled=True, key=key)

                            form_data[col] = value
                            continue



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
                    # 🔥 Format table name nicely like tabs
                    clean_name = section_name.replace(module_name + "_", "").replace("_", " ").title()

                    st.markdown(f"### 📄 {clean_name}")
                    st.dataframe(df_section, use_container_width=True)

    else:
        st.info("No submissions yet.")

# =====================================================
# ================= ADMIN SIDE ========================
# =====================================================

if is_admin:

    # UI filter state
    if "status_filter" not in st.session_state:
        st.session_state.status_filter = "ALL"



    st.subheader("📋 Admin Panel")

    users_df = get_users_with_data()
    selected_user = st.selectbox("Select User", users_df["username"])
    user_row = users_df[users_df["username"] == selected_user].iloc[0]
    selected_user_id = int(user_row["id"])

    approved, rejected, pending = get_user_master_status_counts(selected_user_id)

    total = approved + rejected + pending
    column1, column2, column3, column4 = st.columns(4)

    with column1:
        # st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
        # st.metric("📦 Total", total)
        if st.button(f"📦  Total\n\n{total}", use_container_width=True):
            st.session_state.status_filter = "ALL"
        st.markdown('</div>', unsafe_allow_html=True)

    with column2:
        # st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
        # st.metric("🟢 Approved", approved)
        if st.button(f"🟢  Approved\n\n{approved}", use_container_width=True):
            st.session_state.status_filter = "APPROVED"

        st.markdown('</div>', unsafe_allow_html=True)

    with column3:
        # st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
        # st.metric("🔴 Rejected", rejected)
        if st.button(f"🔴  Rejected\n\n{rejected}", use_container_width=True):
            st.session_state.status_filter = "REJECTED"
        st.markdown('</div>', unsafe_allow_html=True)

    with column4:
        # st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
        # st.metric("🟡 Pending", pending)
        if st.button(f"🟡  Pending\n\n{pending}", use_container_width=True):
            st.session_state.status_filter = "PENDING"
        st.markdown('</div>', unsafe_allow_html=True)

    submissions = get_user_master_submissions_admin(selected_user_id)

    if submissions:
        for sub in submissions:

            if st.session_state.status_filter != "ALL":
                if sub["status"] != st.session_state.status_filter:
                    continue


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


            # this is for Time Line
            st.markdown("### 🕒Form Submission Timeline")

            # Draft Created (we assume created_at exists in master_submission)
            created_at = sub.get("created_at")

            if created_at:
                st.markdown(f"📝 **Submitted:** {created_at}")

            # Status-based timeline
            if sub["status"] == "APPROVED":
                approved_at = sub.get("approved_at")
                if approved_at:
                    st.markdown(f"🟢 **Approved:** {approved_at}")

            elif sub["status"] == "REJECTED":
                rejected_at = sub.get("rejected_at")
                reason = sub.get("rejection_reason")

                if rejected_at:
                    st.markdown(f"🔴 **Rejected:** {rejected_at}")

                if reason:
                    st.markdown(f"💬 **Reason:** {reason}")

            else:
                st.markdown("🟡 **Pending Review**")

            st.markdown("---")

            # this is for Time Line ENDS

            with st.expander(
                    f"📄 {module_label} - Form | {badge}",
                    expanded=False
            ):
                full_data = get_full_submission_data(sub["id"])
                for section_name, df_section in full_data.items():
                    # 🔥 Format table name nicely like tabs
                    clean_name = section_name.replace(module_name + "_", "").replace("_", " ").title()

                    st.markdown(f"### 📄 {clean_name}")
                    st.dataframe(df_section, use_container_width=True)

                st.markdown("---")
                st.markdown("### ⚖ Review Decision")
                colA, colB, colC = st.columns([1, 2, 1])



                if colA.button("✅ Approve", key=f"a{sub['id']}"):
                    approve_master_submission(sub["id"])
                    st.rerun()

                reason = colB.text_input("Rejection Reason", key=f"r{sub['id']}")
                if colB.button("❌ Reject", key=f"rej{sub['id']}"):
                    reject_master_submission(sub["id"], reason)
                    st.rerun()

                    # 🔥 PDF HERE
                pdf = export_master_submission_pdf(sub["id"])

                st.download_button(
                        "Download Full Application PDF",
                        pdf,
                        file_name=f"{selected_user}_cycle_{sub['cycle']}.pdf",
                        mime="application/pdf",
                        key=f"pdf_{sub['id']}"
                    )

    else:
        st.info("No submissions found.")
