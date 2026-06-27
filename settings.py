FONT = "Calibri"
MAIN_TEXT_SIZE = 150
INPUT_FONT_SIZE = 26
SWITCH_FONT_SIZE = 18
BUTTON_CORNER_RADIUS = 6
GREEN = '#50BFAB'
DARK_GREEN = '#3A8A7B'
WHITE = '#F2F2F2'
BLACK ='#1F1F1F'
LIGHT_GRAY = '#E8E8E8'
GRAY = '#D9D9D9'
EVEN_COLOR = '#F8F9FA'
ODD_COLOR = '#E9ECEF'
TITLE_HEX_COLOR = 0X00ABBF50

SUPPLIER_PATH = r"C:\Users\sang.n\OneDrive - whitebird.ca\Paper App\suppliers"
PO_PATH = r"C:\Users\sang.n\OneDrive - whitebird.ca\Paper App\purchase order"
CUSTOMER_PATH = r"C:\Users\sang.n\OneDrive - whitebird.ca\Paper App\customers.csv"
CPO_PATH = r"C:\Users\sang.n\OneDrive - whitebird.ca\Paper App\purchase order"
DR_PATH = r"C:\Users\sang.n\OneDrive - whitebird.ca\Paper App\suppliers"

COLUMNS_CONFIG = {
            "supplier_name":"Supplier Name",
             "purchase_order_number" :"PO #", 
             "line": "Line",
             "suffix" :"Suffix",
             "material":"Material", 
             "price":"Price", 
             "uom": "UOM",
             "width":"Width", 
             "length":"Length",  
             "ordered_quantity":"Qty Ordered",
             "purchase_date":"Purchase Date", 
             "requested_date":"Due Date", 
             "file_name":"File Name"
        }

PURCHASING_COLUMN_CONFIG = {
        "customer_name": "Customer Name",
        "order_id" : "Order Number",
        "supplier_name":"Supplier Name",
        "purchase_order_number" :"PO #", 
        "material":"Grade", 
        "sheet_size":"Sheet Size",
        "price":"Price", 
        "ordered_quantity":"Qty Ordered",
        "total_shipped":"Qty Recv",
        "ordered_msf":"Ordered MSF", 
        "total_msf": "Total MSF",
        "shipped_msf":"Recv MSF", 
        "purchase_date":"Purchase Date", 
        "requested_date":"Due Date", 
        "status":"Status",
        "delivery_dockets": "D/Rs",
        "width":"Width", 
        "length":"Length",
        "file_name" : "Filename",
        "id":"ID"
        }

ORDERS_COLUMN_CONFIG ={
    "order_id" : "Order #",
    "customer_name" : "Customer Name",
    "status" : "Status"
}

ORDER_DETAILS_COLUMN_CONFIG = {
    'order_line' : 'Order Line', 
    'docket_id' : 'Docket #', 
    'order_quantity' : 'Order Quantity', 
    'requested_date' : 'Requested Date', 
    'docket_description' : 'Docket Description', 
    'style_description' : 'Style Description', 
    'closure_description' : 'Closure Description', 
    'ink_description' : 'Ink Description', 
    'tooling_description' : 'Tooling Description', 
    'active_date' : 'Active Date', 
    'status' : 'Status'
}

DELIVERY_DOCKET_COLUMN_CONFIG = {
             "purchase_order_number" :"PO #",
             "shipped_quantity":"Shipped Quantity"
        }

MAIN_BUTTONS = {
    "add_new" : {'col' : 0, 'row': 0, 'style': 'success', 'text': "Add New"},
    "receipt_po" : {'col' : 1, 'row': 0, 'style': 'warning', 'text': "Receipt PO"},
    "export_csv" : {'col' : 2, 'row': 0, 'style': 'danger', 'text': "Export CSV"},
    "paste_files_to_directory" : {'col' : 3, 'row': 0, 'style': 'info', 'text': "Paste PO"},
    "view_status_log" : {'col' : 4, 'row': 0, 'style': 'secondary', 'text': "View Status Log"}
}

ORDER_DETAIL_BUTTONS = {
    "change_bill_to" : {'col' : 0, 'row': 0, 'style': 'success', 'text': "Change Bill-To"},
    "change_ship_to" : {'col' : 1, 'row': 0, 'style': 'warning', 'text': "Change Ship-To"},
    "request_qta" : {'col' : 3, 'row': 0, 'style': 'info', 'text': "Request QTA"},
    "export_csv" : {'col' : 2, 'row': 0, 'style': 'danger', 'text': "Export CSV"},
    "view_status_log" : {'col' : 4, 'row': 0, 'style': 'secondary', 'text': "View Status Log"}
}

DICT_MATERIAL = {'claymetsakraftbackwhite2s': "Coated White 2 sides",
        'claymetsakraftbackwhiteoutside': "Coated White",
        'claymetsakbw': "Coated White",
        'claymetsakraftbackwhite': "Coated White",
        'claymetsakbw2s' : "Coated White 2 sides",
        'claymetsakbwoutside': "Coated White",
        'coatedwhite2s' : "Coated White 2 sides",
        'coatedwhite': "Coated White",
        'kemi2s': "Coated White 2 sides",'kemi': "Coated White",
        'whitetop2s': "Oyster 2 sides",'whitetop' : "Oyster",
        'oyster2s': "Oyster 2 sides",'oyster': "Oyster",
        'oy2s': "Oyster 2 sides", 'oy': "Oyster",'k' : "Kraft"}

STATUS = ["Pending", "Confirmed", "Shipped", "Completed", "Closed", "Cancelled", "Rejected", "Partial Rejected"]
ORDER_STATUS = ["Pending", "Shipped", "Completed", "Closed", "Cancelled"]
TOOLBAR ={
    'new' : {'image path': 'icons/new.png'},
    'purchase' : {'image path': "icons/shopping-cart-32.png"}
}