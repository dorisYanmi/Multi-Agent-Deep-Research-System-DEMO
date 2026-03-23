import warnings
warnings.filterwarnings("ignore")

from agents import *

from langgraph.graph import StateGraph, END
import argparse
import random


# ==============================
# saving .md file
# ==============================
def save_report_to_file(state: ResearchState) -> None:
    """
    Saves the final report to a Markdown file with the format report_on-[query].md
    """
    # filename
    safe_query = state["query"].replace(' ', '_').replace('?', '').replace('!', '').replace('.', '').replace(',', '')
    filename = os.path.join(md_dir, f"report_{safe_query}.md")
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(state["final_report"])
        print(f"\nReport saved to: {filename}")
    except Exception as e:
        print(f"Error saving report: {str(e)}")

# ==============================
# Build LangGraph
# ==============================
def route_after_coordinator(state: ResearchState):
    """Route based on coordinator's decision"""
    decision = state.get("coordinator_decision", "planner")
    return decision

def build_graph():
    workflow = StateGraph(ResearchState)

    # 1. add nodes
    workflow.add_node("planner", planner_agent)
    workflow.add_node("researcher", researcher_agent)
    workflow.add_node("reporter", reporter_agent)
    workflow.add_node("coordinator", coordinator_agent)
    workflow.add_node("human_review", human_review)
    workflow.add_node("finalize", finalize)
    workflow.add_node("system_end", system_end)

    # 2. start from coordinator
    workflow.set_entry_point("coordinator")

    # 3. dynamic conditional edges based on coordinator's decision
    workflow.add_conditional_edges(
        "coordinator",
        route_after_coordinator,
        {
            "planner": "planner",
            "researcher": "researcher", 
            "reporter": "reporter",
            "human_review": "human_review",
            "finalize": "finalize",
            "system_end": "system_end"
        }
    )

    # 4. go back to coordinator
    workflow.add_edge("planner", "coordinator")
    workflow.add_edge("researcher", "coordinator")
    workflow.add_edge("reporter", "coordinator")
    workflow.add_edge("human_review", "coordinator")
    workflow.add_edge("finalize", END)
    workflow.add_edge("system_end", END)

    app = workflow.compile()

    return app

def get_random_query():
    """
    Get a random query from queries.txt
    """
    try:
        with open('queries.txt', 'r', encoding='utf-8') as f:
            queries = [line.strip() for line in f if line.strip() and not line.strip().startswith('>>')]
        if queries:
            return random.choice(queries)
        else:
            print("queries.txt is empty. Please add some research queries.")
            return input("Enter research query: ")
    except FileNotFoundError:
        print("queries.txt not found. Creating a new one with sample queries.")
        sample_queries = [
            "How does artificial intelligence transform healthcare?",
            "What are the latest advancements in renewable energy technology?",
            "How does blockchain technology impact supply chain management?",
            "What are the ethical implications of genetic engineering?",
            "How is quantum computing changing cryptography?"
        ]
        with open('queries.txt', 'w', encoding='utf-8') as f:
            f.write('\n'.join(sample_queries))
        return random.choice(sample_queries)


def main():
    # Reset coordinator call counter
    global coordinator_call_counter
    coordinator_call_counter = 0
    
    app = build_graph()
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Multi-Agent Deep Research System')
    parser.add_argument('-r', action='store_true', help='Use a random query from queries.txt')
    parser.add_argument('-q', '--query', nargs='+', help='Use a specific query')
    args = parser.parse_args()
    
    # Determine the query
    if args.r:
        query = get_random_query()
        print(f"Using random query: {query}")
    elif args.query:
        query = ' '.join(args.query)
        print(f"Using specified query: {query}")
    else:
        query = input("Enter research query: ")

    result = app.invoke({
        "query": query,
        "tasks": [],
        "research_results": {},
        "draft_report": "",
        "final_report": "",
        "human_feedback": "",
        "is_approved": False,
        "coordinator_decision": "",
        "history": []
    })

    print("\n\n========== FINAL REPORT ==========\n")

    print(result["final_report"])

    # Print coordinator call history
    print_coordinator_call_history()

    save_report_to_file(result)


if __name__ == "__main__":
    main()
    
