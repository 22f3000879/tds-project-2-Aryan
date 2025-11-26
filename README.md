TDS Project 2: Autonomous LLM Quiz Agent 🤖
An intelligent, fully automated AI agent capable of solving complex, multi-step data science quizzes. Built for the Tools in Data Science (TDS) course at IIT Madras.

This agent uses FastAPI for handling webhooks and OpenAI (GPT-4o-mini) as the reasoning engine to perform tasks involving web scraping, audio transcription, data analysis, and logic translation.

🚀 Key Capabilities
This agent is designed to handle a specific "Looping Quiz" format, capable of:

🕵️‍♂️ Advanced Web Scraping: Handles dynamic HTML and recursively fetches external resources (JavaScript imports, linked files).

🧠 Logic Translation (JS to Python): Reads JavaScript logic files (e.g., utils.js), translates them into Python, and executes them to reverse-engineer secret codes.

🛡️ Hallucination Guardrails: Implements a custom Code Sanitizer that neutralizes common LLM hallucinations (e.g., preventing the use of training-data constants like 7919 or demo2_key when they aren't present in the source).

🎧 Audio Processing: Detects audio instructions, transcribes them using OpenAI Whisper, and applies the spoken rules to data analysis tasks.

📊 Data Analysis & Visualization: Parses raw CSV data (handling TypeErrors and formatting) and generates visualizations using Matplotlib/Seaborn.

⚡ Asynchronous Architecture: Built on FastAPI with BackgroundTasks to ensure immediate HTTP 200 responses while processing long-running solver tasks.

📂 Project Structure
Bash

.
├── agent.py         # The "Brain": Prompts, Code Generation, and Sanitization Logic
├── config.py        # Configuration and Environment Variables
├── main.py          # FastAPI Application and Recursive Solver Loop
├── utils.py         # "Tools": Recursive Fetching, Audio Transcription, Decoding
├── requirements.txt # Dependencies
└── README.md        # Documentation
🛠️ Architecture & Logic Flow
Trigger: The agent receives a POST request with a Quiz URL.

Fetch & Enrich: utils.py scrapes the page. It recursively follows <script src="..."> and import ... from statements to build a complete context of the problem.

Analyze: The agent determines the task type:

Scenario A: Simple Placeholder submission.

Scenario B: JavaScript Logic puzzle (Crypto/Math).

Scenario C: Hybrid Task (Audio instructions + CSV Data).

Code Generation: The LLM generates a Python script to solve the problem.

Sanitization: The Nuclear Sanitizer strips network calls, enforces synchronous execution, and surgically removes hallucinated math logic.

Execution: The sanitized code is executed in a constrained local scope.

Submission: The calculated solution is POSTed back to the evaluation server.

⚙️ Setup & Installation
Prerequisites
Python 3.9+

An OpenAI API Key

1. Clone the Repository
Bash

git clone https://github.com/22f3000879/tds-project-2-Aryan.git
cd tds-project-2-Aryan
2. Install Dependencies
Bash

pip install -r requirements.txt
3. Configure Environment
Create a .env file (or set system environment variables):

Bash

OPENAI_API_KEY=sk-your-api-key-here
# Student details are configured in config.py or can be added here
4. Run Locally
Bash

uvicorn main:app --reload
The server will start at http://localhost:8000.

☁️ Deployment
This project is optimized for deployment on Render.

Connect your GitHub repository to Render.

Set the Build Command: pip install -r requirements.txt

Set the Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT

Add the OPENAI_API_KEY in the Environment Variables settings.

Important: Set PYTHONUNBUFFERED to 1 in environment variables to see real-time logs.

🧪 Testing
You can test the agent using the REST Client or cURL:

HTTP

POST https://your-app-url.onrender.com/
Content-Type: application/json

{
    "email": "your-student-email",
    "secret": "your-secret",
    "url": "https://tds-llm-analysis.s-anand.net/demo"
}
🛡️ Guardrails & Security
To ensure the agent behaves correctly during evaluation, agent.py includes a Sanitizer that:

Blocks Network Calls: Prevents the generated Python code from using requests (the agent calculates locally).

Enforces Sync: Converts async/await logic to synchronous Python to prevent SyntaxError in exec().

Anti-Hallucination: If the LLM attempts to use logic from previous course iterations (e.g., multiplying by 7919) that isn't present in the current source text, the sanitizer detects and neutralizes the math to ensure the correct answer is derived from the provided files.

📄 License
This project is licensed under the MIT License.
