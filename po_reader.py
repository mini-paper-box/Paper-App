import re
import pdfplumber

def extract_text_lines_from_pdf(file_path):
    lines = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            # print(text)
            if text:
                lines.extend(text.splitlines())
    return lines

def find_lines_with_pattern(file_path, pattern):
    lines = extract_text_lines_from_pdf(file_path)
    matching_lines = [line for line in lines if re.search(pattern, line, re.IGNORECASE)]
    return matching_lines

def find_date(file_path):
    lines = extract_text_lines_from_pdf(file_path)
    date_pattern = r'\b(?:\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{1,2}-\d{1,2}|\d{1,2}-\d{1,2}-\d{4})\b|\b\d{2}-[A-Za-z]{3}-\d{2}\b|\b\d{2}[\-–−][A-Z]{3}[\-–−]\d{2}\b'
    result=[]
    for line in lines:
        match = re.findall(date_pattern, line)
        if match:
            result.extend(match)
    return result

def find_material(file_path, pattern):
    lines = extract_text_lines_from_pdf(file_path)
    result = []
    print(lines)
    # for line in lines:
    #     match = re.findall(pattern, lines, re.IGNORECASE)
    #     if match:
    #         result.extend(match)
    # return result
    return re.findall(pattern, " ".join(lines), re.IGNORECASE)

# Example usage
pdf_path = 'example.pdf'

keywords = ["Clay Coated White 2 Sides", 
            "Clay METSA KBW 2 Sides", 
            "Clay METSA KraftBack White 2 Sides", 
            "Clay METSA KraftBack White",
            "Coated White 2 Sides","Coated White 1S",
            "OY", "Oyster", "Whitetop", "WT", "BW", "Kemi",
            "OY 2 Sides", "Oyster 2 Sides", "Whitetop 2 Sides", "WT 2 Sides", "BW 2 Sides", "Kemi 2 Sides",
            "OY 2S", "Oyster 2S", "Whitetop 2S", "WT 2S", "BW 2S", "Kemi 2S",
            ]

# Join keywords with | and escape special regex characters
pattern = r"|".join(re.escape(keyword) for keyword in keywords)

result = find_material(pdf_path, pattern)
print(result)

regex_pattern = r'\b\d{7,8}-\S*'  # Match 7 digits + hyphen + optional trailing content

results = find_lines_with_pattern(pdf_path, regex_pattern)

