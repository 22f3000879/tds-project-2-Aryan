from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
import httpx
import re
import asyncio
from urllib.parse import urljoin
from config import STUDENT_EMAIL, STUDENT_SECRET
from utils import fetch_and_decode_page, parse_file_content
from agent import analyze_task, solve_question

app = FastAPI()

async def run_quiz_process(start_url: str):
    current_url = start_url
    step_count = 0
    
    # 1. Determine the Base Domain (Live Server)
    base_domain = "https://tds-llm-analysis.s-anand.net"
    if "localhost" in start_url or "127.0.0.1" in start_url:
        base_domain = "http://127.0.0.1:8787"
    
    while current_url and step_count < 15:
        print(f"\n--- STEP {step_count + 1} processing {current_url} ---")
        
        try:
            decoded_text = await fetch_and_decode_page(current_url)
        except Exception as e:
            print(f"Failed to fetch page: {e}")
            break
        
        # 2. Analyze the Task
        task_data = analyze_task(decoded_text)
        if not task_data:
            print("Failed to parse task.")
            break
            
        print(f"Task Found: {task_data}")
        
        # 3. Download Files (Fixing 'example.com' traps)
        file_summary = "No files."
        if task_data.get("file_url"):
            raw_f_url = task_data["file_url"]
            # Remove HTML tags if any
            f_url = re.sub(r'<[^>]+>', '', raw_f_url).strip()
            
            if f_url:
                # TRAP FIX: If the LLM extracts 'example.com', force the real domain
                if "example.com" in f_url:
                    f_url = f_url.replace("https://example.com", base_domain).replace("http://example.com", base_domain)
                
                # Handle relative URLs
                if not f_url.startswith("http"): 
                    f_url = urljoin(base_domain, f_url)
                    
                print(f"Downloading file: {f_url}")
                file_summary = parse_file_content(f_url)

        # 4. TARGET URL IS ALWAYS /submit
        # We ignore what the LLM thinks the submit URL is. 
        # The documentation confirms everything goes to /submit.
        submit_url = urljoin(base_domain, "/submit")

        # 5. Solve & Submit
        attempts = 0
        success = False
        
        while attempts < 3 and not success:
            answer = solve_question(task_data["question"], file_summary, decoded_text)
            print(f"Calculated Answer (Attempt {attempts+1}): {answer}")
            
            payload = {
                "email": STUDENT_EMAIL,
                "secret": STUDENT_SECRET,
                "url": current_url,  # The Problem URL
                "answer": answer     # The Solution
            }
            
            try:
                print(f"Submitting to {submit_url}")
                async with httpx.AsyncClient() as client:
                    resp = await client.post(submit_url, json=payload, timeout=30)
                    
                    if resp.status_code != 200:
                        print(f"Server Error {resp.status_code}: {resp.text[:200]}")
                    
                    try:
                        result = resp.json()
                        print(f"Submission Result: {result}")
                        
                        if result.get("correct"):
                            success = True
                            next_url = result.get("url")
                            if next_url:
                                # Ensure next_url is absolute
                                if not next_url.startswith("http"):
                                    next_url = urljoin(base_domain, next_url)
                                current_url = next_url
                                step_count += 1
                            else:
                                print("Quiz Completed Successfully!")
                                return
                        else:
                            print(f"Wrong Answer. Retrying... Reason: {result.get('reason')}")
                            attempts += 1
                            await asyncio.sleep(1)
                    except:
                        print(f"Failed to parse JSON. Raw: {resp.text[:100]}")
                        attempts += 1
                        
            except Exception as e:
                print(f"Submission failed: {e}")
                attempts += 1
        
        if not success:
            print("Failed step after 3 attempts.")
            break

@app.post("/")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    try: data = await request.json()
    except: raise HTTPException(status_code=400, detail="Invalid JSON")
    if data.get("secret") != STUDENT_SECRET: raise HTTPException(status_code=403, detail="Invalid Secret")
    background_tasks.add_task(run_quiz_process, data.get("url"))
    return {"message": "Quiz processing started", "status": "ok"}

@app.get("/")
def health_check():
    return {"status": "active", "student": STUDENT_EMAIL}
