import re
import base64
import httpx
from io import BytesIO
from pypdf import PdfReader
import pandas as pd
from urllib.parse import urljoin
from config import STUDENT_EMAIL

def try_decode_base64(text: str):
    """
    Helper to find and decode base64 strings in any text.
    """
    candidates = re.findall(r'[`\'"]([A-Za-z0-9+/=\s]{100,})[`\'"]', text)
    if candidates:
        encoded = max(candidates, key=len)
        try:
            decoded = base64.b64decode(encoded).decode('utf-8')
            return decoded.replace("$EMAIL", STUDENT_EMAIL)
        except:
            pass
    return text

def fetch_external_scripts(base_url, text):
    """
    Finds and downloads scripts referenced via <script src="..."> OR import ... from "..."
    """
    extra_content = ""
    
    # 1. Find <script src="...">
    script_srcs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', text)
    
    # 2. Find JS imports: import ... from "./utils.js"
    js_imports = re.findall(r'from\s+["\']([^"\']+)["\']', text)
    
    all_refs = script_srcs + js_imports
    
    for ref in all_refs:
        # Build full URL
        full_url = urljoin(base_url, ref)
        try:
            # Download the script/import
            resp = httpx.get(full_url, timeout=10)
            script_text = resp.text
            extra_content += f"\n\n--- IMPORTED FILE ({ref}) ---\n{script_text}"
            
            # RECURSIVE CHECK: Does this new file have imports too? (Go 1 level deeper)
            nested_imports = re.findall(r'from\s+["\']([^"\']+)["\']', script_text)
            for nested in nested_imports:
                nested_url = urljoin(full_url, nested)
                try:
                    nested_resp = httpx.get(nested_url, timeout=10)
                    extra_content += f"\n\n--- NESTED IMPORT ({nested}) ---\n{nested_resp.text}"
                except:
                    pass
                    
        except Exception as e:
            print(f"Failed to fetch {ref}: {e}")
            
    return extra_content

async def fetch_and_decode_page(url: str):
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url)
        response.raise_for_status()
        html = response.text
    
    # Check for external scripts on the main page too
    extras = fetch_external_scripts(url, html)
    return try_decode_base64(html + extras)

def parse_file_content(file_url: str):
    try:
        if "$EMAIL" in file_url:
            file_url = file_url.replace("$EMAIL", STUDENT_EMAIL)

        response = httpx.get(file_url, timeout=30)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "").lower()

        if "pdf" in content_type or file_url.endswith(".pdf"):
            reader = PdfReader(BytesIO(response.content))
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return f"PDF CONTENT:\n{text}"
        
        elif "csv" in content_type or file_url.endswith(".csv"):
            df = pd.read_csv(BytesIO(response.content))
            return f"CSV CONTENT:\n{df.head(50).to_string()}"
        
        else:
            main_text = response.text
            # --- THE FIX: Fetch scripts and imports recursively ---
            extras = fetch_external_scripts(file_url, main_text)
            combined_text = main_text + extras
            
            decoded = try_decode_base64(combined_text)
            return f"SCRAPED CONTENT:\n{decoded[:20000]}"

    except Exception as e:
        return f"Error reading file: {e}"
