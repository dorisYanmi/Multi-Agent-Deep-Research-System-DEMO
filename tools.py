import os
import json
import re
import requests
import feedparser
import urllib.parse

import google.generativeai as genai
from crewai_tools import SerperDevTool

# ==============================
# API Keys
# ==============================
# from API_keys import add_API_keys
# add_API_keys()

# reports directory
md_dir = "./reports"

if not os.path.exists(md_dir):
    os.makedirs(md_dir)

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

model = genai.GenerativeModel("gemini-2.5-flash")

serper = SerperDevTool()

MAX_CALLS = 20

# ==============================
# Prompt Debug Switch
# ==============================
PRINT_PROMPTS = False  # Set to True to print all prompts

def print_prompt(agent_name, prompt_text):
    """Print the prompt if PRINT_PROMPTS is True"""
    if PRINT_PROMPTS:
        print(f"\n{'='*80}")
        print(f"PROMPT - Agent: {agent_name}")
        print(f"{'='*80}")
        print(prompt_text)
        print(f"{'='*80}\n")

        
# ==============================
# Coordinator Call Logger
# ==============================
coordinator_call_history = []

# Simple loop limit counter
coordinator_call_counter = 0

def log_coordinator_call(agent_name, instruction, timestamp=None):
    """Log coordinator's agent calls"""
    import datetime
    entry = {
        "timestamp": timestamp or datetime.datetime.now().isoformat(),
        "agent": agent_name,
        "instruction": instruction
    }
    coordinator_call_history.append(entry)


def print_coordinator_call_history():
    """Print coordinator call history"""
    if not coordinator_call_history:
        print("No coordinator calls recorded.")
        return
    
    print("\n" + "="*80)
    print("COORDINATOR CALL HISTORY")
    print("------------------------")
    
    # Print as agent chain
    agent_chain = " -> ".join(entry['agent'] for entry in coordinator_call_history)
    print(f"Agent Chain: {agent_chain}")
    
    print("\n" + "="*80)


# ==============================
# Logging Helpers
# ==============================

def print_agent_header(name):
    print("\n" + "-" * 50)
    print(name)
    print("-" * 50)


def log(msg):
    print(f"[LOG] {msg}")



# ==============================
# Utility
# ==============================

def extract_json(text):

    match = re.search(r"\{.*\}|\[.*\]", text, re.S)

    if match:
        return json.loads(match.group())

    return json.loads(text)


# ==============================
# Search Tools
# ==============================

def serper_search(query):

    res = serper.run(search_query=query)

    if isinstance(res, dict):

        texts = []

        for r in res.get("organic", [])[:5]:

            texts.append(
                f"Title: {r.get('title')}\n"
                f"Snippet: {r.get('snippet')}\n"
                f"URL: {r.get('link')}"
            )

        return texts

    return [str(res)]


def tavily_search(query):

    url = "https://api.tavily.com/search"

    params = {
        "api_key": os.environ["TAVILY_API_KEY"],
        "query": query,
        "search_depth": "advanced"
    }

    r = requests.get(url, params=params)

    data = r.json()

    results = []

    for res in data.get("results", []):

        results.append(
            f"Title: {res.get('title')}\n"
            f"Content: {res.get('content')}\n"
            f"URL: {res.get('url')}"
        )

    return results


def arxiv_search(query: str, max_results: int = 5):
    base_url = "http://export.arxiv.org/api/query"
    # use all as search prefix
    search_query = f"all:{query}"
    url = f"{base_url}?search_query={urllib.parse.quote(search_query)}&start=0&max_results={max_results}&sortBy=relevance&sortOrder=descending"
    
    response = requests.get(url, timeout=50)
    feed = feedparser.parse(response.content)
    results = []
    for entry in feed.entries:
        results.append({
            "title": entry.get("title", "N/A"),
            "summary": entry.get("summary", "N/A"),
            "url": entry.get("link", "N/A")
        })
    return results if results else ["No papers found"]
