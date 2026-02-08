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

def main():
    graph = create_graph()
    config = {"configurable": {"thread_id": "ace_session"}}
    
    console.print(Panel("[bold green]ACE: Agentic Cold Emailer[/bold green]\nStarting workflow...", expand=False))
    
    # Run loop
    while True:
        # If we have a state, we resume; otherwise, we start fresh
        state = graph.get_state(config)
        
        if not state.values:
            # Start fresh
            graph.invoke({}, config)
        else:
            # Check why we interrupted
            current_state = state.values
            
            if current_state.get("status") == "end":
                console.print("[bold green]All leads processed. Goodbye![/bold green]")
                break
                
            display_draft(current_state)
            
            # Handle Email Selection if needed
            candidate_emails = current_state.get('candidate_emails', [])
            selected_email = current_state.get('selected_email')
            
            if len(candidate_emails) > 1 and not selected_email:
                console.print(Panel(
                    "[bold yellow]WARNING:[/bold yellow] Multiple emails found for this lead.",
                    border_style="yellow"
                ))
                for i, email in enumerate(candidate_emails, 1):
                    console.print(f"  [{i}] {email}")
                
                choice = IntPrompt.ask(
                    "Which email to target?", 
                    choices=[str(i) for i in range(1, len(candidate_emails) + 1)],
                    default=1
                )
                selected_email = candidate_emails[choice - 1]
                console.print(f"[green]Selected:[/green] {selected_email}\n")
            elif len(candidate_emails) == 1:
                 selected_email = candidate_emails[0]
            
            # Action Loop
            action = Prompt.ask(
                "[y] Approve / [s] Skip / [type feedback] Refine",
                default="y"
            )
            
            if action.lower() == 'y':
                graph.update_state(config, {
                    "status": "approved", 
                    "selected_email": selected_email
                })
            elif action.lower() == 's':
                graph.update_state(config, {"status": "skipped"})
            else:
                graph.update_state(config, {"user_feedback": action, "status": "refining"})
            
            # Resume execution
            print(f"[DEBUG] Resuming graph execution from: {state.next}")
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
