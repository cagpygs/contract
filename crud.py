import psycopg2
import pandas as pd
import streamlit as st
from psycopg2 import sql
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
import io


# ================= DB CONNECTION =================
def get_connection():
return psycopg2.connect(
host=os.environ.get("DB_HOST"),
database=os.environ.get("DB_NAME"),
user=os.environ.get("DB_USER"),
password=os.environ.get("DB_PASSWORD"),
port=os.environ.get("DB_PORT"),
sslmode="require"
)


# ================= LOAD TABLES =================
def get_all_tables(conn=None):
    close_conn = False

    if conn is None:
        conn = get_connection()
        close_conn = True

    df = pd.read_sql("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema='public'
        AND table_type='BASE TABLE'
        AND (
            table_name LIKE 'contract_management_%'
            OR table_name LIKE 'canal_performance_%'
        )
        ORDER BY table_name
    """, conn)

    if close_conn:
        conn.close()

    return df["table_name"].tolist()


# ================= GET NEXT CYCLE =================
def get_next_cycle(user_id, module):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT COALESCE(MAX(cycle), 0)
        FROM master_submission
        WHERE user_id=%s
        AND module=%s
    """, (user_id, module))

    last_cycle = cur.fetchone()[0]
    conn.close()

    return last_cycle + 1


# ================= SAVE DRAFT =================
def save_draft_record(table, data, user_id):

    user_id = int(user_id)
    conn = get_connection()
    cur = conn.cursor()

    clean_cols = []
    clean_vals = []

    for k, v in data.items():
        if not k or not k.strip():
            continue

        clean_cols.append(k)

        if v == "" or v is None:
            clean_vals.append(None)
        elif isinstance(v, (list, tuple)):
            clean_vals.append(str(v))
        else:
            clean_vals.append(v)

    if not clean_cols:
        conn.close()
        return

    # Escape % in column names
    safe_cols = [col.replace('%', '%%') for col in clean_cols]

    # STEP 1: Fetch existing draft rows
    check_query = sql.SQL("""
        SELECT id FROM {table}
        WHERE created_by=%s AND is_draft=TRUE
        ORDER BY id DESC
    """).format(
        table=sql.Identifier(table)
    )

    cur.execute(check_query, (user_id,))
    existing_rows = cur.fetchall()

    if existing_rows:

        latest_id = existing_rows[0][0]

        # Delete older drafts
        if len(existing_rows) > 1:
            delete_query = sql.SQL("""
                DELETE FROM {table}
                WHERE created_by=%s
                AND is_draft=TRUE
                AND id<>%s
            """).format(
                table=sql.Identifier(table)
            )

            cur.execute(delete_query, (user_id, latest_id))

        # Update latest draft
        set_clause = sql.SQL(', ').join(
            sql.SQL("{} = %s").format(sql.Identifier(col))
            for col in safe_cols
        )

        update_query = sql.SQL("""
            UPDATE {table}
            SET {fields}
            WHERE id=%s
        """).format(
            table=sql.Identifier(table),
            fields=set_clause
        )

        cur.execute(update_query, clean_vals + [latest_id])

    else:
        # Insert new draft
        insert_query = sql.SQL("""
            INSERT INTO {table} ({fields}, created_by, is_draft)
            VALUES ({placeholders}, %s, TRUE)
        """).format(
            table=sql.Identifier(table),
            fields=sql.SQL(', ').join(map(sql.Identifier, safe_cols)),
            placeholders=sql.SQL(', ').join(
                sql.Placeholder() for _ in safe_cols
            )
        )

        cur.execute(insert_query, clean_vals + [user_id])

    conn.commit()
    conn.close()


# ================= CREATE MASTER SUBMISSION =================
def create_master_submission(user_id, module, tables):

    user_id = int(user_id)
    cycle = get_next_cycle(user_id, module)

    conn = get_connection()
    cur = conn.cursor()

    # Create module-specific master
    cur.execute("""
        INSERT INTO master_submission (user_id, cycle, status, module)
        VALUES (%s, %s, 'PENDING', %s)
        RETURNING id
    """, (user_id, cycle, module))

    master_id = cur.fetchone()[0]

    # Attach drafts only for this module
    for table in tables:

        cur.execute(f"""
            UPDATE "{table}"
            SET is_draft=FALSE,
                master_id=%s
            WHERE created_by=%s
            AND is_draft=TRUE
        """, (master_id, user_id))

    conn.commit()
    conn.close()


# ================= GET USER MASTER SUBMISSIONS =================
def get_user_master_submissions(user_id, module):

    conn = get_connection()

    df = pd.read_sql("""
        SELECT *
        FROM master_submission
        WHERE user_id=%s
        AND module=%s
        ORDER BY cycle DESC
    """, conn, params=[user_id, module])

    conn.close()
    return df.to_dict("records")

def get_user_master_submissions_admin(user_id):

    conn = get_connection()

    df = pd.read_sql("""
        SELECT *
        FROM master_submission
        WHERE user_id=%s
        ORDER BY cycle DESC
    """, conn, params=[user_id])

    conn.close()
    return df.to_dict("records")

# ================= GET FULL SUBMISSION DATA =================
def get_full_submission_data(master_id):

    conn = get_connection()
    tables = get_all_tables(conn)

    full_data = {}

    for table in tables:
        df = pd.read_sql(f"""
            SELECT *
            FROM "{table}"
            WHERE master_id=%s
        """, conn, params=[master_id])

        if not df.empty:
            full_data[table] = df

    conn.close()
    return full_data


# ================= APPROVE MASTER =================
def approve_master_submission(master_id):

    conn = get_connection()
    cur = conn.cursor()

    # 1️⃣ Update master table
    cur.execute("""
        UPDATE master_submission
        SET status='APPROVED',
            approved_at=NOW()
        WHERE id=%s
    """, (master_id,))

    # 2️⃣ Update all related form tables
    tables = get_all_tables(conn)

    for table in tables:

        update_query = sql.SQL("""
            UPDATE {table}
            SET approval_status='APPROVED'
            WHERE master_id=%s
        """).format(
            table=sql.Identifier(table)
        )

        cur.execute(update_query, (master_id,))

    conn.commit()
    conn.close()


# ================= REJECT MASTER =================
def reject_master_submission(master_id, reason):

    conn = get_connection()
    cur = conn.cursor()

    # 1️⃣ Update master table
    cur.execute("""
        UPDATE master_submission
        SET status='REJECTED',
            rejection_reason=%s,
            rejected_at=NOW()
        WHERE id=%s
    """, (reason, master_id))

    # 2️⃣ Update all related form tables
    tables = get_all_tables(conn)

    for table in tables:

        update_query = sql.SQL("""
            UPDATE {table}
            SET approval_status='REJECTED'
            WHERE master_id=%s
        """).format(
            table=sql.Identifier(table)
        )

        cur.execute(update_query, (master_id,))

    conn.commit()
    conn.close()


# ================= USER PROGRESS =================
def get_user_progress(user_id, tables):

    user_id = int(user_id)

    conn = get_connection()
    cur = conn.cursor()

    total = len(tables)
    completed = 0

    for table in tables:

        cur.execute(f"""
            SELECT 1 FROM "{table}"
            WHERE created_by=%s
            AND is_draft=TRUE
            LIMIT 1
        """, (user_id,))

        if cur.fetchone():
            completed += 1

    conn.close()

    percentage = int((completed / total) * 100) if total > 0 else 0

    return percentage, completed, total


# ================= INCOMPLETE SECTIONS =================
def get_incomplete_forms(user_id, tables):

    user_id = int(user_id)
    conn = get_connection()
    cur = conn.cursor()

    incomplete = []

    for table in tables:

        # Get business columns (ignore system fields)
        columns = get_table_columns(table, is_admin=False)
        business_cols = [col["column_name"] for col in columns]

        if not business_cols:
            continue

        # Condition: at least one business field filled
        conditions = " OR ".join(
            [f"{col} IS NOT NULL" for col in business_cols]
        )

        query = f"""
            SELECT 1 FROM "{table}"
            WHERE created_by=%s
            AND is_draft=TRUE
            AND ({conditions})
            LIMIT 1
        """

        cur.execute(query, (user_id,))
        row = cur.fetchone()

        if not row:
            incomplete.append(table)

    conn.close()
    return incomplete


# ================= STATUS COUNTS =================
def get_user_master_status_counts(user_id):

    user_id = int(user_id)

    conn = get_connection()

    df = pd.read_sql("""
        SELECT status, COUNT(*)
        FROM master_submission
        WHERE user_id=%s
        GROUP BY status
    """, conn, params=[user_id])

    conn.close()

    approved = rejected = pending = 0

    for _, row in df.iterrows():
        if row["status"] == "APPROVED":
            approved = row["count"]
        elif row["status"] == "REJECTED":
            rejected = row["count"]
        else:
            pending = row["count"]

    return approved, rejected, pending


# ================= EXPORT MASTER PDF =================
def export_master_submission_pdf(master_id):

    conn = get_connection()

    # 🔥 Fetch master status and rejection reason
    cur = conn.cursor()
    cur.execute("""
        SELECT status, rejection_reason, module
        FROM master_submission
        WHERE id=%s
    """, (master_id,))

    master_row = cur.fetchone()

    status = master_row[0] if master_row else ""
    rejection_reason = master_row[1] if master_row else None

    tables = get_all_tables(conn)

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=20,
        leftMargin=20,
        topMargin=20,
        bottomMargin=20
    )

    elements = []
    styles = getSampleStyleSheet()

    # 🔥 Add Application Status at top
    elements.append(Paragraph(f"<b>Application Status:</b> {status}", styles["Heading2"]))
    elements.append(Spacer(1, 12))

    # 🔥 If Rejected → Show Reason
    if status == "REJECTED" and rejection_reason:
        elements.append(
            Paragraph(
                f"<b>Rejection Reason:</b> {rejection_reason}",
                styles["Normal"]
            )
        )
        elements.append(Spacer(1, 20))

    wrap_style = ParagraphStyle(
        name="wrap",
        parent=styles["Normal"],
        fontSize=7,
        leading=9
    )

    page_width = landscape(A4)[0] - 40
    MAX_COLS_PER_TABLE = 8   # 🔥 change if needed

    for table in tables:

        df = pd.read_sql(
            f'SELECT * FROM "{table}" WHERE master_id=%s',
            conn,
            params=[master_id]
        )

        if df.empty:
            continue

        elements.append(Paragraph(f"<b>{table}</b>", styles["Heading2"]))
        elements.append(Spacer(1, 10))

        total_cols = len(df.columns)

        # 🔥 Split into column chunks
        for start in range(0, total_cols, MAX_COLS_PER_TABLE):

            end = start + MAX_COLS_PER_TABLE
            df_chunk = df.iloc[:, start:end]

            data = []

            # Header
            header = [Paragraph(str(col), wrap_style) for col in df_chunk.columns]
            data.append(header)

            # Rows
            for row in df_chunk.itertuples(index=False):
                row_data = [
                    Paragraph("" if val is None else str(val), wrap_style)
                    for val in row
                ]
                data.append(row_data)

            num_cols = len(df_chunk.columns)
            col_width = page_width / num_cols

            table_obj = Table(
                data,
                colWidths=[col_width] * num_cols,
                repeatRows=1
            )

            table_obj.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('FONTSIZE', (0, 0), (-1, -1), 7),
                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ]))

            elements.append(table_obj)
            elements.append(Spacer(1, 15))

    if not elements:
        elements.append(Paragraph("No Data Available", styles["Normal"]))

    doc.build(elements)

    conn.close()
    buffer.seek(0)
    return buffer

# ================= GET TABLE COLUMNS =================
def get_table_columns(table, is_admin=False):

    conn = get_connection()

    query = """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema='public'
        AND table_name=%s
        ORDER BY ordinal_position
    """

    df = pd.read_sql(query, conn, params=[table])
    conn.close()

    system_fields = (
        "id",
        "created_by",
        "is_draft",
        "master_id",
        "submitted_at",
        "approval_status",
        "approved_at",
        "submission_cycle",
        "created_at",
        "status",
        "approved_by",
        "draft_id"
    )

    if not is_admin:
        df = df[~df["column_name"].isin(system_fields)]

    return df.to_dict("records")


def get_user_draft(table, user_id):

    conn = get_connection()
    cur = conn.cursor()

    query = sql.SQL("""
        SELECT * FROM {table}
        WHERE created_by=%s AND is_draft=TRUE
        ORDER BY id DESC
        LIMIT 1
    """).format(
        table=sql.Identifier(table)
    )

    cur.execute(query, (user_id,))
    row = cur.fetchone()

    if not row:
        conn.close()
        return None

    columns = [desc[0] for desc in cur.description]

    conn.close()

    return dict(zip(columns, row))

def get_users_with_data():

    conn = get_connection()

    # Users with submitted master
    submitted_query = """
        SELECT DISTINCT user_id FROM master_submission
    """

    submitted_users = pd.read_sql(submitted_query, conn)["user_id"].tolist()

    # Users with drafts in any table
    tables = get_all_tables(conn)
    draft_users = set()

    for table in tables:
        q = f'SELECT DISTINCT created_by FROM "{table}" WHERE is_draft=TRUE'
        df = pd.read_sql(q, conn)
        draft_users.update(df["created_by"].tolist())

    all_users = set(submitted_users) | draft_users

    if not all_users:
        conn.close()
        return pd.DataFrame(columns=["id", "username"])

    users_query = f"""
        SELECT id, username
        FROM users
        WHERE id IN ({','.join(map(str, all_users))})
        ORDER BY username
    """

    users_df = pd.read_sql(users_query, conn)
    conn.close()

    return users_df

def can_user_edit(master_id):
    status = get_master_status(master_id)

    if status in ["DRAFT", "REJECTED"]:
        return True

    return False

def get_total_master_submissions():
            conn = get_connection()
            cur = conn.cursor()
            try:
                cur.execute("SELECT COUNT(*) FROM master_submission;")
                result = cur.fetchone()[0]
                return result
            finally:
                cur.close()
                conn.close()

def get_global_status_counts():
                    conn = get_connection()
                    cur = conn.cursor()
                    try:
                        cur.execute("""
                            SELECT 
                                SUM(CASE WHEN status = 'APPROVED' THEN 1 ELSE 0 END) AS approved,
                                SUM(CASE WHEN status = 'REJECTED' THEN 1 ELSE 0 END) AS rejected,
                                SUM(CASE WHEN status = 'PENDING' THEN 1 ELSE 0 END) AS pending
                            FROM master_submission;
                        """)
                        result = cur.fetchone()
                        approved = result[0] or 0
                        rejected = result[1] or 0
                        pending = result[2] or 0
                        return approved, rejected, pending
                    finally:
                        cur.close()
                        conn.close()



def get_monthly_submission_trend():
                            conn = get_connection()
                            try:
                                query = """
                                    SELECT 
                                        TO_CHAR(created_at, 'YYYY-MM') AS month,
                                        SUM(CASE WHEN status = 'APPROVED' THEN 1 ELSE 0 END) AS approved,
                                        SUM(CASE WHEN status = 'REJECTED' THEN 1 ELSE 0 END) AS rejected,
                                        SUM(CASE WHEN status = 'PENDING' THEN 1 ELSE 0 END) AS pending
                                    FROM master_submission
                                    GROUP BY month
                                    ORDER BY month;
                                """
                                df = pd.read_sql(query, conn)
                                return df
                            finally:
                                conn.close()


# ================= RESTORE DRAFT =================
def restore_draft_to_session(table, columns, user_id):

    draft_data = get_user_draft(table, user_id)

    if not draft_data:
        return

    for col_info in columns:

        col = col_info["column_name"]
        dtype = col_info["data_type"]

        key = f"{table}_{col}"

        if key in st.session_state:
            continue

        if col not in draft_data:
            continue

        value = draft_data[col]

        if value is None:
            continue

        if dtype in ("integer", "bigint", "smallint"):
            st.session_state[key] = int(value)

        elif dtype in ("numeric", "double precision", "real"):
            st.session_state[key] = float(value)

        elif dtype == "date":
            st.session_state[key] = value

        else:
            st.session_state[key] = str(value)

def get_master_status(user_id, module_name):
    conn = get_connection()
    cur = conn.cursor()

    query = """
        SELECT status
        FROM master_submission
        WHERE user_id = %s
        AND module = %s
        ORDER BY created_at DESC
        LIMIT 1
    """

    cur.execute(query, (user_id, module_name))
    result = cur.fetchone()

    cur.close()
    conn.close()

    if result:
        return result[0]
    return None


def get_estimate_details(user_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT estimate_number, year_of_estimate
        FROM contract_management_admin_financial_sanction
        WHERE user_id=%s
        LIMIT 1
    """, (user_id,))

    row = cur.fetchone()
    conn.close()

    if row:
        return {
            "estimate_number": row[0],
            "year_of_estimate": row[1]
        }

    return None



