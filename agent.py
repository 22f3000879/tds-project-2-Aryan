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
    CONTENT:
    {decoded_html[:15000]}
    """
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        content = response.choices[0].message.content.strip()
        if "```" in content:
            content = content.split("```")[1].replace("json", "")
        return json.loads(content.strip())
    except:
        return None

def solve_question(question: str, file_summary: str, page_content: str = ""):
    """
    Solves the question by generating and EXECUTING Python code.
    """
    prompt = f"""
    You are a Python Expert. Write a Python script to calculate the answer.
    
    QUESTION: {question}
    Student Email: "{STUDENT_EMAIL}"
    
    --- DATA / SCRIPTS (JS Logic) ---
    {file_summary}
    
    --- PAGE CONTENT ---
    {page_content[:10000]}
    
    STRICT INSTRUCTIONS:
    1. **NO NETWORK CALLS:** Do NOT use `requests`, `urllib`, or any network library. You are a calculator.
    2. **NO HALLUCINATIONS:** Only implement logic found in the provided "IMPORTED FILE" or "NESTED IMPORT" sections. Do not invent functions like "demo2_key" unless they are in the text.
    3. **TRANSLATE JS TO PYTHON:**
       - Look for the main function called in the JS (e.g., `await emailNumber()`).
       - Find that function's definition in the imported files.
       - Translate that SPECIFIC logic (math, string slicing, sha1) into Python.
       - If the JS imports `sha1` from `utils.js`, write a Python `sha1` function.
    4. **STEP 1 HANDLING:** If the question is just "POST this JSON" with no math, just write: `solution = "anything"`
    5. **OUTPUT:**
       - Define a variable `solution` with the final answer.
       - Return ONLY the Python code block.
    """
    
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        content = response.choices[0].message.content.strip()
        
        # Extract Python Code
        code_match = re.search(r"```python\n(.*?)```", content, re.DOTALL)
        if code_match:
            code = code_match.group(1)
        else:
            code = content.replace("```python", "").replace("```", "")
            
        print(f"DEBUG: Generated Python Code:\n{code}")
        
        # Execute Code
        local_scope = {"email": STUDENT_EMAIL}
        
        try:
            exec(code, {"__builtins__": __builtins__, "import": __import__}, local_scope)
        except Exception as e:
            print(f"Execution Error: {e}")
            traceback.print_exc()
            return "Error executing code"
            
        # Retrieve Solution
        answer = local_scope.get("solution")
        print(f"DEBUG: Execution Result (solution): {answer}")
        
        return answer

    except Exception as e:
        print(f"Solve Error: {e}")
        return "Error"
