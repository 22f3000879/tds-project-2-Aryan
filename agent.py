import json
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL

client = OpenAI(api_key=OPENAI_API_KEY)

# In agent.py

def analyze_task(decoded_html: str):
    """
    Step 1: Look at the decoded HTML and extract the structure.
    """
    prompt = f"""
    You are a scraper parser. 
    Analyze this HTML/Text content (which was decoded from a hidden script).
    
    Extract strictly valid JSON with these keys:
    - "question": The main question text.
    - "submit_url": The URL found in the text where the answer must be POSTed.
    - "file_url": Look for <a href="..."> links. If a file (PDF/CSV) needs to be downloaded, put the URL here. If none, null.
    
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
        
        # --- ROBUST JSON CLEANING START ---
        # 1. Find the first '{'
        start_index = content.find("{")
        # 2. Find the last '}'
        end_index = content.rfind("}")
        
        if start_index != -1 and end_index != -1:
            # Slice strictly between { and }
            json_str = content[start_index : end_index + 1]
            return json.loads(json_str)
        else:
            print(f"No JSON found in LLM response: {content}")
            return None
        # --- ROBUST JSON CLEANING END ---

    except Exception as e:
        print(f"Parse Error: {e}")
        # Print the raw content to see what went wrong
        print(f"Raw LLM Output: {content}") 
        return None

def solve_question(question: str, file_summary: str):
    """
    Step 2: Answer the question based on the question text and file content.
    """
    prompt = f"""
    You are a Data Science assistant. 
    Calculate the answer to this question.
    
    QUESTION: {question}
    
    DATA CONTEXT:
    {file_summary}
    
    Return STRICT JSON format:
    {{
        "answer": <YOUR_ANSWER_HERE>
    }}
    If the answer is a number, return a number. If text, return text.
    """
    
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        content = response.choices[0].message.content.strip()
        content = content.replace("```json", "").replace("```", "").strip()
        return json.loads(content)["answer"]
    except Exception as e:
        print(f"Solve Error: {e}")
        return None
