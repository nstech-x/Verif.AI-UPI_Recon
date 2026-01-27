import sys, zipfile, re
from pathlib import Path

docx_path = Path(__file__).parents[1] / 'bank_recon_files' / 'Verif.ai - UPI Functional Document - V1-30.12.2025.doc'
out_path = Path(__file__).parents[1] / 'bank_recon_files' / 'verif_doc_text.txt'

if not docx_path.exists():
    print('DOC not found:', docx_path)
    sys.exit(2)

try:
    with zipfile.ZipFile(docx_path, 'r') as z:
        if 'word/document.xml' not in z.namelist():
            # maybe it's .doc (old) - cannot parse
            print('Not a .docx file or missing document.xml')
            sys.exit(3)
        xml = z.read('word/document.xml').decode('utf-8', errors='ignore')
        # extract text within w:t tags
        texts = re.findall(r'<w:t[^>]*>(.*?)</w:t>', xml, flags=re.DOTALL)
        # join by paragraph breaks
        paras = re.split(r'</w:p>|<w:p[^>]*>', xml)
        # heuristic: group w:t per paragraph
        out_lines = []
        # simpler: just join all w:t with spaces and split into lines by periods
        full = ' '.join(texts)
        # normalize whitespace
        full = re.sub(r'\s+', ' ', full)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(full)
    print('OK', out_path)
except Exception as e:
    print('ERROR', e)
    sys.exit(4)
