import re
import base64
import httpx
from io import BytesIO
from pypdf import PdfReader
import pandas as pd
from config import STUDENT_EMAIL

async def fetch_and_decode_page(url: str):
    """
    Fetches HTML and hunts for hidden Base64 content using multiple Regex patterns.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url)
        response.raise_for_status()
        html = response.text

    # Pattern 1: Direct atob call -> atob("...")
    # Pattern 2: Variable assignment -> const code = "..." (common in these CTFs)
    # We look for a long string (base64-like) inside backticks or quotes.
    
    # Strategy: Find the longest string inside quotes/backticks that looks like Base64.
    # This covers both atob(`...`) and const x = `...`
    candidates = re.findall(r'[`\'"]([A-Za-z0-9+/=\s]{100,})[`\'"]', html)
    
    encoded_content = None
    
    if candidates:
        # Pick the longest candidate, it's almost certainly the hidden content
        encoded_content = max(candidates, key=len)

    if encoded_content:
        try:
            # Decode the base64 string
            decoded_bytes = base64.b64decode(encoded_content)
            decoded_text = decoded_bytes.decode('utf-8')
            
            # --- CRITICAL FIX: Replace variables like $EMAIL ---
            # The page expects JS to do this. We must do it in Python.
            decoded_text = decoded_text.replace("$EMAIL", STUDENT_EMAIL)
            
            return decoded_text
        except Exception as e:
            print(f"Error decoding Base64: {e}")
            return html 
    
    return html

def parse_file_content(file_url: str):
    """
    Downloads content. Handles PDFs, CSVs, AND generic HTML scraping.
    """
    try:
        # Safety check for the $EMAIL variable issue
        if "$EMAIL" in file_url:
            return "Error: The $EMAIL variable was not replaced. decoding failed."

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
            return f"CSV CONTENT (First 50 rows):\n{df.head(50).to_string()}"
        
        else:
            return f"SCRAPED CONTENT:\n{response.text[:10000]}"
            
    except Exception as e:
        return f"Error reading file: {e}"
