import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import numpy as np

# --- CONFIG ---
st.set_page_config(page_title="Moyy Sheets", layout="wide", page_icon="🏭")

# --- ADVANCED CSS FOR FULL-WIDTH NAV ---
st.markdown("""
    <style>
    /* Side bar background color */
    [data-testid="stSidebar"] {
        background-color: #1E293B;
    }
    
    /* Title styling */
    .sidebar-title {
        color: #F8FAFC;
        font-size: 22px;
        font-weight: 800;
        padding-bottom: 20px;
        text-align: center;
    }

    /* Make all sidebar buttons fill width and look uniform */
    div.stButton > button {
        width: 100% !important;
        border-radius: 0px !important;
        height: 3.5em !important;
        background-color: #1E293B !important;
        color: #CBD5E1 !important;
        border: none !important;
        text-align: left !important;
        padding-left: 25px !important;
        font-size: 16px !important;
        transition: all 0.3s ease;
        border-left: 4px solid transparent !important;
    }

    /* Hover effect */
    div.stButton > button:hover {
        background-color: #334155 !important;
        color: #FFFFFF !important;
        border-left: 4px solid #3B82F6 !important;
    }

    /* Selected state styling (Logic handled via session state) */
    div.stButton > button:focus {
        background-color: #334155 !important;
        color: #3B82F6 !important;
        border-left: 4px solid #3B82F6 !important;
        box-shadow: none !important;
    }
    
    /* Hide the default radio button area if any exists */
    [data-testid="stSidebarNav"] {display: none;}
    </style>
    """, unsafe_allow_html=True)

# --- NAVIGATION LOGIC ---
if 'page' not in st.session_state:
    st.session_state.page = "Dashboard"

def set_page(name):
    st.session_state.page = name

# --- DATABASE CONNECTION ---
DB_PATH = "test_db.db"
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def run_action(query, params=()):
    """Executes a write/update query safely."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor

# --- SIDEBAR CONSTRUCTION ---
with st.sidebar:
    st.markdown('<div class="sidebar-title">Moyy Sheets</div>', unsafe_allow_html=True)
    
    # Navigation Stack
    st.button("Dashboard", on_click=set_page, args=("Dashboard",))
    st.button("Programs", on_click=set_page, args=("Programs",))
    st.button("Planning", on_click=set_page, args=("Planning",))
    st.button("Orders", on_click=set_page, args=("Orders",))
    st.button("Inventory", on_click=set_page, args=("Inventory",))
    
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("---")
    st.button("⚙️  Settings", on_click=set_page, args=("Settings",))
    
    st.markdown(f"""
        <div style='position: fixed; bottom: 20px; left: 20px; color: #94A3B8; font-size: 12px;'>
            User: Admin<br>
            Server: Test
        </div>
    """, unsafe_allow_html=True)

# --- PAGE CONTENT ROUTING ---

if st.session_state.page == "Dashboard":
    st.title("Plant Overview")
    cols = st.columns(4)
    cols[0].metric("Pending Orders", "14")
    cols[1].metric("Active Programs", "3")
    cols[2].metric("Stock Tonnage", "420 T")
    cols[3].metric("Wastage", "2.4%")

elif st.session_state.page == "Programs":
    st.title("Active Production")
    # Tallying logic goes here

elif st.session_state.page == "Planning":
    st.title("📅 Production Planning")
    st.markdown("---")

    conn = get_connection()

    # 1. SELECT RECIPE FIRST
    st.subheader("1. Select Board Specification")
    recipes_df = pd.read_sql("""
        SELECT grade_id, board_grade || ' ' || flute as name, board_grade, flute 
        FROM grade_master
    """, conn)

    if recipes_df.empty:
        st.warning("⚠️ No Recipes found. Please add Board Grades in Master Data first.")
    else:
        recipe_options = dict(zip(recipes_df['name'], recipes_df['grade_id']))
        selected_recipe_name = st.selectbox("Choose Grade/Flute for this Run", options=list(recipe_options.keys()))
        
        # Get recipe details for the chosen grade
        recipe_id = recipe_options[selected_recipe_name]
        recipe_info = pd.read_sql("SELECT * FROM grade_master WHERE grade_id = ?", conn, params=(recipe_id,)).iloc[0]

        st.info(f"📋 **Target Recipe:** {selected_recipe_name}")

        # 2. FILTER ORDERS BASED ON THE GRADE
        st.subheader("2. Select Compatible Orders")
        
        # We only show orders that aren't 'Completed' or 'Cancelled'
        # In a real scenario, we might also filter orders by the specific paper grade required
        orders_query = """
            SELECT o.order_id, o.order_number, c.customer_name, o.required_lineal, o.status
            FROM orders o
            JOIN customers c ON o.customer_id = c.customer_id
            WHERE o.status = 'Pending'
        """
        pending_orders = pd.read_sql(orders_query, conn)

        if pending_orders.empty:
            st.write("No pending orders available.")
        else:
            # Multi-select for combining orders
            order_list = [f"{r['order_number']} | {r['customer_name']} ({r['required_lineal']} ft)" for _, r in pending_orders.iterrows()]
            selected_labels = st.multiselect("Combine Orders into this Run:", options=order_list)

            if selected_labels:
                # Extract Order IDs from selection
                selected_order_nos = [label.split(" | ")[0] for label in selected_labels]
                to_combine = pending_orders[pending_orders['order_number'].isin(selected_order_nos)]
                
                total_run_lineal = to_combine['required_lineal'].sum()
                
                # Summary Box
                with st.container(border=True):
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Orders Combined", len(to_combine))
                    col2.metric("Total Lineal", f"{total_run_lineal} ft")
                    col3.metric("Flute", recipe_info['flute'])

                # 3. CREATE THE PROGRAM
                st.subheader("3. Finalize Run Details")
                with st.form("create_run"):
                    p_name = st.text_input("Program / Run ID", value=f"RUN-{datetime.now().strftime('%m%d-%H%M')}")
                    m_width = st.number_input("Minimum Required Roll Width (in)", min_value=0.0, step=0.1)
                    
                    if st.form_submit_button("🚀 Create Production Program"):
                        try:
                            # A. Insert the Program
                            prog_query = """
                                INSERT INTO programs (
                                    program_name, board_grade, flute, target_width, 
                                    top_liner_id, medium_id, bottom_liner_id, target_lineal, status
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Active')
                            """
                            # We use IDs from the grade_master recipe
                            params = (
                                p_name, recipe_info['board_grade'], recipe_info['flute'], m_width,
                                recipe_info['top_liner_id'], recipe_info['medium_id'], recipe_info['bottom_liner_id'],
                                total_run_lineal
                            )
                            
                            with get_connection() as conn:
                                cursor = conn.cursor()
                                cursor.execute(prog_query, params)
                                new_program_id = cursor.lastrowid
                                
                                # B. Link Orders to the Program and update their status
                                for _, row in to_combine.iterrows():
                                    cursor.execute("INSERT INTO program_items (program_id, order_id) VALUES (?, ?)", 
                                                    (new_program_id, row['order_id']))
                                    cursor.execute("UPDATE orders SET status = 'Scheduled' WHERE order_id = ?", (row['order_id'],))
                                
                                conn.commit()
                                st.success(f"Successfully created Program {p_name} and linked {len(to_combine)} orders.")
                                st.balloons()
                        except Exception as e:
                            st.error(f"Error creating program: {e}")

elif st.session_state.page == "Orders":
    st.title("Order Management")
    # Customer orders list

elif st.session_state.page == "Inventory":
    st.title("Roll Inventory")
    
    # --- TOP METRICS ---
    conn = get_connection()
    # Metric Fix: Convert total_lineal to feet for the header metric
    total_rolls = pd.read_sql("SELECT COUNT(*) as count FROM paper_rolls WHERE status='available'", conn).iloc[0]['count']
    total_lineal_m = pd.read_sql("SELECT SUM(remaining_lineal) as total FROM paper_rolls WHERE status='available'", conn).iloc[0]['total'] or 0
    total_lineal_ft = int(total_lineal_m * 3.28084)

    m1, m2, m3 = st.columns(3)
    m1.metric("Available Rolls", total_rolls)
    m2.metric("Total Lineal on Hand", f"{total_lineal_ft:,} m")
    m3.metric("Warehouse Status", "Normal")

    tab1, tab2 = st.tabs(["🔍 Stock Lookup", "📥 Receive New Rolls"])

    with tab1:
        col1, col2, col3 = st.columns([2, 1, 1])
        search_query = col1.text_input("🔍 Search Serial or Paper Code")
        min_width = col2.number_input("Min Width (in)", value=0.0)
        status_filter = col3.selectbox("Status", ["Available", "Locked", "Depleted"])

        query = """
            SELECT 
                pr.internal_serial AS 'Serial',
                p.paper_code AS 'Grade',
                p.paper_type AS 'Paper Type',
                s.name AS 'Supplier',
                ROUND(pr.width_mm / 25.4, 1) AS 'Width (in)',
                pr.remaining_lineal AS 'Length (m)',
                pr.original_lineal AS 'original_m',
                CASE 
                    WHEN pr.assigned_program_id IS NOT NULL THEN 'LOCKED'
                    ELSE 'OPEN'
                END AS 'Availability',
                prog.program_name AS 'Assigned To'
            FROM paper_rolls pr
            JOIN paper p ON pr.paper_id = p.paper_id
            JOIN suppliers s ON pr.supplier_id = s.supplier_id
            LEFT JOIN programs prog ON pr.assigned_program_id = prog.program_id
            WHERE pr.status = ?
        """
        
        df_inv = pd.read_sql(query, conn, params=(status_filter.lower(),))
        
        # Apply filters
        if search_query:
            df_inv = df_inv[
                df_inv['Serial'].str.contains(search_query, case=False, na=False) | 
                df_inv['Grade'].str.contains(search_query, case=False, na=False)
            ]
        
        if min_width > 0:
            df_inv = df_inv[df_inv['Width (in)'] >= min_width]

        # --- THE VITAL FIX BLOCK ---
        if not df_inv.empty:
            df_display = df_inv.copy()
            df_display['fill_ratio'] = (df_display['Length (m)'] / df_display['original_m']).fillna(0)

            df_display['fill_ratio'] = df_display['fill_ratio'].clip(0, 1)

            st.dataframe(
                df_display,
                column_config={
                    "original_ft": None, # Hide the dynamic max from view
                    "fill_ratio": st.column_config.ProgressColumn(
                        "Roll Capacity",
                        help="Fullness relative to this specific roll's original size",
                        format=" ",      # Hide the decimal number
                        min_value=0.0,
                        max_value=1.0    # Static 1.0 is stable, but the DATA is dynamic
                    ),
                    "Length (m)": "Current (m)" # The actual footage shows next to the bar
                }
            )
        else:
            st.info(f"No rolls found with status: {status_filter}")

    # --- TAB 2: RECEIVE NEW ROLLS ---
    with tab2:
        st.subheader("Register Incoming Paper")
        
        # Load masters for selectboxes
        paper_master = pd.read_sql("SELECT CAST(paper_id AS INTEGER) AS paper_id, paper_code, basis_weight_gsm, (paper_code || ' - ' || CAST(basis_weight_gsm AS TEXT) || ' gsm') AS paper_code_gsm FROM paper", conn)
        supp_master = pd.read_sql("SELECT CAST(supplier_id AS INTEGER) AS supplier_id, name FROM suppliers", conn)
        last_serial_df = pd.read_sql("SELECT max(internal_serial) as last_val FROM paper_rolls WHERE internal_serial LIKE 'R%'", conn)
        last_val = last_serial_df.iloc[0]['last_val']

        #Helper 
        def convert_df_to_imperial(df):
            # Create a copy so we don't modify the original metric data
            temp_df = df.copy()
            
            # 1. Convert Basis Weight (Inverse of your 4.882 rule)
            if 'basis_weight_gsm' in temp_df.columns:
                temp_df['basis_weight_gsm'] = np.ceil(temp_df['basis_weight_gsm'] / 4.882).astype(int)
            # 2. Convert Width (mm to inches)
            if 'width' in temp_df.columns:
                temp_df['width'] = np.ceil(temp_df['width'] / 25.4).astype(int)
                
            # 3. Convert Length (m to ft)
            if 'length' in temp_df.columns:
                temp_df['length'] = np.ceil(temp_df['length'] * 3.28084).astype(int)
                
            # 4. Convert Mass (kg to lbs)
            if 'weight' in temp_df.columns:
                temp_df['weight'] = np.ceil(temp_df['weight'] * 2.20462).astype(int)

            if 'basis_weight_gsm' in temp_df.columns:
                temp_df['paper_code_gsm'] = (
                    temp_df['paper_code'] + " - " + 
                    temp_df['basis_weight_gsm'].astype(str) + "#")

            return temp_df
        
        unit_mode = st.radio("Input Units", ["Metric (mm/kg)", "Imperial (in/lbs)"], horizontal=True)
        
        #Toggle Metric/Imperial
        if unit_mode == "Metric (mm/kg)":
            unit = ['g/m²', 'mm', 'm', 'kg']
            converted_df = paper_master
        else:
            unit = ["lb/1000ft²", 'in', 'ft', 'lbs']
            converted_df = convert_df_to_imperial(paper_master)
        
        #Convert Paper Code to List
        paper_code_option = converted_df['paper_code_gsm'].tolist()
        supplier_option = options=supp_master['name'].tolist()

        
        if paper_master.empty or supp_master.empty:
            st.error("⚠️ Setup Paper Grades and Suppliers in Master Data before receiving inventory.")

        else:
            with st.form("receiving_form", clear_on_submit=True):
                c1, c2 = st.columns(2)
                
                roll_prefix = datetime.now().strftime("R%y")

                def get_next_serial_number(prefix):
                    if not last_val:
                        return f"{prefix}-0001"
                    
                    try:
                        parts = last_val.split("-")
                        
                        if len(parts) < 2:
                            return f"{prefix}-0001"
                            
                        last_number = int(parts[1])
                        new_number = last_number + 1
                        return f"{prefix}-{str(new_number).zfill(4)}"
                        
                    except (ValueError, IndexError):
                        return f"{prefix}-0001"

                with c1:
                    roll_serial = st.text_input("Roll Serial (Scan Barcode)", placeholder="e.g,WKL, DTK")
                    #Generate new serial
                    new_serial = st.text_input("Serial Number", value=get_next_serial_number(roll_prefix))
                    paper_code_gsm = st.selectbox(f"Paper Grade ({unit[0]})", options=paper_code_option, index=1 if paper_code_option else None)
                    width = st.number_input("Roll Width (inches)", min_value=37, step=1)
                
                with c2:
                    supplier_choice = st.selectbox("Supplier", options=supplier_option, index=3 if supplier_option else None)
                    lineal = st.number_input(f"Total Lineal ({unit[2]})", min_value=0, step=10)
                    weight = st.number_input("Roll Weight (lbs/kg)", min_value=0)
                    location = st.text_input("Location", value="A1", placeholder="e.g, BAY-L1, BAY-L2")

                if st.form_submit_button("Receive Roll"):
                    if not roll_serial:
                        roll_serial = new_serial
                    if not new_serial:
                        st.error("Serial Number is required.")
                    else:
                        if unit_mode == "Imperial (in/lbs)":
                            lineal = int(lineal / 3.28084) # or x 0.3048
                            width = int(np.ceil(width * 25.4))
                        else:
                            if width < 760: # If width in mm less than 760(30 inches), do the conversion as input either typo or in imperial
                                width = int(np.ceil(width * 25.4))

                        p_map = dict(zip(converted_df['paper_code_gsm'], converted_df['paper_id']))
                        s_map = dict(zip(supp_master['name'], supp_master['supplier_id']))

                        p_id = int(p_map.get(paper_code_gsm))
                        s_id = int(s_map.get(supplier_choice))
                        
                        try:
                            run_action("""
                                INSERT INTO paper_rolls (roll_serial, internal_serial, paper_id, supplier_id, width_mm, weight, original_lineal, remaining_lineal, location, status)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'available')
                            """, (roll_serial, new_serial, p_id, s_id, width, weight, lineal, lineal, f"BAY-{location.upper()}"))
                            st.success(f"Roll {new_serial} successfully added to stock.")
                            # st.balloons()
                        except sqlite3.IntegrityError:
                            st.error(f"Error: A roll with serial {new_serial} already exists.")

elif st.session_state.page == "Settings":
    st.title("⚙️ Configuration")
    
    # Tabbed interface for clean organization
    tab1, tab2, tab3 = st.tabs(["Paper & Entities", "Grade Combination", "🛠️ System Tools"])

    # --- TAB 1: PAPERS, SUPPLIERS, CUSTOMERS ---
    with tab1:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📜 Paper Grades")
            with st.form("add_paper", clear_on_submit=True):
                p_code = st.text_input("Paper Code (e.g., 42PL, 23M, 175WKL)")
                b_weight = st.text_input("Basis Weight (e.g., 23# - 112, 33# - 161,35# - 175)")
                p_type = st.selectbox("Type", ["Liner", "Medium", "White Top"])
                if st.form_submit_button("Add Paper"):
                    if p_code:
                        run_action("INSERT OR IGNORE INTO paper (paper_code, paper_type, basis_weight_gsm) VALUES (?,?,?)", (p_code, p_type, b_weight))
                        st.success(f"Added {p_code}")
            
            # Display current papers
            papers_df = pd.read_sql("SELECT paper_code AS 'Paper Code', basis_weight_gsm AS 'Basis Weight', paper_type AS 'Paper Type' FROM paper", get_connection())
            st.dataframe(papers_df, width='stretch', hide_index=True)

        with col2:
            st.subheader("🏢 Suppliers & Customers")
            entry_type = st.radio("Entry Type", ["Supplier", "Customer"], horizontal=True)
            with st.form("add_entity", clear_on_submit=True):
                ent_name = st.text_input(f"{entry_type} Name")
                if st.form_submit_button(f"Add {entry_type}"):
                    if ent_name:
                        table = "suppliers" if entry_type == "Supplier" else "customers"
                        col = "name" if entry_type == "Supplier" else "customer_name"
                        run_action(f"INSERT OR IGNORE INTO {table} ({col}) VALUES (?)", (ent_name,))
                        st.success(f"Added {ent_name}")
            
            # Show existing
            st.write("---")
            if entry_type == "Supplier":
                st.dataframe(pd.read_sql("SELECT name FROM suppliers", get_connection()), width='stretch')
            else:
                st.dataframe(pd.read_sql("SELECT customer_name FROM customers", get_connection()), width='stretch')

    # --- TAB 2: GRADE MASTER (The Recipes) ---
    with tab2:
        st.subheader("Board Grade Combination")
        st.write("Define which papers make up a specific Board Grade/Flute combination.")
        
        # Load available papers for the dropdowns
        all_papers = pd.read_sql("SELECT paper_id, paper_code FROM paper", get_connection())
        p_map = dict(zip(all_papers['paper_code'], all_papers['paper_id']))
        
        if all_papers.empty:
            st.warning("Please add Paper Grades in the first tab before creating combination.")
        else:
            with st.form("recipe_form", clear_on_submit=True):
                c1, c2 = st.columns(2)
                bg_name = c1.text_input("Board Grade (e.g., ECT-32)")
                flute_name = c2.selectbox("Flute", ["A", "B", "C", "E", "BC", "EB"])
                
                r1, r2, r3 = st.columns(3)
                top = r1.selectbox("Top Liner", options=list(p_map.keys()))
                med = r2.selectbox("Medium", options=list(p_map.keys()))
                bot = r3.selectbox("Bottom Liner", options=list(p_map.keys()))
                
                if st.form_submit_button("Add Combination"):
                    run_action("""
                        INSERT OR REPLACE INTO grade_master 
                        (board_grade, flute, top_liner_id, medium_id, bottom_liner_id)
                        VALUES (?, ?, ?, ?, ?)
                    """, (bg_name, flute_name, p_map[top], p_map[med], p_map[bot]))
                    st.success(f"Combination for {bg_name} {flute_name} saved!")

            # Show current recipes
            st.write("### Current Combination")
            recipe_view = pd.read_sql("""
                SELECT gm.board_grade, gm.flute, p1.paper_code as 'Top Liner', p2.paper_code as Medium, p3.paper_code as 'Bottom Liner'
                FROM grade_master gm
                JOIN paper p1 ON gm.top_liner_id = p1.paper_id
                JOIN paper p2 ON gm.medium_id = p2.paper_id
                JOIN paper p3 ON gm.bottom_liner_id = p3.paper_id
            """, get_connection())
            st.dataframe(recipe_view, width='stretch', hide_index=True)

    # --- TAB 3: SYSTEM TOOLS (The 'Nuke' Button) ---
    with tab3:
        st.subheader("🛠️ Database Maintenance")
        st.warning("These actions are permanent. Use only during development.")
        
        if st.button("🔥 Factory Reset (Delete All Data)"):
            import os
            if os.path.exists("paper_app.db"):
                os.remove("paper_app.db")
                st.success("Database deleted. Please refresh the page to rebuild.")
                st.rerun()