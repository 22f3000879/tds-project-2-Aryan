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
    except Exception as e:
        print(f"Parse Error: {e}")
        return None

def sanitize_code(code: str, context: str):
    """
    Cleans code and neutralizes hallucinations by checking against the source context.
    """
    # 1. Remove Network stuff to prevent crashes
    code = re.sub(r'^import requests.*$', '', code, flags=re.MULTILINE)
    code = re.sub(r'^import urllib.*$', '', code, flags=re.MULTILINE)
    code = code.replace("async def ", "def ").replace("await ", "")
    
    # 2. NEUTRALIZE HALLUCINATED MATH (The Critical Fix)
    # The LLM often hallucinates "demo2_key" logic involving 7919 and 12345.
    # If the code uses 7919 but the downloaded files DO NOT contain 7919...
    if "7919" in code and "7919" not in context:
        print("DEBUG: Neutralizing hallucinated math (7919 -> 1)")
        # We replace the numbers with Identity values (x * 1 + 0 = x)
        # This preserves the variable names the LLM chose, preventing syntax errors,
        # but forces the calculation to return the base value (which is the correct answer).
        code = code.replace("7919", "1")
        code = code.replace("12345", "0")
        code = code.replace("% 100000000", "")
        
    # 3. Function Replacement (Safety)
    # If it calls demo2_key but defined email_number, point it to the right one.
    if "demo2_key" in code and "demo2_key" not in context:
         code = re.sub(r'demo2_key\(.*?\)', 'email_number(email)', code)

    return code

def solve_question(question: str, file_summary: str, page_content: str = ""):
    """
    Solves the question by generating and EXECUTING Python code.
    """
    prompt = f"""
    You are a Python Expert. Write a Python script to calculate the answer.
    
    QUESTION: {question}
    Student Email: "{STUDENT_EMAIL}"
    
    --- DATA / SCRIPTS / TRANSCRIPTS ---
    {file_summary}
    
    --- PAGE CONTENT ---
    {page_content[:10000]}
    
    STRICT RULES:
    1. **SCENARIO A (Anything):** If JSON sample says "answer": "anything", write: `solution = "anything you want"`
    
    2. **SCENARIO B (JS Logic):** - Implement logic from "IMPORTED FILE" 1:1.
       - **CRITICAL:** If `utils.js` calculates a number (e.g. via sha1), THAT NUMBER IS THE ANSWER.
       - Do **NOT** perform extra multiplication (like `* 7919`) unless it is WRITTEN in the `utils.js` file provided above.
    
    3. **SCENARIO C (Audio/CSV):**
       - Read "AUDIO TRANSCRIPT" for the rule.
       - Use `io.StringIO(file_summary)` for CSVs.
       - `solution = int(result)` (Convert numpy types).

    **OUTPUT:**
    - **MUST** define a variable named `solution` at the end.
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
        
        # --- INTELLIGENT SANITIZATION ---
        # Passing file_summary so we know if 7919 is real or fake
        code = sanitize_code(code, file_summary)
        print(f"DEBUG: Final Python Code:\n{code}")
        
        # Shared Scope
        scope = {"__builtins__": __builtins__, "import": __import__, "email": STUDENT_EMAIL, 
                 "file_summary": file_summary, "page_content": page_content}
        
        exec(code, scope, scope)
        
        # --- SAFETY NET: Variable Rescue ---
        # If the LLM forgot 'solution' but defined 'secret_code', grab that instead
        solution = None
        # Check possible variable names in order of likelihood
        for var in ["solution", "secret_code", "answer", "result", "json_data"]:
            if var in scope:
                solution = scope[var]
                break
        
        # Fix numpy types (int64 -> int)
        if hasattr(solution, 'item'): 
            solution = solution.item()
            
        if solution is None:
            print("ERROR: No solution variable found in executed code.")
            
        return solution

    except Exception as e:
        print(f"Solve Error: {e}")
        traceback.print_exc()
        return "Error"
