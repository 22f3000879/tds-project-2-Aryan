import json
import re
import traceback
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL, STUDENT_EMAIL

client = OpenAI(api_key=OPENAI_API_KEY)

def analyze_task(decoded_html: str):
    prompt = f"""
    You are a scraper parser. Extract strictly valid JSON.
    Keys: "question", "submit_url", "file_url".
    CONTENT: {decoded_html[:15000]}
    """
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL, messages=[{"role": "user", "content": prompt}], temperature=0
        )
        content = response.choices[0].message.content.strip()
        if "```" in content: content = content.split("```")[1].replace("json", "")
        return json.loads(content.strip())
    except: return None

def sanitize_code(code: str):
    # Remove network libraries
    code = re.sub(r'^import requests.*$', '', code, flags=re.MULTILINE)
    code = re.sub(r'^import urllib.*$', '', code, flags=re.MULTILINE)
    # Force Synchronous
    code = code.replace("async def ", "def ")
    code = code.replace("await ", "")
    # Remove specific hallucinated function calls if found
    if "7919" not in code and "demo2_key" in code:
        code = re.sub(r'demo2_key\(.*?\)', 'email_number(email)', code)
    return code

def solve_question(question: str, file_summary: str, page_content: str = ""):
    prompt = f"""
    You are a Python Expert. Write a Python script to calculate the answer.
    
    QUESTION: {question}
    Student Email: "{STUDENT_EMAIL}"
    
    --- DATA / SCRIPTS / TRANSCRIPTS ---
    {file_summary}
    
    --- PAGE CONTENT ---
    {page_content[:10000]}
    
    STRICT INSTRUCTIONS:
    1. **SCENARIO A (Anything):** If JSON sample says "answer": "anything", write: `solution = "anything you want"`
    
    2. **SCENARIO B (Secret Code):** - Implement logic from "IMPORTED FILE" (e.g. `emailNumber`) 1:1.
       - Do NOT use `demo2_key` or `7919` unless seen in text.
    
    3. **SCENARIO C (Audio/CSV):**
       - Read "AUDIO TRANSCRIPT" for the rule.
       - **CSV HANDLING:** The CSV data is provided in the variable `file_summary` (passed as a string). 
       - **DO NOT read a file from disk.** Use `io.StringIO`.
       - Example:
         ```python
         import pandas as pd
         import io
         # 'file_summary' variable contains the CSV text
         # We need to strip non-CSV parts first if it has headers like "CSV CONTENT:"
         csv_text = "{file_summary}".split("CSV CONTENT:")[-1].strip()
         df = pd.read_csv(io.StringIO(csv_text))
         ```
       - **Cutoff:** If the page mentions `emailNumber()`, implement that function (from utils.js logic) to calculate the cutoff.
       - Calculate the result. `solution = int(result)`.

    4. **OUTPUT:** Return ONLY the Python code block.
    """
    
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL, messages=[{"role": "user", "content": prompt}], temperature=0
        )
        content = response.choices[0].message.content.strip()
        
        # Extract Code
        code_match = re.search(r"```python\n(.*?)```", content, re.DOTALL)
        code = code_match.group(1) if code_match else content.replace("```python", "").replace("```", "")
        
        # Sanitize
        code = sanitize_code(code)
        print(f"DEBUG: Sanitized Python Code:\n{code}")
        
        # Execute
        scope = {"__builtins__": __builtins__, "import": __import__, "email": STUDENT_EMAIL}
        exec(code, scope, scope)
        
        return scope.get("solution")

    except Exception as e:
        print(f"Solve Error: {e}")
        traceback.print_exc()
        return "Error"
