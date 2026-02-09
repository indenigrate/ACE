import os
import sys
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt, IntPrompt

from src.graph import create_graph
from src.state import AgentState

console = Console()

def display_draft(state: AgentState):
    console.clear()
    console.print(Panel.fit(
        f"[bold blue]Recipient:[/bold blue] {state['recipient_name']} ({state['company_name']})\n"
        f"[bold blue]Position:[/bold blue] {state['position']}",
        title=f"Lead Information (Row {state.get('row_index', '?')})"
    ))
    
    console.print("\n")
    console.print(Panel(
        f"[bold]Subject:[/bold] {state.get('email_subject', 'N/A')}\n"
        "---"
        f"{state.get('email_body', 'N/A')}",
        title="Email Draft"
    ))

    # RAW DEBUG PRINT
    # raw_body = state.get('email_body', '')
    # print("\n[DEBUG] --- RAW BODY (Inspect for hidden newlines) ---")
    # print(f"[START BODY]{raw_body}[END BODY]")
    # print("[DEBUG] -----------------------------------------------\n")

def main():
    console.print(Panel("[bold green]ACE: Agentic Cold Emailer[/bold green]", expand=False))
    
    # Mode Selection
    console.print("\n[bold]Select Execution Mode:[/bold]")
    console.print("1. [bold cyan]Interactive (HITL)[/bold cyan]: Review and approve each email before sending.")
    console.print("2. [bold magenta]Automatic (Draft Mode)[/bold magenta]: Automatically create drafts for all leads to review later in Gmail.")
    
    mode_choice = Prompt.ask("Enter choice", choices=["1", "2"], default="1")
    
    is_autonomous = (mode_choice == "2")
    run_mode = "auto_draft" if is_autonomous else "interactive"
    
    if is_autonomous:
        console.print(f"\n[bold magenta]Starting in Automatic Draft Mode.[/bold magenta] All emails will be saved to 'Drafts'.")
    else:
        console.print(f"\n[bold cyan]Starting in Interactive Mode.[/bold cyan]")

    # Create Graph with conditional interrupt
    graph = create_graph(autonomous=is_autonomous)
    config = {"configurable": {"thread_id": "ace_session"}}
    
    console.print("Starting workflow...")
    
    # Initial kickoff with mode configuration
    # We pass the mode in the initial state. 
    # If the graph has memory, it might resume, so we update state first if needed or rely on invoke input.
    # Ideally, we start fresh or resume.
    
    # Run loop
    first_run = True
    
    while True:
        # If we have a state, we resume; otherwise, we start fresh
        state = graph.get_state(config)
        
        if not state.values or first_run:
            # Start fresh or restart logic, ensuring mode is set
            # We use update_state to inject the config if starting fresh
            # or pass it in the input of invoke.
            if not state.values:
                 graph.invoke({"mode": run_mode}, config)
            else:
                 # If resuming a previous session, we might want to update the mode
                 graph.update_state(config, {"mode": run_mode})
                 if first_run and not is_autonomous: 
                     # If interactive and resuming, just continue
                     pass 
                 elif first_run and is_autonomous:
                     # If auto, trigger execution if paused
                     graph.invoke(None, config)
            first_run = False
        
        # Refresh state after invoke
        state = graph.get_state(config)
        current_state = state.values
        
        if not current_state:
             # Should not happen after invoke, but safety check
             break

        if current_state.get("status") == "end":
            console.print("[bold green]All leads processed. Goodbye![/bold green]")
            break
            
        # INTERACTIVE MODE LOGIC
        if not is_autonomous:
            # Only display and ask if we are interrupted (which happens at 'review' node)
            # The graph pauses BEFORE 'review' or 'human_review_node' logic depending on implementation.
            # In our graph.py, interrupt_before=["review"].
            
            # Check if we are actually at the interrupt point
            if state.next and "review" in state.next:
                display_draft(current_state)
                
                # Handle Email Selection if needed
                candidate_emails = current_state.get('candidate_emails', [])
                selected_emails = current_state.get('selected_emails')
                
                if len(candidate_emails) > 1 and not selected_emails:
                    console.print(Panel(
                        "[bold yellow]WARNING:[/bold yellow] Multiple emails found for this lead.",
                        border_style="yellow"
                    ))
                    for i, email in enumerate(candidate_emails, 1):
                        console.print(f"  [{i}] {email}")
                    
                    choice = Prompt.ask(
                        "Target which email? (Type 'all' for all, or '1', '2'...)", 
                        default="all"
                    )
                    
                    if choice.lower() == 'all':
                        selected_emails = candidate_emails
                    else:
                        try:
                            idx = int(choice) - 1
                            if 0 <= idx < len(candidate_emails):
                                selected_emails = [candidate_emails[idx]]
                            else:
                                console.print("[red]Invalid index, defaulting to first.[/red]")
                                selected_emails = [candidate_emails[0]]
                        except ValueError:
                            console.print("[red]Invalid input, defaulting to first.[/red]")
                            selected_emails = [candidate_emails[0]]
                            
                    console.print(f"[green]Selected:[/green] {', '.join(selected_emails)}\n")
                elif len(candidate_emails) == 1:
                     selected_emails = [candidate_emails[0]]
                
                # Action Loop
                action = Prompt.ask(
                    "[y] Approve / [s] Skip / [type feedback] Refine",
                    default="y"
                )
                
                if action.lower() == 'y':
                    graph.update_state(config, {
                        "status": "approved", 
                        "selected_emails": selected_emails
                    })
                elif action.lower() in ['s', 'skip']:
                    graph.update_state(config, {
                        "status": "skipped",
                        "selected_emails": None
                    })
                else:
                    graph.update_state(config, {"user_feedback": action, "status": "refining"})
                
                # Resume execution
                print(f"[LOG] Resuming workflow...")
                graph.invoke(None, config)
            else:
                # If we are not at interrupt, maybe we just finished a cycle?
                # If the graph finishes a run without ending, it might be in a weird state.
                # Usually invoke() runs until interrupt or END.
                # If we are here, it means invoke returned.
                # If status is not end, and next is empty, we loop back?
                # Our graph has a cycle: update -> fetch. 
                # So it should keep running until 'end' or interrupt.
                # If it stopped and not 'end', we invoke again.
                graph.invoke(None, config)

        # AUTOMATIC MODE LOGIC
        else:
            # In autonomous mode, the graph runs continuously until it hits END or an error.
            # We just loop and check status.
            if current_state.get("status") != "end":
                 # If it stopped but not end, kick it again (e.g. after a draft creation cycle)
                 graph.invoke(None, config)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[bold red]Interrupted by user. Exiting...[/bold red]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)