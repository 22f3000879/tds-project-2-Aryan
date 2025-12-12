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
    Sanitizes code. Ensures URLs are correct for the LIVE SERVER.
    """
    code = code.replace("async def ", "def ").replace("await ", "")
    
    # 1. FIX UV COMMAND URL (Force Absolute Live URL)
    # If the Agent writes a relative path '/project2/uv', prepend the live domain.
    if '/project2/uv' in code and 'https://' not in code:
        code = code.replace('/project2/uv', 'https://tds-llm-analysis.s-anand.net/project2/uv')
    
    # 2. REMOVE SPAN ARTIFACTS
    if '<span class="origin"></span>' in code:
        code = code.replace('<span class="origin"></span>', 'https://tds-llm-analysis.s-anand.net')

    # 3. LEGACY FIX (Function Replacement)
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
    
    CAPABILITIES & RULES:
    1. **DATA SOURCES:**
       - **Text/JSON/CSV:** Provided in `file_summary`. Use `io.StringIO` or `json.loads`.
       - **Images/ZIP:** Provided as `BASE64:...`. Use `base64`, `io.BytesIO`, `PIL`, `zipfile`.
       - **External APIs:** You MAY use `requests.get()` if the task requires API access (e.g. GitHub).
    
    2. **SCENARIOS:**
       - **JS LOGIC (Secret Code):**
         - **DEFAULT:** Use **SHA-1**: `int(hashlib.sha1(email.encode()).hexdigest()[:4], 16)`.
         - Only use SHA-256 if `utils.js` explicitly imports `sha256`.
       
       - **COMMANDS (UV / Git):**
         - Return the EXACT command string.
         - For `uv`, ensure the URL is **ABSOLUTE**: `https://tds-llm-analysis.s-anand.net/...`.
       
       - **DEMO 2 (Alphametic):**
         - Re-calculate key: `(base * 7919 + 12345) % 100000000`.
         - Checksum: `hashlib.sha256((key + blob).encode()).hexdigest()`.
         
       - **DATA ANALYSIS (F1 / Logs / CSV / Invoice):**
         - **F1:** Use `sklearn.metrics`. Return JSON dict.
         - **Logs (ZIP):** Decode Base64 -> Unzip -> Sum bytes.
         - **Invoice (PDF):** Extract text -> Regex -> Sum.
         
       - **VISUALIZATION (Heatmap/Diff):**
         - Decode Base64 -> PIL Image -> Analyze pixels.

    **OUTPUT:**
    - Define `solution` variable.
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
        
        # Sanitize
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
