import dash
from dash import html, dcc, Input, Output, State, clientside_callback, ClientsideFunction
import dash_bootstrap_components as dbc

# ========== APP SETUP ==========
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.BOOTSTRAP],
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no"}
    ],
    suppress_callback_exceptions=True
)
app.title = "PaperLink MES"

# ========== LAYOUT ==========
app.layout = html.Div([
    dcc.Location(id="url"),
    dcc.Store(id="sidebar-state", data={"collapsed": False, "mobile_open": False}),
    
    # Mobile overlay backdrop
    html.Div(id="sidebar-backdrop", className="sidebar-backdrop"),
    
    # Top navbar (mobile only)
    dbc.Navbar(
        dbc.Container([
            dbc.Button(
                html.I(className="bi bi-list fs-4"),
                id="mobile-menu-btn",
                color="link",
                className="text-white p-0 me-3"
            ),
            dbc.NavbarBrand([
                html.I(className="bi bi-stack me-2"),
                "PaperLink"
            ], className="text-white fw-bold"),
        ], fluid=True),
        color="dark",
        dark=True,
        className="mobile-navbar d-lg-none",
        style={"position": "fixed", "top": 0, "left": 0, "right": 0, "z-index": 1030}
    ),
    
    # Sidebar
    html.Div(
        [
            # Sidebar Header
            html.Div([
                html.Div([
                    html.I(className="bi bi-stack text-primary fs-3 me-2", id="sidebar-icon"),
                    html.Span("PaperLink", id="sidebar-brand", className="fs-4 fw-bold text-white"),
                ], className="d-flex align-items-center"),
                dbc.Button(
                    html.I(className="bi bi-list fs-5"),
                    id="desktop-toggle-btn",
                    color="link",
                    className="text-secondary p-0 d-none d-lg-block"
                ),
            ], className="sidebar-header d-flex justify-content-between align-items-center mb-4 px-3"),
            
            html.Hr(className="sidebar-divider"),

            # Navigation
            dbc.Nav(
                [
                    dbc.NavLink(
                        [
                            html.I(className="bi bi-grid-1x2 fs-5 me-3"),
                            html.Span("Dashboard", className="nav-label")
                        ],
                        href="/",
                        active="exact",
                        className="sidebar-nav-link"
                    ),
                    dbc.NavLink(
                        [
                            html.I(className="bi bi-cpu fs-5 me-3"),
                            html.Span("Programs", className="nav-label")
                        ],
                        href="/programs",
                        active="exact",
                        className="sidebar-nav-link"
                    ),
                    dbc.NavLink(
                        [
                            html.I(className="bi bi-clipboard-data fs-5 me-3"),
                            html.Span("Planning", className="nav-label")
                        ],
                        href="/planning",
                        active="exact",
                        className="sidebar-nav-link"
                    ),
                    dbc.NavLink(
                        [
                            html.I(className="bi bi-archive fs-5 me-3"),
                            html.Span("Inventory", className="nav-label")
                        ],
                        href="/inventory",
                        active="exact",
                        className="sidebar-nav-link"
                    ),
                ],
                vertical=True,
                className="flex-column sidebar-nav px-2"
            ),
            
            # Bottom section
            html.Div([
                html.Hr(className="sidebar-divider"),
                dbc.NavLink(
                    [
                        html.I(className="bi bi-gear fs-5 me-3"),
                        html.Span("Settings", className="nav-label")
                    ],
                    href="/settings",
                    active="exact",
                    className="sidebar-nav-link text-secondary"
                ),
            ], className="mt-auto px-2")
        ],
        id="sidebar",
        className="sidebar"
    ),

    # Main Content
    html.Div(
        id="page-content",
        className="main-content"
    ),
])

# ========== STYLES ==========
app.index_string = '''
<!DOCTYPE html>
<html lang="en">
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                overflow-x: hidden;
            }
            
            /* ===== SIDEBAR ===== */
            .sidebar {
                position: fixed;
                top: 0;
                left: 0;
                height: 100vh;
                width: 280px;
                background: linear-gradient(180deg, #0F172A 0%, #1E293B 100%);
                border-right: 1px solid #334155;
                box-shadow: 4px 0 10px rgba(0, 0, 0, 0.3);
                display: flex;
                flex-direction: column;
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                z-index: 1040;
                overflow-y: auto;
                overflow-x: hidden;
            }
            
            .sidebar.collapsed {
                width: 80px;
            }
            
            .sidebar-header {
                padding: 1.5rem 1rem;
                min-height: 70px;
            }
            
            .sidebar.collapsed .sidebar-brand,
            .sidebar.collapsed .nav-label {
                opacity: 0;
                width: 0;
                overflow: hidden;
            }
            
            .sidebar.collapsed .sidebar-icon {
                margin-right: 0 !important;
            }
            
            .sidebar-divider {
                border-color: #334155;
                margin: 0.5rem 1rem;
            }
            
            /* Navigation Links */
            .sidebar-nav-link {
                display: flex;
                align-items: center;
                padding: 0.875rem 1rem;
                color: #94A3B8 !important;
                border-radius: 8px;
                margin-bottom: 0.25rem;
                transition: all 0.2s ease;
                text-decoration: none;
                white-space: nowrap;
            }
            
            .sidebar-nav-link:hover {
                background-color: #1E293B;
                color: #60A5FA !important;
                transform: translateX(4px);
            }
            
            .sidebar-nav-link.active {
                background-color: #3B82F6;
                color: white !important;
                font-weight: 600;
                box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
            }
            
            .sidebar-nav-link i {
                flex-shrink: 0;
            }
            
            .nav-label {
                transition: all 0.3s ease;
            }
            
            /* Main Content */
            .main-content {
                margin-left: 280px;
                padding: 2rem;
                min-height: 100vh;
                background-color: #F8FAFC;
                transition: margin-left 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            }
            
            .main-content.sidebar-collapsed {
                margin-left: 80px;
            }
            
            /* Mobile Navbar */
            .mobile-navbar {
                display: none;
            }
            
            /* Sidebar Backdrop (mobile only) */
            .sidebar-backdrop {
                display: none;
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background-color: rgba(0, 0, 0, 0.5);
                z-index: 1035;
                opacity: 0;
                transition: opacity 0.3s ease;
            }
            
            .sidebar-backdrop.show {
                display: block;
                opacity: 1;
            }
            
            /* Scrollbar */
            .sidebar::-webkit-scrollbar {
                width: 6px;
            }
            
            .sidebar::-webkit-scrollbar-track {
                background: #0F172A;
            }
            
            .sidebar::-webkit-scrollbar-thumb {
                background: #334155;
                border-radius: 3px;
            }
            
            /* ===== MOBILE STYLES ===== */
            @media (max-width: 991.98px) {
                .mobile-navbar {
                    display: flex !important;
                }
                
                .sidebar {
                    transform: translateX(-100%);
                    width: 280px !important;
                    z-index: 1050;
                }
                
                .sidebar.mobile-open {
                    transform: translateX(0);
                }
                
                .sidebar.collapsed {
                    transform: translateX(-100%);
                }
                
                .sidebar .d-none.d-lg-block {
                    display: none !important;
                }
                
                .main-content {
                    margin-left: 0 !important;
                    padding: 1rem;
                    padding-top: 70px; /* Account for fixed navbar */
                }
            }
            
            @media (max-width: 768px) {
                .main-content {
                    padding: 0.75rem;
                    padding-top: 70px;
                }
                
                h1, h2 {
                    font-size: 1.5rem !important;
                }
            }
            
            @media (max-width: 576px) {
                .main-content {
                    padding: 0.5rem;
                    padding-top: 70px;
                }
                
                .sidebar {
                    width: 100% !important;
                }
            }
            
            /* Utility */
            .card {
                border: none;
                box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

# ========== CALLBACKS ==========

# Desktop sidebar toggle
@app.callback(
    Output("sidebar", "className"),
    Output("main-content", "className"),
    Output("sidebar-state", "data"),
    Input("desktop-toggle-btn", "n_clicks"),
    State("sidebar-state", "data"),
    prevent_initial_call=True
)
def toggle_desktop_sidebar(n_clicks, state):
    if n_clicks:
        collapsed = not state.get("collapsed", False)
        state["collapsed"] = collapsed
        
        sidebar_class = "sidebar collapsed" if collapsed else "sidebar"
        content_class = "main-content sidebar-collapsed" if collapsed else "main-content"
        
        return sidebar_class, content_class, state
    
    return "sidebar", "main-content", state


# Mobile menu toggle
@app.callback(
    Output("sidebar", "className", allow_duplicate=True),
    Output("sidebar-backdrop", "className"),
    Input("mobile-menu-btn", "n_clicks"),
    Input("sidebar-backdrop", "n_clicks"),
    Input("url", "pathname"),
    State("sidebar", "className"),
    prevent_initial_call=True
)
def toggle_mobile_menu(menu_clicks, backdrop_clicks, pathname, current_class):
    ctx = dash.callback_context
    
    if not ctx.triggered:
        return "sidebar", "sidebar-backdrop"
    
    trigger = ctx.triggered[0]["prop_id"]
    
    # Close on navigation or backdrop click
    if "pathname" in trigger or "backdrop" in trigger:
        return "sidebar", "sidebar-backdrop"
    
    # Toggle on menu button click
    if "mobile-open" in current_class:
        return "sidebar", "sidebar-backdrop"
    else:
        return "sidebar mobile-open", "sidebar-backdrop show"


# Page content
@app.callback(
    Output("page-content", "children"),
    Input("url", "pathname")
)
def render_page(pathname):
    if pathname == "/programs":
        return html.Div([
            html.H2("🖥️ Programs", className="mb-4"),
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Program List"),
                        dbc.CardBody([
                            html.P("Program management interface")
                        ])
                    ])
                ], md=12)
            ])
        ])
    
    elif pathname == "/planning":
        return html.Div([
            html.H2("📋 Planning", className="mb-4"),
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Production Planning"),
                        dbc.CardBody([
                            html.P("Planning tools and schedules")
                        ])
                    ])
                ], md=12)
            ])
        ])
    
    elif pathname == "/inventory":
        return html.Div([
            html.H2("📦 Inventory", className="mb-4"),
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Inventory Management"),
                        dbc.CardBody([
                            html.P("Stock levels and tracking")
                        ])
                    ])
                ], md=12)
            ])
        ])
    
    elif pathname == "/settings":
        return html.Div([
            html.H2("⚙️ Settings", className="mb-4"),
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Master Data Configuration"),
                        dbc.CardBody([
                            html.P("System settings and preferences")
                        ])
                    ])
                ], md=12)
            ])
        ])
    
    # Default: Dashboard
    return html.Div([
        html.H2("📊 Dashboard", className="mb-4"),
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H4("Welcome to PaperLink MES", className="card-title"),
                        html.P("Your Manufacturing Execution System", className="text-muted"),
                        html.Hr(),
                        html.P("Select a section from the sidebar to get started.")
                    ])
                ])
            ], md=12, className="mb-3"),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H5("Quick Stats"),
                        html.P("Production metrics will appear here")
                    ])
                ])
            ], md=6, lg=3),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H5("Active Orders"),
                        html.P("Current order status")
                    ])
                ])
            ], md=6, lg=3),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H5("Inventory"),
                        html.P("Stock levels")
                    ])
                ])
            ], md=6, lg=3),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H5("Alerts"),
                        html.P("System notifications")
                    ])
                ])
            ], md=6, lg=3),
        ])
    ])


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8050)