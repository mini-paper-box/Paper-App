
# importing required classes
import email, smtplib, ssl, os, shutil, datetime, csv, pathlib, re
from pypdf import PdfReader
from settings import *
from datetime import datetime
from database import MakeSimpleSql

class PDFReader():
    def __init__(self):
        self.database = MakeSimpleSql()
        self.path = PO_PATH
        self.suppliers = self.database.get_suppliers()

    def get_material(self, vendor, list_material):
        str_material = []
        for m in list_material:
            alt_name = self.database.get_material_with_supplier(vendor,m)
            if not alt_name:
                alt_name = "TBA"
            str_material.append(alt_name)
        return " ".join(str_material)
    
    def extract_dates(self, str_d):
        date_pattern = r'\d{2,4}-\d{2}-\d{2}'  # Matches YYYY-MM-DD with zero-padding
        query = re.findall(date_pattern, str_d)
        if len(query) >= 2:
            try:
                date_objs = [datetime.strptime(d, "%Y-%m-%d") for d in query[:2]]
                date_objs.sort()
                return {
                    "purchase_date": date_objs[0],
                    "due_date": date_objs[1]
                }
            except ValueError:
                pass  # If dates are malformed, fall through to default

        # Fallback: use today's date
        today = datetime.today()
        return {"purchase_date": today, "due_date": today}

    def extract_po_number(self,str_d):
        if not str_d.strip():
            return "TBD"

        # 1. Match patterns like "123-4 Pcs"
        pattern1 = r"\d+-\d\D+"
        match1 = re.findall(pattern1, str_d)
        if match1:
            return match1[0].replace("\n", "").strip()

        # 2. Match 5-digit PO number followed by a space
        pattern2 = r"\b\d{5}\b"
        match2 = re.findall(pattern2, str_d)
        if match2:
            return match2[0].strip()

        # 3. Default fallback
        return "TBD"

    def extract_quantity(self,str_d):
        if not str_d.strip():
            return 1

        # 1. Match formats like "123-4 Pcs", extract number after dash
        pattern1 = r"\d+-\d\D+ \d+"
        match1 = re.findall(pattern1, str_d)
        if match1:
            # Remove everything before the final number
            return re.sub(r"\d+-\d\D+", "", match1[0]).strip()

        # 2. Match formats like "750.00 5.291", extract the first number
        str_d_clean = str_d.replace(",", "")
        match2 = re.findall(r"\b\d+\.\d+.\d+\.\d+", str_d_clean)
        if match2:
            nums = re.findall(r"\d+", match2[0])
            if nums:
                return nums[0]

        # 3. Match "100 Cut-to-Size", extract the number
        match3 = re.findall(r"\b\d+\s+Cut-to-Size\b", str_d)
        if match3:
            nums = re.findall(r"\d+", match3[0])
            if nums:
                return nums[0]

        # Default fallback
        return 1
            
    def extract_sheet_size(self,str_d):
        if not str_d.strip():
            return (1, 1)

        # Patterns to match formats like "25 1/2 x 32", "25x32", "25.5 x 32.75", etc.
        patterns = [
            r"\d{2,3}[-/.\d]*\s*x\s*\d{2,3}[-/.\d]*",     # with spaces: 25 1/2 x 32 or 25.5 x 32.75
            r"\d{2,3}[-/.\d]*x\d{2,3}[-/.\d]*"            # without spaces: 25x32 or 25.5x32.75
        ]

        for pattern in patterns:
            matches = re.findall(pattern, str_d, flags=re.IGNORECASE)
            if matches:
                break
        else:
            return (1, 1)  # No matches found

        # Take the first matched size
        sheet_size = matches[0].lower().replace(" ", "")  # Normalize and remove spaces
        width_str, length_str = sheet_size.split("x")
        def parse_dimension(dim):
            """Convert strings like '25-1/2' or '25.75' to float."""
            # Handle fractions like 25-1/2
            if '-' in dim:
                whole, frac = dim.split('-')
                numerator, denominator = frac.split('/')
                return int(whole) + int(numerator) / int(denominator)
            elif '/' in dim:
                numerator, denominator = dim.split('/')
                return int(numerator) / int(denominator)
            elif '.' in dim:
                whole, numerator = dim.split('.')
                denominator = 16
                return int(whole) + int(numerator) / int(denominator)
            else:
                return float(dim)

        try:
            width = parse_dimension(width_str)
            length = parse_dimension(length_str)
        except:
            return (1, 1)

        return (round(width, 3), round(length, 3))
        
    def extract_material_info(self,str_d):
        patterns = r"MRA|WRA|#30|#36|30#|36#"

        # FLUTE + ECT patterns like B32, 32C, BC44, etc.
        flute_ect_pattern = r"\b[bceBCE]{1,2}[0-9]{2}\b[12a-zA-Z ]*|\b[0-9]{2}[bceBCE]{1,2}\b[12a-zA-Z ]*|\b\d{1,2}mm\b"
        # flute_ect_pattern = r"\b[bceBCE]{1,2}[0-9]{2}\b(?:[12a-zA-Z ]*|\s*\d{1,2}mm)?|\b[0-9]{2}[bceBCE]{1,2}\b(?:[12a-zA-Z ]*|\s*\d{1,2}mm)?"

        material = []

        # Find flute/ect pattern
        query = re.findall(flute_ect_pattern, str_d, re.IGNORECASE)
        print(query)
        if query:
            # Just take the first match
            temp_material = query[0].split(' ')
            parts = re.findall(r"\D+|\d+", temp_material[0])
            if parts: #extract 32C
                if not parts[0].isdigit():
                    combined = parts[1] + parts[0]# + " ".join(parts[2:])
                else:
                    combined = parts[0] + parts[1]# + " ".join(parts[2:])

                material.append(combined)

                #liner_patters
                str_liner = re.sub(r'\s+', '',"".join(temp_material[1:]))
                liner_patterns= [r'ClayMETSAKraftBackWhite',
                                 r'ClayMETSAKBW',
                                 r'CoatedWhite',
                                 r'Kemi',
                                 r'Whitetop',
                                 r'Oy',
                                 r'K',
                                 r'Corroplast']
                
                print(str_liner)
                for liner_pattern in liner_patterns:
                    liner = re.search(liner_pattern, str_liner, re.IGNORECASE)
                    print(liner)
                    if liner:
                        mat = liner.group().lower()
                        if '2s' in str_liner.lower():
                            mat = "".join([liner.group().lower(),"2s"])
                        if DICT_MATERIAL[mat]:

                            material.append(DICT_MATERIAL[mat])
                            break

        # Search for adders
        adders = re.findall(patterns, str_d, re.IGNORECASE)
        if adders:
            material.extend(adders)
        result = []
        for m in material:
            result.append(MakeSimpleSql().get_material(m))
        
        print(result)
        return result
    
    def extract_price(self, str_d):
        text = str_d

        # Compile the pattern once, with flags
        pattern = re.compile(r"""
            (?:\d{1,3}(?:,\d{3})*|\d+)?    # Optional integer part with commas
            \.\d+                          # Required decimal
            (?:\.\d+)?                     # Optional second decimal (rare)
            \s*/\s*                        # Slash separator
            (MSF|M|EA|EACH)                        # Units
        """, re.IGNORECASE | re.VERBOSE)

        # Find all price/unit matches
        query = [m.group(0) for m in pattern.finditer(text)]

        if query:
            return query[0].upper().strip()
        else:
            # Fallback: extract 2 decimal numbers like '12.5 3.25'
            fallback = re.findall(r"(\d+\.\d+)\s+(\d+\.\d+)", text)
            if fallback:
                _, price = fallback[0]  # use second number as price
                return f"{price}/EA"
            return None
    
    def extract_vendor(self,str_d):
        text = str_d
        keywords = ['green meadows', 
                    'coastal', 'tencorr', 
                    'independent', 
                    'plastic and paper',
                    'master packaging', 
                    'em plastic']
        # keywords = self.suppliers
        pattern = r'\b(?:' + '|'.join(map(re.escape, keywords)) + r')\b'
        result = re.findall(pattern.lower(), text, re.IGNORECASE)
        if result:
            #optional return longest match
            longest = max(result, key=len)
            return longest.title()
        else:
            return None

    def extract_files_info(self, file_path = None):
        files = [f for f in os.listdir(self.path) if f.lower().endswith(".pdf")]
        list_po = []

        def split_po_number(po_string):
            if '-' not in po_string:
                return po_string, 1, None

            base, rest = po_string.split('-', 1)

            # Separate digits and letters after the dash
            num_part = ''.join(filter(str.isdigit, rest))
            suffix = ''.join(filter(str.isalpha, rest))

            return base, num_part, suffix
        
        def split_price(price_string):
            if "/" not in price_string:
                return price_string, None
            
            base, rest = price_string.split("/", 1)

            return base, rest

        if file_path:
            files = [file_path]
        for file_name in files:
            try:
                file_path = os.path.join(self.path, file_name)
                reader = PdfReader(file_path)
                page = reader.pages[0]
                text = page.extract_text()

                get_date = self.extract_dates(text)
                purchase_date = get_date.get("purchase_date", "").strftime("%Y-%m-%d") if get_date.get("purchase_date") else ""
                due_date = get_date.get("due_date", "").strftime("%Y-%m-%d") if get_date.get("due_date") else ""

                po_number = self.extract_po_number(text).strip()
                vendor = self.extract_vendor(text)
                sheet_size = self.extract_sheet_size(text)
                quantity = self.extract_quantity(text)
                material = self.extract_material_info(text)
                if not (vendor and po_number and sheet_size and quantity and material):
                    # print(po_number)
                    # print(vendor)
                    # print(sheet_size)
                    # print(material)
                    print(f"Missing data in {file_name}, skipping...")
                    continue
                try:
                    price = (self.extract_price(text))
                except:
                    price = 0.0

                supplier_id = MakeSimpleSql().get_supplier_id(vendor)
                material_name = self.get_material(supplier_id, material)

                po, line, suffix = split_po_number(po_number)

                unit_price, uom = split_price(price)

                list_po.append((
                    vendor, po, line, suffix, material_name, unit_price, uom,
                    float(sheet_size[0]), float(sheet_size[1]),
                    int(quantity), purchase_date, due_date, file_name
                ))
            except Exception as e:
                print(f"Error processing file {file_name}: {e}")
                continue
        return list_po
   
    def update_record(self):
        MakeSimpleSql().insert_multiple_purchase_order(self.read_files())

    def rename_files(self):
        get_files_info = self.extract_files_info()
        # vendor, po, line, suffix, material_name, unit_price, uom, size1, size2, quantity, purchase_date, due_date, file_name
        try:
            for file in get_files_info:
                vendor, po, line, suffix, material_name, unit_price, uom, size1, size2, quantity, purchase_date, due_date, file_name = file
                # vendor_name = MakeSimpleSql().get_supplier_name(vendor)
                if line and suffix:
                    po_number = f"{po}-{line}{suffix}"
                elif line:
                    po_number = f"{po}-{line}"
                else:
                    po_number = f"{po}"

                msf = f'{(int(size1 * size2 / 144 * quantity))}'
                temp_name = "_".join([vendor,po_number,due_date,msf]) + ".pdf"
                origin_path = os.path.join(self.path, file_name)
                os.rename(origin_path, os.path.join(self.path,temp_name))
        except:
            pass


def main() -> None:
    (pdf_reader().rename_files())
    # po = (pdf_reader().read_files())
    # for i in po:
    #     print(i[9])
    # MakeSimpleSql().insert_multiple_purchase_order(po)

if __name__ == '__main__':
    main()