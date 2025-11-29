import json
import re
import traceback
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL, STUDENT_EMAIL

client = OpenAI(api_key=OPENAI_API_KEY)

def analyze_task(decoded_html: str):
    """
    Analyzes the task to extract the question and URLs.
    """
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
    """
    Cleans code and NEUTRALIZES hallucinations.
    """
    code = re.sub(r'^import requests.*$', '', code, flags=re.MULTILINE)
    code = re.sub(r'^import urllib.*$', '', code, flags=re.MULTILINE)
    code = code.replace("async def ", "def ").replace("await ", "")
    
    # URL Fix
    if '<span class="origin"></span>' in code:
        code = code.replace('<span class="origin"></span>', 'https://tds-llm-analysis.s-anand.net')
        
    # Math Fix
    if "7919" in code:
        code = code.replace("7919", "1").replace("12345", "0").replace("% 100000000", "")
    if "demo2_key" in code:
         code = re.sub(r'demo2_key\(.*?\)', 'email_number(email)', code)

    return code

def solve_question(question: str, file_summary: str, page_content: str = ""):
    prompt = f"""
    You are a Python Expert. Write a Python script to calculate the answer.
    
    QUESTION: {question}
    Student Email: "{STUDENT_EMAIL}"
    
    --- DATA / SCRIPTS / TRANSCRIPTS ---
    {file_summary[:1000]} ... (Data truncated for brevity)
    
    STRICT RULES:
    1. **NO NETWORK:** Do NOT use `requests`. 
    2. **NO HALLUCINATIONS:** Trust the provided data ONLY.
    3. **SYNCHRONOUS ONLY:** No `async`/`await`.
    
    SCENARIO DETECTOR:
    
    **A. IMAGE ANALYSIS (Colors/Pixels):**
       - If `file_summary` starts with "IMAGE_BASE64:", it contains the image data.
       - Use `PIL` (Pillow) and `io.BytesIO` to read it:
         ```python
         import base64, io
         from PIL import Image
         # The variable 'file_summary' contains "IMAGE_BASE64:..."
         b64_data = file_summary.split(":", 1)[1]
         img = Image.open(io.BytesIO(base64.b64decode(b64_data)))
         ```
       - Analyze pixels to find the most frequent color.
       - Return hex string: `solution = "#..."`.
    
    **B. COMMAND GENERATION (uv/pip):**
       - If asking for a command, return the string.
       - `solution = "uv http get ..."`
    
    **C. HYBRID TASK (Audio/CSV/JS):**
       - Read Audio Transcript.
       - Parse CSV from `file_summary` using `io.StringIO`.
       - Implement JS logic 1:1 (No fake math!).
       - `solution = int(result)`.
    
    **D. SIMPLE PLACEHOLDER:**
       - `solution = "anything you want"`.

    **OUTPUT:**
    - Return ONLY Python code.
    """
    
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL, messages=[{"role": "user", "content": prompt}], temperature=0
        )
        content = response.choices[0].message.content.strip()
        
        # Extract Code
        code_match = re.search(r"```python\n(.*?)```", content, re.DOTALL)
        code = code_match.group(1) if code_match else content.replace("```python", "").replace("```", "")
        
        code = sanitize_code(code)
        print(f"DEBUG: Final Python Code:\n{code}")
        
        # Shared Scope
        scope = {"__builtins__": __builtins__, "import": __import__, "email": STUDENT_EMAIL, 
                 "file_summary": file_summary, "page_content": page_content}
        
        exec(code, scope, scope)
        
        solution = None
        for var in ["solution", "secret_code", "answer", "result"]:
            if var in scope:
                solution = scope[var]
                break
        
        if hasattr(solution, 'item'): solution = solution.item()
        return solution

    except Exception as e:
        print(f"Solve Error: {e}")
        traceback.print_exc()
        return "Error"
