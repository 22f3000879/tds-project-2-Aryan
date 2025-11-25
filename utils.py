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
    Helper to find and decode base64 strings in any text (HTML or JS).
    """
    # Look for long strings (100+ chars) inside quotes or backticks
    candidates = re.findall(r'[`\'"]([A-Za-z0-9+/=\s]{100,})[`\'"]', text)
    if candidates:
        # Pick the longest one
        encoded = max(candidates, key=len)
        try:
            decoded = base64.b64decode(encoded).decode('utf-8')
            # Fix variables
            return decoded.replace("$EMAIL", STUDENT_EMAIL)
        except:
            pass
    return text

async def fetch_and_decode_page(url: str):
    """
    Async fetcher for the main quiz loop.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url)
        response.raise_for_status()
        html = response.text
    
    # Try decoding the main page HTML
    return try_decode_base64(html)

def parse_file_content(file_url: str):
    """
    Sync fetcher for files. NOW HANDLES EXTERNAL SCRIPTS.
    """
    try:
        # 1. Handle variable replacement in URL
        if "$EMAIL" in file_url:
            file_url = file_url.replace("$EMAIL", STUDENT_EMAIL)

        response = httpx.get(file_url, timeout=30)
        response.raise_for_status()
        
        content_type = response.headers.get("Content-Type", "").lower()

        # 2. PDF Handler
        if "pdf" in content_type or file_url.endswith(".pdf"):
            reader = PdfReader(BytesIO(response.content))
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return f"PDF CONTENT:\n{text}"
        
        # 3. CSV Handler
        elif "csv" in content_type or file_url.endswith(".csv"):
            df = pd.read_csv(BytesIO(response.content))
            return f"CSV CONTENT:\n{df.head(50).to_string()}"
        
        # 4. HTML/JS Handler (The Fix!)
        else:
            main_text = response.text
            combined_text = main_text
            
            # Look for external scripts: <script src="demo-scrape.js">
            scripts = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', main_text)
            
            for src in scripts:
                # Build full URL for the script
                script_url = urljoin(file_url, src)
                try:
                    # Download the script content
                    js_resp = httpx.get(script_url, timeout=10)
                    combined_text += f"\n\n--- EXTERNAL SCRIPT ({src}) ---\n{js_resp.text}"
                except Exception as e:
                    print(f"Failed to fetch script {src}: {e}")

            # Now try to decode the COMBINED content (HTML + JS)
            decoded = try_decode_base64(combined_text)
            
            return f"SCRAPED CONTENT:\n{decoded[:15000]}"

    except Exception as e:
        return f"Error reading file: {e}"
