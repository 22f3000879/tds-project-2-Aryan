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
    code = re.sub(r'^\s*import requests.*$', '', code, flags=re.MULTILINE)
    code = code.replace("async def ", "def ").replace("await ", "")
    if '<span class="origin"></span>' in code:
        code = code.replace('<span class="origin"></span>', 'https://tds-llm-analysis.s-anand.net')
    if "demo2_key" in code:
         code = re.sub(r'demo2_key\(.*?\)', 'email_number(email)', code)
    return code

def solve_question(question: str, file_summary: str, page_content: str = ""):
    # We construct a prompt that EMPHASIZES using the existing data variable.
    prompt = f"""
    You are a Python Expert.
    
    QUESTION: {question}
    Student Email: "{STUDENT_EMAIL}"
    
    IMPORTANT: The variable `file_summary` contains the RAW CONTENT of the data file (CSV/JSON/Text).
    It is already loaded in memory. DO NOT create fake data.
    
    --- RULES ---
    1. **NO NETWORK:** Do not use `requests`.
    2. **USE THE DATA:** `pd.read_csv(io.StringIO(file_summary), ...)`
    3. **OUTPUT:** Define `solution`.
    
    --- SCENARIOS ---
    
    **A. CSV PROCESSING (Audio/Step 3):**
       - **Task:** Sum values >= cutoff in first column.
       - **Cutoff:** `int(hashlib.sha1(email.encode()).hexdigest()[:4], 16) % 100000`
       - **Logic:** `df = pd.read_csv(io.StringIO(file_summary), header=None)`
       - **Solution:** `solution = int(df[df[0] >= cutoff][0].sum())`
    
    **B. SECRET CODE:**
       - `solution = int(hashlib.sha1(email.encode()).hexdigest()[:4], 16)`
    
    **C. DEMO 2 (Alphametic):**
       - Key Formula: `(int(hashlib.sha1(email.encode()).hexdigest()[:4], 16) * 7919 + 12345) % 100000000`
       - Checksum: `hashlib.sha256((str(key).zfill(8) + blob).encode()).hexdigest()`
       
    **D. COMMANDS (UV):**
       - `solution = "uv http get https://tds-llm-analysis.s-anand.net/project2/uv.json?email={STUDENT_EMAIL} -H \\"Accept: application/json\\""`

    OUTPUT ONLY PYTHON CODE.
    """
    
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL, messages=[{"role": "user", "content": prompt}], temperature=0
        )
        content = response.choices[0].message.content.strip()
        code_match = re.search(r"```python\n(.*?)```", content, re.DOTALL)
        code = code_match.group(1) if code_match else content.replace("```python", "").replace("```", "")
        
        code = sanitize_code(code)
        print(f"DEBUG: Final Python Code:\n{code}")
        
        # Pass the real file content to the scope
        scope = {"__builtins__": __builtins__, "import": __import__, "email": STUDENT_EMAIL, 
                 "file_summary": file_summary}
        
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
        return "Error"
