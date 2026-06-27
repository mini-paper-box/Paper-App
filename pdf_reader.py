import email, smtplib, ssl, os, shutil, datetime, csv, pathlib, re
import logging
from pypdf import PdfReader
from typing import Tuple, List, Optional, Dict
from datetime import datetime
from settings import *
from database import MakeSimpleSql

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PDFReader:
    """Extracts purchase order information from PDF files."""
    
    def __init__(self):
        self.database = MakeSimpleSql()
        self.path = PO_PATH
        self.suppliers = self.database.get_suppliers()
        
        # Load vendor keywords from database supplier table
        self.vendor_keywords = self._load_supplier_names()

    def _load_supplier_names(self) -> List[str]:
        """Load supplier names from the supplier table."""
        try:
            # Assuming get_suppliers() returns supplier data
            # If it returns a list of tuples/dicts, extract supplier_name
            suppliers = self.database.get_suppliers()
            print(suppliers)
            # Handle different return formats
            if suppliers and len(suppliers) > 0:
                # If suppliers is a list of tuples, assume supplier_name is in there
                if isinstance(suppliers[0], tuple):
                    # You may need to adjust the index based on your table structure
                    supplier_names = [str(s[1]).lower() if len(s) > 1 else str(s[0]).lower() 
                                    for s in suppliers]
                # If suppliers is a list of dicts
                elif isinstance(suppliers[0], dict):
                    supplier_names = [s.get('supplier_name', '').lower() 
                                    for s in suppliers if s.get('supplier_name')]
                # If it's just a list of names
                else:
                    supplier_names = [str(s).lower() for s in suppliers]
                
                logger.info(f"Loaded {len(supplier_names)} suppliers from database")
                return supplier_names
            
            logger.warning("No suppliers found in database, using fallback list")
            return self._get_fallback_suppliers()
            
        except Exception as e:
            logger.error(f"Error loading suppliers from database: {e}", exc_info=True)
            return self._get_fallback_suppliers()
    
    def _get_fallback_suppliers(self) -> List[str]:
        """Return fallback supplier list if database query fails."""
        return [
            'green meadows', 'coastal', 'tencorr', 
            'independent', 'plastic and paper',
            'master packaging', 'em plastic'
        ]

    def get_material(self, vendor: int, list_material: List[str]) -> str:
        """Get material names for a vendor."""
        str_material = []
        for m in list_material:
            alt_name = self.database.get_material_with_supplier(vendor, m)
            if not alt_name:
                alt_name = "TBA"
            str_material.append(alt_name)
        return " ".join(str_material)
    
    def extract_dates(self, str_d: str) -> Dict[str, datetime]:
        """Extract purchase and due dates from text."""
        date_pattern = r'\d{2,4}-\d{2}-\d{2}'
        query = re.findall(date_pattern, str_d)
        
        if len(query) >= 2:
            try:
                date_objs = [datetime.strptime(d, "%Y-%m-%d") for d in query[:2]]
                date_objs.sort()
                
                # Validate dates are reasonable (not too far in past/future)
                today = datetime.today()
                for date_obj in date_objs:
                    days_diff = abs((date_obj - today).days)
                    if days_diff > 730:  # More than 2 years
                        logger.warning(f"Date seems unusual: {date_obj}")
                
                return {
                    "purchase_date": date_objs[0],
                    "due_date": date_objs[1]
                }
            except ValueError as e:
                logger.error(f"Error parsing dates: {e}")

        # Fallback: use today's date
        today = datetime.today()
        logger.warning("Using fallback dates (today)")
        return {"purchase_date": today, "due_date": today}

    def extract_po_number(self, str_d: str):
        if not str_d or not str_d.strip():
            return []

        # Normalize text
        text = (
            str_d
            .replace('−', '-')
            .replace('–', '-')
        )
        text = re.sub(r'\s+', ' ', text)
        results = []
        seen = set()

        # ----------------------------------------------------
        # Flute PO
        # ----------------------------------------------------
        base_po_match = re.search(r'(?:CP-)?\b(\d{7})\b', text)
        if base_po_match:
            base_po = base_po_match.group(1)

            line_re = re.compile(
                rf'\b{base_po}-(\d+)([A-Z])?\b',
                re.IGNORECASE
            )

            for match in line_re.finditer(text):
                line, suffix = match.groups()
                key = (base_po, line, suffix)
                if key in seen:
                    continue
                seen.add(key)

                results.append({
                    "po": base_po,
                    "line": int(line),
                    "suffix": suffix or None
                })

            if results:
                return results   # ✅ stop here if multi-line PO found

        # ----------------------------------------------------
        # Pronto PO
        # ----------------------------------------------------
        header_text = text[:250]

        po_5_re = re.compile(
        r'\b\d{2}-[A-Z]{3}-\d{2}\s+(\d{5})\b',  # date + PO
        re.IGNORECASE
        )

        for match in po_5_re.finditer(header_text):
            po = match.group(1)

            # 🚫 Exclude known bad contexts
            bad_context = re.search(
                rf'(TAX\s*#|HST|SUBTOTAL|TOTAL)\s*{po}',
                text,
                re.IGNORECASE
            )
            if bad_context:
                continue

            results.append({
                "po": po,
                "line": 1,
                "suffix": None
            })
            break  # only ONE 5-digit PO per document

        return results

    
    def extract_po_number_v1(self, str_d: str) -> str:
        """Extract purchase order number from text."""
        if not str_d.strip():
            return "TBD"

        # 1. Match patterns like "123-4 Pcs"
        pattern1 = r"\d+-\d\D+"
        match1 = re.findall(pattern1, str_d)
        if match1:
            return match1[0].replace("\n", "").strip()

        # 2. Match 5-digit PO number
        pattern2 = r"\b\d{5}\b"
        match2 = re.findall(pattern2, str_d)
        if match2:
            return match2[0].strip()

        return "TBD"

    def extract_quantity(self, str_d: str) -> int:
        """Extract quantity from text."""
        if not str_d.strip():
            return 1

        try:
            # 1. Match formats like "123-4 Pcs", extract number after dash
            pattern1 = r"\d+-\d\D+ \d+"
            match1 = re.findall(pattern1, str_d)
            if match1:
                qty = re.sub(r"\d+-\d\D+", "", match1[0]).strip()
                return int(qty)

            # 2. Match formats like "750.00 5.291"
            str_d_clean = str_d.replace(",", "")
            match2 = re.findall(r"\b\d+\.\d+.\d+\.\d+", str_d_clean)
            if match2:
                nums = re.findall(r"\d+", match2[0])
                if nums:
                    return int(nums[0])

            # 3. Match "100 Cut-to-Size"
            match3 = re.findall(r"\b\d+\s+Cut-to-Size\b", str_d)
            if match3:
                nums = re.findall(r"\d+", match3[0])
                if nums:
                    return int(nums[0])
        except (ValueError, IndexError) as e:
            logger.error(f"Error extracting quantity: {e}")

        return 1
            
    def extract_sheet_size(self, str_d: str) -> Tuple[float, float]:
        """Extract sheet dimensions from text."""
        if not str_d.strip():
            return (1.0, 1.0)

        patterns = [
            r"\d{2,3}[-/.\d]*\s*x\s*\d{2,3}[-/.\d]*",
            r"\d{2,3}[-/.\d]*x\d{2,3}[-/.\d]*"
        ]

        matches = None
        for pattern in patterns:
            matches = re.findall(pattern, str_d, flags=re.IGNORECASE)
            if matches:
                break
        
        if not matches:
            return (1.0, 1.0)

        sheet_size = matches[0].lower().replace(" ", "")
        width_str, length_str = sheet_size.split("x")
        
        def parse_dimension(dim: str) -> float:
            """Convert strings like '25-1/2' or '25.75' to float."""
            try:
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
            except (ValueError, ZeroDivisionError) as e:
                logger.error(f"Error parsing dimension '{dim}': {e}")
                return 1.0

        width = parse_dimension(width_str)
        length = parse_dimension(length_str)
        
        # Validate dimensions are reasonable
        if width <= 0 or length <= 0 or width > 1000 or length > 1000:
            logger.warning(f"Unusual dimensions: {width} x {length}")
            return (1.0, 1.0)

        return (round(width, 3), round(length, 3))
        
    def extract_material_info(self, str_d: str) -> List[str]:
        """Extract material information from text."""
        patterns = r"MRA|WRA|#30|#36|30#|36#"
        flute_ect_pattern = r"\b[bceBCE]{1,2}[0-9]{2}\b[12a-zA-Z ]*|\b[0-9]{2}[bceBCE]{1,2}\b[12a-zA-Z ]*|\b\d{1,2}mm\b"
        
        material = []

        # Find flute/ect pattern
        query = re.findall(flute_ect_pattern, str_d, re.IGNORECASE)
        logger.debug(f"Material matches: {query}")
        
        if query:
            temp_material = query[0].split(' ')
            parts = re.findall(r"\D+|\d+", temp_material[0])
            
            if parts:
                if not parts[0].isdigit():
                    combined = parts[1] + parts[0]
                else:
                    combined = parts[0] + parts[1]
                material.append(combined)

                # Extract liner patterns
                str_liner = re.sub(r'\s+', '', "".join(temp_material[1:]))
                liner_patterns = [
                    r'ClayMETSAKraftBackWhite',
                    r'ClayMETSAKBW',
                    r'CoatedWhite',
                    r'Kemi',
                    r'Whitetop',
                    r'Oy',
                    r'K',
                    r'Corroplast'
                ]
                
                logger.debug(f"Liner string: {str_liner}")
                for liner_pattern in liner_patterns:
                    liner = re.search(liner_pattern, str_liner, re.IGNORECASE)
                    if liner:
                        mat = liner.group().lower()
                        if '2s' in str_liner.lower():
                            mat = f"{liner.group().lower()}2s"
                        if mat in DICT_MATERIAL:
                            material.append(DICT_MATERIAL[mat])
                            break

        # Search for adders
        adders = re.findall(patterns, str_d, re.IGNORECASE)
        if adders:
            material.extend(adders)
        
        # Use existing database instance
        result = []
        for m in material:
            db_material = self.database.get_material(m)
            if db_material:
                result.append(db_material)
        
        logger.debug(f"Final materials: {result}")
        return result
    
    def extract_price(self, str_d: str) -> Optional[str]:
        """Extract price from text."""
        pattern = re.compile(r"""
            (?:\d{1,3}(?:,\d{3})*|\d+)?
            \.\d+
            (?:\.\d+)?
            \s*/\s*
            (MSF|M|EA|EACH)
        """, re.IGNORECASE | re.VERBOSE)

        query = [m.group(0) for m in pattern.finditer(str_d)]

        if query:
            return query[0].upper().strip()
        
        # Fallback
        fallback = re.findall(r"(\d+\.\d+)\s+(\d+\.\d+)", str_d)
        if fallback:
            _, price = fallback[0]
            return f"{price}/EA"
        
        return None
    
    def extract_vendor(self, str_d: str) -> Optional[str]:
        """Extract vendor name from text."""
        pattern = r'\b(?:' + '|'.join(map(re.escape, self.vendor_keywords)) + r')\b'
        result = re.findall(pattern, str_d.lower(), re.IGNORECASE)
        
        if result:
            longest = max(result, key=len)
            return longest.title()
        
        return None

    def extract_pdf_text(self, full_path: str) -> str:
        reader = PdfReader(full_path)

        pages_text = []
        for i, page in enumerate(reader.pages):
            try:
                page_text = page.extract_text()
                if page_text:
                    pages_text.append(page_text)
            except Exception as e:
                logger.warning(f"Failed to read page {i} in {full_path}: {e}")

        return re.sub(r'(\d+)\s+-', r'\1-', "\n".join(pages_text))

    def extract_files_info(self, file_path: Optional[str] = None) -> List[Tuple]:
        """Extract information from PDF files."""
        if file_path:
            files = [file_path]
        else:
            files = [f for f in os.listdir(self.path) if f.lower().endswith(".pdf")]
        
        list_po = []

        def split_po_number(po_string: str) -> Tuple[str, int, Optional[str]]:
            """Split PO number into base, line, and suffix."""
            if '-' not in po_string:
                return po_string, 1, None

            base, rest = po_string.split('-', 1)
            num_part = ''.join(filter(str.isdigit, rest))
            suffix = ''.join(filter(str.isalpha, rest))

            return base, int(num_part) if num_part else 1, suffix if suffix else None
        
        def split_price(price_string: str) -> Tuple[str, Optional[str]]:
            """Split price string into amount and unit."""
            if not price_string or "/" not in price_string:
                return price_string if price_string else "0", None
            
            base, rest = price_string.split("/", 1)
            return base, rest

        for file_name in files:
            try:
                full_path = os.path.join(self.path, file_name)
                text = self.extract_pdf_text(full_path)

                # Extract all fields
                get_date = self.extract_dates(text)
                purchase_date = get_date["purchase_date"].strftime("%Y-%m-%d")
                due_date = get_date["due_date"].strftime("%Y-%m-%d")
                
                # po_number = self.extract_po_number(text).strip()
                po_numbers = self.extract_po_number(text)
                vendor = self.extract_vendor(text)
                sheet_size = self.extract_sheet_size(text)
                quantity = self.extract_quantity(text)
                material = self.extract_material_info(text)
                
                # Validate required fields
                # if not all([vendor, po_number, material]):
                #     logger.warning(
                #         f"Missing required data in {file_name}: "
                #         f"vendor={vendor}, po={po_number}, material={material}"
                #     )
                #     continue
                
                try:
                    price = self.extract_price(text)
                except Exception as e:
                    logger.error(f"Error extracting price from {file_name}: {e}")
                    price = "0.0/EA"

                supplier_id = self.database.get_supplier_id(vendor)
                material_name = self.get_material(supplier_id, material)
                
                unit_price, uom = split_price(price)

                for each_po in po_numbers:
                    list_po.append((
                    vendor, each_po['po'], each_po['line'], each_po['suffix'], material_name, unit_price, uom,
                        float(sheet_size[0]), float(sheet_size[1]),
                        int(quantity), purchase_date, due_date, file_name
                    ))
                
                logger.info(f"Successfully processed {file_name}")
                
            except Exception as e:
                logger.error(f"Error processing file {file_name}: {e}", exc_info=True)
                continue
        
        return list_po
   
    def update_record(self):
        """Update database with extracted PO information."""
        try:
            po_data = self.extract_files_info()
            self.database.insert_multiple_purchase_order(po_data)
            logger.info(f"Successfully inserted {len(po_data)} purchase orders")
        except Exception as e:
            logger.error(f"Error updating records: {e}", exc_info=True)

    def rename_files(self):
        """Rename PDF files with standardized naming."""
        get_files_info = self.extract_files_info()
        
        for file in get_files_info:
            try:
                (vendor, po, line, suffix, material_name, unit_price, uom, 
                 size1, size2, quantity, purchase_date, due_date, file_name) = file
                
                # Build PO number
                if line and suffix:
                    po_number = f"{po}-{line}{suffix}"
                elif line:
                    po_number = f"{po}-{line}"
                else:
                    po_number = f"{po}"

                msf = int(size1 * size2 / 144 * quantity)
                new_name = f"{vendor}_{po_number}_{due_date}_{msf}.pdf"
                
                origin_path = os.path.join(self.path, file_name)
                new_path = os.path.join(self.path, new_name)
                
                if origin_path != new_path:
                    os.rename(origin_path, new_path)
                    logger.info(f"Renamed {file_name} to {new_name}")
                    
            except Exception as e:
                logger.error(f"Error renaming file {file_name}: {e}", exc_info=True)


def main() -> None:
    """Main entry point."""
    try:
        reader = PDFReader()
        reader.extract_files_info()
    except Exception as e:
        logger.error(f"Fatal error in main: {e}", exc_info=True)


if __name__ == '__main__':
    main()