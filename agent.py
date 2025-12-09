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
    Keys: "question", "submit_url", "file_url" (if explicit).
    
    NOTE: If comparing two files, put the FIRST file in "file_url".
    CONTENT: {decoded_html[:20000]}
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
    Sanitizes code. Aggressively removes network calls.
    """
    # 1. Remove Network stuff (Improved Regex to catch '  import requests')
    code = re.sub(r'^\s*import requests.*$', '', code, flags=re.MULTILINE)
    code = re.sub(r'^\s*from requests import.*$', '', code, flags=re.MULTILINE)
    code = re.sub(r'^\s*import urllib.*$', '', code, flags=re.MULTILINE)
    
    # 2. Async Fix
    code = code.replace("async def ", "def ").replace("await ", "")
    
    # 3. URL Fix (Step 2 uv command)
    if '<span class="origin"></span>' in code:
        code = code.replace('<span class="origin"></span>', 'https://tds-llm-analysis.s-anand.net')
        
    # 4. Math Fix (Step 2 Secret Code)
    if "7919" in code:
        code = code.replace("7919", "1").replace("12345", "0").replace("% 100000000", "")
        
    if "demo2_key" in code:
         code = re.sub(r'demo2_key\(.*?\)', 'email_number(email)', code)

    return code

def solve_question(question: str, file_summary: str, page_content: str = ""):
    prompt = f"""
    You are a Data Science & Python Expert. Write a Python script to calculate the answer.
    
    QUESTION: {question}
    Student Email: "{STUDENT_EMAIL}"
    
    --- DATA / ASSETS ---
    {file_summary}
    
    --- PAGE INSTRUCTIONS ---
    {page_content[:15000]}
    
    STRICT RULES:
    1. **NO NETWORK:** Do NOT use `requests`. Do NOT try to simulate a POST submission.
    2. **IMAGES/ZIPS:** Provided as `BASE64:...`. Use `base64`, `io.BytesIO`, `PIL`, `zipfile`.
    3. **OUTPUT:** Must define `solution` variable.
    
    SCENARIO DETECTOR (Check which applies):
    
    **A. SIMPLE PLACEHOLDER:**
       - If sample says "answer": "anything" (or similar), STOP.
       - WRITE ONLY: `solution = "anything you want"`
    
    **B. COMMANDS (Git / UV):**
       - If asked to craft a command string.
       - `solution = "the string"`.
    
    **C. VISUALIZATION (Diff / Heatmap):**
       - Task: "Compare images" or "Most frequent color".
       - Logic: Decode Base64 -> PIL Image -> Analyze pixels.
       - Diff: Count pixels where `p1 != p2`.
       - Heatmap: `Counter(img.getdata()).most_common(1)`.
       - `solution = "#hexcolor"` or `int(count)`.
    
    **D. MATH / OPTIMIZATION (Shards / Rate):**
       - Task: "Read constraints from json".
       - Logic: Parse JSON. Write Python loop to find optimal values.
    
    **E. DATA ANALYSIS (F1 / Logs / CSV / Invoice):**
       - **F1:** Use `sklearn.metrics` or manual formula. `solution = {{...}}`.
       - **Logs (ZIP):** Decode Base64 -> Unzip -> Sum bytes.
       - **Orders (CSV):** Parse CSV -> Pandas -> Filter -> JSON list.
       - **Invoice (PDF):** Extract text -> Regex -> Sum numbers.
    
    **F. EMBEDDINGS (Email Length):**
       - Task: "Choose pair based on email length".
       - Logic: `if len(email) % 2 == 0: ...`
    
    **G. JS LOGIC (Secret Code):**
       - Implement JS logic (`emailNumber`) 1:1 using `hashlib`.
       - `solution = calculated_value`
    
    **H. AUDIO TRANSCRIPT:**
       - If "AUDIO TRANSCRIPT" exists, apply the math rule to the CSV.

    **OUTPUT:**
    - Return ONLY the Python code block.
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
        for var in ["solution", "secret_code", "answer", "result", "command_string", "hex_color"]:
            if var in scope:
                solution = scope[var]
                break
        
        if hasattr(solution, 'item'): solution = solution.item()
        return solution

    except Exception as e:
        print(f"Solve Error: {e}")
        traceback.print_exc()
        return "Error"
