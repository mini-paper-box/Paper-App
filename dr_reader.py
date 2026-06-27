import re
import pdfplumber
from typing import List, Tuple, Optional
from settings import *


class DeliveryReceiptReader:
    """Extracts purchase order numbers and quantities from delivery receipt PDFs."""
    
    # Regex patterns as class constants for clarity
    PO_PATTERN = r'\b\d{7,8}-\S*'  # 7-8 digits followed by hyphen and optional content
    QTY_PATTERN = r'(?<=\s)([0-9,]+)$'  # Numbers at end of line (with commas)
    DATE_PATTERN = r'\b(?:\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{1,2}-\d{1,2}|\d{1,2}-\d{1,2}-\d{4})\b'
    COMBINED_PATTERN = r'\b\d{7,8}-\S*|\bOrder Total \d{2,5}\b'
    
    def __init__(self):
        self.path = DR_PATH

    def extract_text_lines_from_pdf(self, file_path: str) -> List[str]:
        """Extract all text lines from a PDF file."""
        lines = []
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    print(text)
                    if text:
                        lines.extend(text.splitlines())
        except Exception as e:
            print(f"Error reading PDF {file_path}: {e}")
            return []
        
        return lines

    def find_lines_with_pattern(self, file_path: str, pattern: str) -> List[str]:
        """Find all lines matching a given regex pattern."""
        lines = self.extract_text_lines_from_pdf(file_path)
        matching_lines = [line for line in lines if re.search(pattern, line, re.IGNORECASE)]
        return matching_lines

    def find_date_with_pattern(self, file_path: str, pattern: str) -> Optional[str]:
        """Find the first date matching the given pattern."""
        lines = self.extract_text_lines_from_pdf(file_path)
        for line in lines:
            match = re.search(pattern, line)
            if match:
                return match.group()
        return None

    def _extract_po_and_qty(self, line: str) -> Optional[Tuple[str, str]]:
        """
        Extract PO number and quantity from a single line.
        Returns (po_number, quantity) or None if not found.
        """
        match_po = re.search(self.PO_PATTERN, line)
        match_qty = re.search(self.QTY_PATTERN, line)
        
        if match_po and match_qty:
            po = match_po.group().replace("/", "")
            qty = match_qty.group().replace(",", "")
            return (po, qty)
        
        return None

    def reader(self, file_path: str) -> Tuple[List[Tuple[str, str]], Optional[str]]:
        """
        Extract PO numbers, quantities, and date from delivery receipt PDF.
        
        Returns:
            Tuple of (list_of_po_qty_tuples, date_string)
        """
        results = self.find_lines_with_pattern(file_path, self.COMBINED_PATTERN)
        print(results)
        list_po = []
        temp_po = ""
        
        for line in results:
            # Try to extract both PO and qty from same line
            po_qty = self._extract_po_and_qty(line)
            if po_qty:
                list_po.append(po_qty)
                temp_po = ""
                continue
            
            # Check if line has PO without quantity
            match_po = re.search(self.PO_PATTERN, line)
            if match_po:
                temp_po = match_po.group().replace("/", "")
                continue
            
            # Check if line has quantity (to pair with previous PO)
            if temp_po:
                match_qty = re.search(self.QTY_PATTERN, line)
                if match_qty:
                    qty = match_qty.group().replace(",", "")
                    list_po.append((temp_po, qty))
                    temp_po = ""
        
        # Extract date from the document
        date = self.find_date_with_pattern(file_path, self.DATE_PATTERN)
        
        return list_po, date

    def process_delivery_receipt(self, file_path: str) -> dict:
        """
        Process a delivery receipt and return structured data.
        
        Returns:
            Dictionary with 'po_items' and 'date' keys
        """
        po_items, date = self.reader(file_path)
        
        return {
            'po_items': [{'po_number': po, 'quantity': qty} for po, qty in po_items],
            'date': date,
            'file_path': file_path
        }


def main() -> None:
    reader = DeliveryReceiptReader()
    
    # Example usage
    try:
        result = reader.process_delivery_receipt(DR_PATH)
        print(f"Found {len(result['po_items'])} PO items")
        print(f"Date: {result['date']}")
        for item in result['po_items']:
            print(f"  PO: {item['po_number']}, Qty: {item['quantity']}")
    except Exception as e:
        print(f"Error processing delivery receipt: {e}")


if __name__ == "__main__":
    main()