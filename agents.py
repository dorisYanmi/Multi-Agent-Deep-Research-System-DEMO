from tools import *
from typing import TypedDict, List, Dict

# ==============================
# State Definition
# ==============================

class ResearchState(TypedDict):

    query: str
    tasks: List[Dict]
    research_results: Dict
    draft_report: str
    final_report: str
    human_feedback: str
    is_approved: bool
    coordinator_decision: str
    instruction: str
    history: List[Dict]

# ==============================
# Planner Agent
# ==============================

def planner_agent(state: ResearchState):

    print_agent_header("Planner Agent")

    query = state["query"]
    history = state.get("history", [])
    instruction = state.get("instruction", "")

    log(f"Breaking query into tasks: {query}")

    prompt = f"""
You are a research planner, you should break the research query into 3-5 tasks according to the instruction.

Query:
{query}

The coordinator's instruction is: {instruction if instruction else "none"}

Return JSON list:

[
{{"task_id": "1", "task": "...", "source": ["serper_search"]}},
{{"task_id": "2", "task": "...", "source": ["arxiv_search"]}},

]
"""
    
    ### add this line it you have aceess to tavily search, otherwise remove "tavily_search" from the prompt
    ### {{"task_id": "3", "task": "...", "source": ["tavily_search"]}}

    print_prompt("planner", prompt)
    resp = model.generate_content(prompt)

    tasks = extract_json(resp.text)

    log(f"{len(tasks)} tasks generated")

    for t in tasks:
        log(f'Task {t["task_id"]}: {t["task"]} | sources={t["source"]}')

    # Add to history
    new_history = history.copy()
    new_history.append(add_to_history(state, "planner", f"Created {len(tasks)} tasks"))

    return {
        "tasks": tasks,
        "research_results": {},  # Clear existing research results when creating new plan
        "history": new_history
    }


# ==============================
# Researcher Agent
# ==============================

def researcher_agent(state: ResearchState):

    print_agent_header("Researcher Agent")

    tasks = state["tasks"]
    history = state.get("history", [])

    # Append to existing research results instead of overwriting
    research_results = state.get("research_results", {})

    tasks_completed = 0

    for task in tasks:

        task_id = task["task_id"]
        desc = task["task"]
        sources = task["source"]
        instruction = state.get("instruction", "")

        log(f"Executing Task {task_id}")
        log(f"Description: {desc}")
        log(f"Sources: {sources}")

        results = []

        for source in sources:

            log(f"Running tool: {source}")

            if source == "serper_search":

                r = serper_search(desc)
                results.extend(r)

            elif source == "tavily_search":

                r = tavily_search(desc)
                results.extend(r)

            elif source == "arxiv_search":

                r = arxiv_search(desc)
                results.extend(r)

        log(f"{len(results)} results collected")

        results_text = "\n".join(map(str, results))

        prompt = f"""
Summarize the following research.

Task:
{desc}

Results:
{results_text}

The coordinator's instruction is: {instruction if instruction else "none"}

Return concise markdown summary.
"""

        print_prompt("researcher", prompt)
        summary = model.generate_content(prompt).text

        log("Summary generated")

        # Check if task already exists
        if task_id in research_results:
            # Merge results instead of overwriting
            existing_result = research_results[task_id]
            research_results[task_id] = {
                "task": desc,
                "summary": existing_result["summary"] + "\n\n" + summary,  # Append new summary
                "sources": existing_result["sources"] + results[:3]  # Append new sources
            }
            log(f"Merged new research results for Task {task_id}")
        else:
            # New task, store as new
            research_results[task_id] = {
                "task": desc,
                "summary": summary,
                "sources": results[:3]
            }
        tasks_completed += 1

    # Add to history
    new_history = history.copy()
    new_history.append(add_to_history(state, "researcher", f"Completed {tasks_completed} tasks"))

    return {
        "research_results": research_results,
        "history": new_history
    }


# ==============================
# Reporter Agent
# ==============================

def reporter_agent(state: ResearchState):

    print_agent_header("Reporter Agent")

    query = state["query"]
    results = state["research_results"]
    history = state.get("history", [])
    instruction = state.get("instruction", "")

    log("Compiling summaries")

    all_text = ""

    for r in results.values():
        all_text += r["summary"] + "\n"

    log("Generating report using Gemini")

    prompt = f"""
Write a research report.

Topic:
{query}

Research summaries:
{all_text}

The coordinator's instruction is: {instruction if instruction else "none"}

Structure:

# Executive Summary
# Key Findings
# Analysis
# Future Directions
# Conclusion
"""

    print_prompt("reporter", prompt)
    report = model.generate_content(prompt).text

    log("Report generated")

    # Add to history
    new_history = history.copy()
    new_history.append(add_to_history(state, "reporter", "Generated draft report"))

    return {
        "draft_report": report,
        "history": new_history
    }


# ==============================
# Human Review
# ==============================

def human_review(state: ResearchState):

    print_agent_header("Human Review")
    history = state.get("history", [])

    print('\a')

    print("\n========== Draft Report ==========\n")

    print(state["draft_report"])

    approval = input("\nApprove report? (yes/no): ")

    if approval.lower() == "yes":

        log("Report approved")
        
        # Add to history
        new_history = history.copy()
        new_history.append(add_to_history(state, "human_review", "Report approved"))

        return {
            "is_approved": True,
            "history": new_history
        }

    feedback = input("Provide feedback: ")

    log("Feedback received")
    
    # Add to history
    new_history = history.copy()
    new_history.append(add_to_history(state, "human_review", "Feedback provided"))

    return {
        "is_approved": False,
        "human_feedback": feedback,
        "history": new_history
    }




# ==============================
# Finalize
# ==============================

def finalize(state: ResearchState):

    print_agent_header("Finalize")
    history = state.get("history", [])

    log("Final report ready")

    # Add to history
    new_history = history.copy()
    new_history.append(add_to_history(state, "finalize", "Research completed"))

    return {
        "final_report": state["draft_report"],
        "history": new_history
    }

def system_end(state: ResearchState):
    """
    If the coordinator reached the maximum call count, the system will shut down.
    Generate new report using reporter agent and finalise.
    """
    print_agent_header("System End")
    log("Maximum coordinator calls reached. Generating final report and finalizing.")
    
    history = state.get("history", [])
    query = state["query"]
    research_results = state.get("research_results", {})
    
    # If we have research results, generate a report
    if research_results:
        log("Generating final report from research results...")
        
        all_text = ""
        for r in research_results.values():
            all_text += r["summary"] + "\n"
        
        prompt = f"""
Write a research report.

Topic:
{query}

Research summaries:
{all_text}

Structure:

# Executive Summary
# Key Findings
# Analysis
# Future Directions
# Conclusion
"""
        
        print_prompt("system_end", prompt)
        report = model.generate_content(prompt).text
        
        log("Final report generated")
    else:
        # No research results, create a simple report
        report = f"# Research Report: {query}\n\nNo research results available due to reaching maximum iteration limit."
        log("No research results available. Creating simple report.")
    
    # Add to history
    new_history = history.copy()
    new_history.append(add_to_history(state, "system_end", "System ended due to maximum call count"))
    
    return {
        "draft_report": report,
        "final_report": report,
        "history": new_history,
        "is_approved": True
    }

# ==============================
# Coordinator Agent
# ==============================
def add_to_history(state: ResearchState, event_type: str, details: str) -> Dict:
    """Add an event to the history"""
    import datetime
    history_entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "type": event_type,
        "details": details
    }
    return history_entry

def coordinator_agent(state: ResearchState):

    print_agent_header("Coordinator Agent")
    log("Coordinator Agent is deciding the next step...")
    
    # Get or initialize history
    history = state.get("history", [])
    
    # Increment global counter
    global coordinator_call_counter
    coordinator_call_counter += 1
    
    # Log current state for debugging
    log(f"Current state: tasks={len(state['tasks'])}, research_results={len(state['research_results'])}, draft_report={len(state['draft_report']) > 0}, is_approved={state['is_approved']}")
    log(f"History length: {len(history)}")
    log(f"Coordinator call count: {coordinator_call_counter}")
    
    # Check for infinite loop
    global MAX_CALLS
    
    if coordinator_call_counter >= MAX_CALLS:
        log("WARNING: Maximum coordinator calls reached. Forcing system_end.")
        decision = "system_end"
        instruction = "Maximum iterations reached, system will end"
        
        # Log coordinator call
        log_coordinator_call(decision, instruction)
        
        # Add coordinator decision to history
        new_history = history.copy()
        new_history.append(add_to_history(state, "coordinator_decision", f"Called {decision}"))
        
        return {
            "coordinator_decision": decision,
            "history": new_history,
            "instruction": instruction
        }
    
    # Format history for prompt
    history_text = ""
    if history:
        history_text = "\nHistory of previous actions:\n"
        for i, entry in enumerate(history[-10:], 1):  # Show last 10 entries
            history_text += f"{i}. [{entry['timestamp']}] {entry['type']}: {entry['details']}\n"
    
    tasks_detail = ""
    if state['tasks']:
        tasks_detail = "\nTask details:\n"
        for task in state['tasks']:
            tasks_detail += f"- Task {task['task_id']}: {task['task']} (sources: {task['source']})\n"
    
    research_summary = ""
    if state['research_results']:
        research_summary = "\nResearch results summary:\n"
        for task_id, result in state['research_results'].items():
            research_summary += f"- Task {task_id}: {result['task']}\n"
            research_summary += f"  Summary: {result['summary'][:150]}...\n"
    
    draft_preview = ""
    if state['draft_report']:
        draft_preview = f"\nDraft report preview:\n{state['draft_report'][:500]}...\n"
    
    feedback_detail = ""
    if state['human_feedback']:
        feedback_detail = f"\nHuman feedback: {state['human_feedback']}\n"
    
    prompt = f"""
    You are a research coordinator, you should decide what to do next based on the current state and history.
    
    Research query: {state['query']}
    
    Current state:
    - Tasks: {len(state['tasks'])} tasks defined
    - Research results: {len(state['research_results'])} tasks completed
    - Draft report: {'Generated' if state['draft_report'] else 'Not generated'}
    - Human feedback: {'Received' if state['human_feedback'] else 'Not received'}
    - Report approved: {state['is_approved']}
    
    Research details:
    task details: {tasks_detail} \
    research results summary: {research_summary} \
    draft report preview: {draft_preview} \
    feedback: {feedback_detail} \
    history: {history_text} \

    You have already called other agents for {state['coordinator_decision']} times, maximum call count is {MAX_CALLS}.
    If you have reached the maximum call count, the system will shut down, so do your plan carefully.
    And notice that you should call human review for at least once.

    Based on this state and history, FLEXIBLY choose the next agent to call from the following options:
    1. planner - to define or redefine research tasks
    2. researcher - to gather research information
    3. reporter - to generate or regenerate a report
    4. human_review - to get human feedback on the current draft
    5. finalize - to complete the research process
    
    Use your judgment - you can:
    - Call planner multiple times if tasks need refinement
    - Call researcher multiple times if more research is needed
    - Call reporter to regenerate the report
    - Ask for human_review at any suitable time and you must call human_review once the report is generated
    - Go back to any previous step if needed
    
    IMPORTANT: When human feedback exists, CAREFULLY analyze the feedback to decide the best next step:
    - If feedback says "add more information about X" → call researcher to research X
    - If feedback says "change the research focus" → call planner to redefine tasks
    - If feedback says "rewrite the report structure" or "fix this section" → call reporter to regenerate
    - If feedback says "looks good, approve it" → call finalize
    
    Also, provide a detailed instruction/prompt for the agent about what to do.
    
    Return JSON in the following format:
    {{
        "next_agent": "agent_name",
        "instruction": "detailed instruction for the agent"
    }}
    """

    print_prompt("coordinator", prompt)
    response = model.generate_content(prompt).text
    
    # Parse the response
    try:
        decision_data = extract_json(response)
        decision = decision_data.get("next_agent", "planner").strip().lower()
        instruction = decision_data.get("instruction", "")
    except:
        # Fallback to simple decision
        decision = "planner"
        instruction = ""
    
    log(f"Coordinator decided to call: {decision}")
    if instruction:
        log(f"Instruction: {instruction}")
    
    # Log coordinator call
    log_coordinator_call(decision, instruction)
    
    # Add coordinator decision to history
    new_history = history.copy()
    new_history.append(add_to_history(state, "coordinator_decision", f"Called {decision}"))
    
    return {
        "coordinator_decision": decision,
        "history": new_history,
        "instruction": instruction
    }