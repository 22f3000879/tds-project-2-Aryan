# TDS Project 2: Autonomous LLM Analysis Agent

An autonomous AI agent built with **FastAPI** and **OpenAI** capable of solving multi-step data science quizzes. This agent performs web scraping, data analysis, audio transcription, and image generation without human intervention.

## Features

* **Multi-Modal Capabilities:**
    * **Web Scraping:** Recursively fetches HTML, JavaScript imports, and hidden data using `httpx` and Regex.
    * **Audio Processing:** Uses **OpenAI Whisper** to transcribe audio instructions (`.opus`/`.mp3`) on the fly.
    * **Data Analysis:** Parses CSVs in-memory using `pandas` and performs statistical/math operations.
    * **Visualization:** Generates charts using `matplotlib` and returns them as Base64 strings.
* **Advanced Resilience:**
    * **Anti-Hallucination Guardrails:** Custom sanitization logic (`agent.py`) that detects and neutralizes LLM hallucinations (e.g., inventing constants like `7919`).
    * **Recursive Script Fetching:** Automatically downloads and analyzes external JavaScript files (`utils.js`) to understand page logic.
    * **Memory Optimization:** Handles CSVs as streams to prevent memory crashes on limited environments (like Render Free Tier).
* **Asynchronous Architecture:** Built on `FastAPI` with background tasks to handle long-running logic while satisfying immediate HTTP response requirements.

## Tech Stack

* **Python 3.11+**
* **FastAPI / Uvicorn** (API Server)
* **OpenAI API** (GPT-4o-mini for logic, Whisper-1 for audio)
* **Pandas / Numpy** (Data Processing)
* **Httpx** (Async HTTP Client)
* **Matplotlib / Seaborn** (Visualization)

## 📂 Project Structure

```text
.
├── agent.py         # The "Brain": LLM logic, code generation, and sanitization
├── config.py        # Environment variables and configuration
├── main.py          # The "Coordinator": FastAPI endpoints and loop management
├── utils.py         # The "Tools": Scraping, downloading, and audio transcription
├── requirements.txt # Python dependencies
└── README.md        # Documentation
⚙️ Installation & Setup
Clone the repository:

Bash

git clone [https://github.com/22f3000879/tds-project-2-Aryan.git](https://github.com/yourusername/tds-project-2.git)
cd tds-project-2-Aryan
Install dependencies:

Bash

pip install -r requirements.txt
Set up Environment Variables: Create a .env file (or set in your OS/Cloud provider):

Code snippet

OPENAI_API_KEY=sk-your-api-key-here
AIPROXY_TOKEN=your-token (if using a proxy)
Note: You must also update config.py with your Student Email and Secret.

🏃‍♂️ Usage
Running Locally
Start the server using Uvicorn:

Bash

uvicorn main:app --reload
The server will start at http://127.0.0.1:8000.

API Endpoints
POST /
Triggers the quiz solving process. Payload:

JSON

{
  "email": "your_email@ds.study.iitm.ac.in",
  "secret": "your_secret_code",
  "url": "[https://tds-llm-analysis.s-anand.net/demo](https://tds-llm-analysis.s-anand.net/demo)"
}
GET /
Health check endpoint. Returns status 200 if the agent is active.

🧠 How It Works
Receive Task: The API receives a starting URL.

Fetch & Decode: utils.py fetches the HTML. It uses Regex to find hidden atob() content, downloads external scripts (<script src="...">), and transcribes any audio instructions (<audio>).

Analyze: agent.py uses the LLM to determine the task type (Simple Answer, JS Logic, or Audio/CSV).

Generate Code: The LLM generates a Python script to solve the specific problem.

Sanitize & Execute: The code is passed through a Sanitizer to remove network calls and fix known hallucinations (like fake math formulas). It is then executed in a secure local scope.

Submit: The result is POSTed back to the server. If correct, the agent proceeds to the next step automatically.

🛡️ License
This project is licensed under the MIT License.
