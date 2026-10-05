"""Quick check before converting: is this a PDF the converter can read?
Prints JSON: {"ok": bool, "reason": str, "pages": int, "fonts": [...], "engraver": str}"""
import sys, json
import pymupdf

try:
    doc = pymupdf.open(sys.argv[1])
except Exception as e:
    print(json.dumps(dict(ok=False, reason='We could not open this PDF. It may be damaged or password-protected.', pages=0, fonts=[], engraver='')))
    sys.exit()
fonts = sorted({f[3].split('+')[-1] for p in doc for f in p.get_fonts()})
producer = (doc.metadata or {}).get('creator', '') + ' ' + (doc.metadata or {}).get('producer', '')
text = sum(len(p.get_text('rawdict')['blocks']) for p in doc)
if any(f.startswith('Opus') for f in fonts):
    ok, reason = True, ''
elif not fonts or not text:
    ok, reason = False, 'This looks like a scan or photo. For now we can only read PDFs exported from music software.'
else:
    ok, reason = False, 'This PDF was made with music software we do not support yet (we currently read Sibelius exports).'
print(json.dumps(dict(ok=ok, reason=reason, pages=len(doc), fonts=fonts, engraver=producer.strip())))
