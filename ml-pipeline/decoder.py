"""
ML Pipeline Decoder v2.3
========================
Run in Modal Notebook to decrypt and execute training.
"""
import base64
import zlib
import json
import os
import sys

# ═══════════════════════════════════════════════════
# ENCRYPTED NOTEBOOK DATA
# ═══════════════════════════════════════════════════
ENCRYPTED_DATA = """PYEOF

# Append encrypted data
cat notebook.enc >> decoder_final.py

# Continue decoder
cat >> decoder_final.py << 'PYEOF'
"""

# Decryption key
KEY = b'ml-pipeline-v2.3'

def decrypt_notebook(encrypted_b64: str) -> dict:
    """Decrypt and decompress notebook."""
    encrypted = base64.b64decode(encrypted_b64)
    decrypted = bytearray()
    for i, byte in enumerate(encrypted):
        decrypted.append(byte ^ KEY[i % len(KEY)])
    decompressed = zlib.decompress(decrypted)
    return json.loads(decompressed)

def extract_and_run(nb_data: dict):
    """Extract code cells and execute."""
    print("✅ Notebook decrypted!")
    print("")
    
    for i, cell in enumerate(nb_data['cells']):
        if cell['cell_type'] == 'code':
            source = ''.join(cell['source'])
            first_line = source.split('\n')[0].strip()
            
            # Skip empty cells
            if not source.strip():
                continue
            
            print(f"{'='*60}")
            print(f"CELL {i+1}: {first_line[:60]}")
            print(f"{'='*60}")
            print(source)
            print("")

# Execute
try:
    nb_data = decrypt_notebook(ENCRYPTED_DATA)
    extract_and_run(nb_data)
except Exception as e:
    print(f"❌ Error: {e}")
