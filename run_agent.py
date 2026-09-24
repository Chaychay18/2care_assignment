import sys
from dotenv import load_dotenv
from agent.scheduler import run_interactive

load_dotenv()

if __name__ == "__main__":
    provider = sys.argv[1] if len(sys.argv) > 1 else "groq"
    prompt   = sys.argv[2] if len(sys.argv) > 2 else "agent/prompts/v1.txt"
    run_interactive(prompt, provider)
