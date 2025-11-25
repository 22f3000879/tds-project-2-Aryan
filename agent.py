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
    You are a Python Expert. Your task is to write a Python script to calculate the answer.
    
    QUESTION: {question}
    
    --- CONTEXT ---
    Student Email: "{STUDENT_EMAIL}"
    
    --- SCRAPED DATA (JS/HTML/Content) ---
    {file_summary}
    
    --- PAGE CONTENT ---
    {page_content[:10000]}
    
    INSTRUCTIONS:
    1. **Analyze the Logic:**
       - If you see JavaScript logic (e.g. `await emailNumber()`, `sha1`), translate it ACCURATELY into Python.
       - Use standard libraries like `hashlib`, `math`, `re`.
       - If the task is simple (extracting a string), just write python to set the variable.
    2. **Write the Script:**
       - The script MUST define a variable named `solution`.
       - `solution` must contain the final answer (string or number).
    3. **Output:**
       - Return ONLY the Python code block (inside ```python ... ```).
    """
    
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        content = response.choices[0].message.content.strip()
        
        # 1. Extract the Python Code
        code_match = re.search(r"```python\n(.*?)```", content, re.DOTALL)
        if code_match:
            code = code_match.group(1)
        else:
            # Fallback if no markdown
            code = content.replace("```python", "").replace("```", "")
            
        print(f"DEBUG: Generated Python Code:\n{code}")
        
        # 2. Execute the Code
        # We pass the email into the environment so the script can use it
        local_scope = {"email": STUDENT_EMAIL}
        
        try:
            # Use exec() to run the generated code
            exec(code, {"__builtins__": __builtins__, "import": __import__}, local_scope)
        except Exception as e:
            print(f"Execution Error: {e}")
            traceback.print_exc()
            return "Error executing code"
            
        # 3. Retrieve the 'solution' variable
        answer = local_scope.get("solution")
        print(f"DEBUG: Execution Result (solution): {answer}")
        
        return answer

    except Exception as e:
        print(f"Solve Error: {e}")
        return "Error"
