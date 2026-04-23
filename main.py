import sys
import argparse
import logging
import time
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.live import Live

from src.graph import create_graph
from src.state import AgentState
from src.analytics import log_event, format_summary
from src.tools_gmail import list_drafts, get_draft_details, send_draft, list_starred_threads, get_thread_history, get_thread_metadata, create_draft_reply
from src.nodes import evaluate_starred_thread
from config.settings import MAX_REFINEMENT_ITERATIONS, RESUME_PDF_PATH

logger = logging.getLogger(__name__)
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


def display_variants(state: AgentState) -> None:
    """Display A/B subject line variants and let user select one."""
    variants = state.get('subject_variants', [])
    if not variants or len(variants) <= 1:
        return

    console.print(Panel(
        "\n".join(f"  [bold cyan][{i}][/bold cyan] {v}" for i, v in enumerate(variants, 1)),
        title="[bold]A/B Subject Line Variants[/bold]",
        border_style="cyan",
    ))

    choice = Prompt.ask(
        "Select a subject variant",
        choices=[str(i) for i in range(1, len(variants) + 1)],
        default="1",
    )
    selected_idx = int(choice) - 1
    selected_subject = variants[selected_idx]

    console.print(f"[green]Selected variant {selected_idx + 1}:[/green] {selected_subject}\n")

    # Log the A/B choice for analytics
    log_event(
        "variant_selected",
        recipient=state.get('recipient_name', ''),
        company=state.get('company_name', ''),
        data={"variant_index": selected_idx, "selected_subject": selected_subject},
    )

    return selected_subject


# ---------------------------------------------------------------------------
# Send Drafts Mode
# ---------------------------------------------------------------------------
SEND_INTERVAL = 20  # seconds between sends


def send_drafts_loop(limit: int) -> None:
    """Fetch recent Gmail drafts and send them at 20-second intervals.

    Args:
        limit: Max number of drafts to send. 0 means unlimited (until exhausted).
    """
    mode_label = f"up to {limit}" if limit > 0 else "all available"
    console.print(Panel(
        f"[bold magenta]Send Drafts Mode[/bold magenta]\n"
        f"Sending [bold]{mode_label}[/bold] recent drafts at {SEND_INTERVAL}s intervals.\n"
        f"Press [bold red]Ctrl+C[/bold red] to stop.",
        expand=False,
    ))

    # Fetch drafts
    fetch_count = limit if limit > 0 else 500  # reasonable upper bound
    console.print(f"\n[dim]Fetching drafts...[/dim]")
    drafts = list_drafts(max_results=fetch_count)

    if not drafts:
        console.print("[yellow]No drafts found. Nothing to send.[/yellow]")
        return

    total = len(drafts)
    if limit > 0:
        total = min(total, limit)
        drafts = drafts[:total]

    console.print(f"[green]Found {len(drafts)} draft(s) to send.[/green]\n")

    sent_count = 0
    try:
        for i, draft_meta in enumerate(drafts, 1):
            draft_id = draft_meta["id"]

            # Fetch header details for display
            try:
                details = get_draft_details(draft_id)
                headers = {
                    h["name"]: h["value"]
                    for h in details.get("message", {}).get("payload", {}).get("headers", [])
                }
                to_field = headers.get("To", "[unknown]")
                subject = headers.get("Subject", "[no subject]")
            except Exception:
                to_field = "[unknown]"
                subject = "[could not fetch details]"

            console.print(
                f"[bold cyan][{i}/{total}][/bold cyan] "
                f"Sending → [bold]{to_field}[/bold]  ·  {subject}"
            )

            # Send
            try:
                send_draft(draft_id)
                sent_count += 1
                console.print(f"  [green]✓ Sent successfully[/green]")
            except Exception as e:
                console.print(f"  [red]✗ Failed: {e}[/red]")

            # Sleep between sends (skip after the last one)
            if i < total:
                console.print(f"  [dim]Waiting {SEND_INTERVAL}s...[/dim]")
                time.sleep(SEND_INTERVAL)

    except KeyboardInterrupt:
        console.print(f"\n[bold red]Interrupted![/bold red]")

    console.print(f"\n[bold green]Done. Sent {sent_count}/{total} draft(s).[/bold green]")


# ---------------------------------------------------------------------------
# Starred Emails Mode
# ---------------------------------------------------------------------------

def starred_emails_loop(limit: int) -> None:
    """Iterate over starred emails, evaluate them natively, and suggest follow-up drafts."""
    mode_label = f"up to {limit}" if limit > 0 else "all available"
    console.print(Panel(
        f"[bold yellow]Starred Emails Mode[/bold yellow]\n"
        f"Processing [bold]{mode_label}[/bold] starred emails.\n"
        f"Press [bold red]Ctrl+C[/bold red] to stop.",
        expand=False,
    ))

    # Fetch starred threads
    fetch_count = limit if limit > 0 else 50
    console.print(f"\n[dim]Fetching starred threads...[/dim]")
    threads = list_starred_threads(max_results=fetch_count)

    if not threads:
        console.print("[yellow]No starred threads found.[/yellow]")
        return

    total = len(threads)
    if limit > 0:
        total = min(total, limit)
        threads = threads[:total]

    console.print(f"[green]Found {len(threads)} starred thread(s) to process.[/green]\n")

    try:
        for i, thread_meta in enumerate(threads, 1):
            thread_id = thread_meta["id"]
            
            console.print(f"[bold cyan]--- [{i}/{total}] Processing Thread {thread_id} ---[/bold cyan]")
            
            # Get metadata & history
            meta = get_thread_metadata(thread_id)
            chat_history = get_thread_history(thread_id)
            
            # Evaluate
            console.print("[dim]Evaluating thread with LLM...[/dim]")
            evaluation = evaluate_starred_thread(chat_history)
            
            # Display
            console.print(Panel.fit(
                f"[bold blue]Subject:[/bold blue] {meta['subject']}\n"
                f"[bold blue]Last Date:[/bold blue] {meta['last_date']}\n"
                f"[bold blue]Messages:[/bold blue] {meta['msg_count']}\n"
                f"---\n"
                f"[bold]Follow up needed?[/bold] [{'green' if evaluation.follow_up else 'red'}]{evaluation.follow_up}[/]\n"
                f"[bold]Confidence:[/bold] {evaluation.confidence_score}%\n"
                f"[bold]Reason:[/bold] {evaluation.reason}",
                title="Thread Evaluation"
            ))
            
            if evaluation.follow_up and evaluation.suggested_draft:
                console.print(Panel(
                    evaluation.suggested_draft,
                    title="Suggested Draft"
                ))
                
                action = Prompt.ask(
                    "[a] Approve & Draft / [s] Skip",
                    choices=["a", "s"],
                    default="a"
                )
                
                if action.lower() == 'a':
                    console.print("[dim]Creating draft...[/dim]")
                    try:
                        # Only attach resume safely if it exists
                        resume_pdf_path = str(RESUME_PDF_PATH) if RESUME_PDF_PATH and hasattr(RESUME_PDF_PATH, 'is_file') and RESUME_PDF_PATH.is_file() else None
                        create_draft_reply(
                            thread_id=thread_id,
                            body=evaluation.suggested_draft,
                            attachment_path=resume_pdf_path
                        )
                        console.print("[green]✓ Draft created successfully.[/green]\n")
                    except Exception as e:
                        console.print(f"[red]✗ Failed to create draft: {e}[/red]\n")
                else:
                    console.print("[yellow]Skipping thread.[/yellow]\n")
            else:
                console.print("[dim]No follow-up suggested by LLM.[/dim]")
                if i < total:
                    Prompt.ask("Press Enter to continue to next thread...", default="")
                console.print("")

    except KeyboardInterrupt:
        console.print(f"\n[bold red]Interrupted![/bold red]")

    console.print(f"\n[bold green]Done processing starred threads.[/bold green]")


def main():
    parser = argparse.ArgumentParser(description="ACE: Agentic Cold Emailer")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--follow-ups", type=int, choices=[1, 2], help="Run follow-up sequence (1 or 2)")
    group.add_argument(
        "--send-drafts", type=int, nargs="?", const=0, default=None, metavar="N",
        help="Send recent Gmail drafts at 20s intervals. Optionally specify N to limit count."
    )
    group.add_argument(
        "--starred", type=int, nargs="?", const=0, default=None, metavar="N",
        help="Process starred emails and draft AI-suggested follow-ups. Optionally specify N to limit count."
    )
    args = parser.parse_args()

    console.print(Panel("[bold green]ACE: Agentic Cold Emailer[/bold green]", expand=False))

    if args.starred is not None:
        starred_emails_loop(args.starred)
        return

    # Dispatch to send-drafts mode if requested
    if args.send_drafts is not None:
        send_drafts_loop(args.send_drafts)
        return

    is_followup = args.follow_ups is not None
    followup_num = args.follow_ups if is_followup else 0

    if is_followup:
        console.print(f"\n[bold yellow]FOLLOW-UP MODE: Stage {followup_num}[/bold yellow]")
        run_mode = "auto_draft" # Follow-ups are usually bulk drafted
    else:
        # Mode Selection
        console.print("\n[bold]Select Execution Mode:[/bold]")
        console.print("1. [bold cyan]Interactive (HITL)[/bold cyan]: Review and approve each email before sending.")
        console.print("2. [bold magenta]Automatic (Draft Mode)[/bold magenta]: Automatically create drafts for all leads to review later in Gmail.")

        mode_choice = Prompt.ask("Enter choice", choices=["1", "2"], default="1")

        is_autonomous = (mode_choice == "2")
        run_mode = "auto_draft" if is_autonomous else "interactive"

    is_autonomous = (run_mode == "auto_draft")

    if is_autonomous and not is_followup:
        console.print(f"\n[bold magenta]Starting in Automatic Draft Mode.[/bold magenta] All emails will be saved to 'Drafts'.")
    elif not is_followup:
        console.print(f"\n[bold cyan]Starting in Interactive Mode.[/bold cyan]")

    # Create Graph with conditional interrupt
    graph = create_graph(autonomous=is_autonomous)
    config = {"configurable": {"thread_id": "ace_session"}}

    console.print("Starting workflow...")

    # Run loop
    first_run = True

    while True:
        state = graph.get_state(config)

        if not state.values or first_run:
            if not state.values:
                initial_input = {
                    "mode": run_mode,
                    "is_followup_mode": is_followup,
                    "followup_number": followup_num
                }
                graph.invoke(initial_input, config)
            else:
                graph.update_state(config, {
                    "mode": run_mode,
                    "is_followup_mode": is_followup,
                    "followup_number": followup_num
                })
                if first_run and is_autonomous:
                    graph.invoke(None, config)
            first_run = False

        # Refresh state after invoke
        state = graph.get_state(config)
        current_state = state.values

        if not current_state:
            break

        if current_state.get("status") == "end":
            console.print("\n[bold green]All leads processed. Goodbye![/bold green]")
            # Print analytics summary
            console.print(f"\n{format_summary()}")
            break

        # INTERACTIVE MODE LOGIC
        if not is_autonomous:
            if state.next and "review" in state.next:
                display_draft(current_state)

                # A/B Variant Selection
                selected_subject = display_variants(current_state)
                if selected_subject:
                    graph.update_state(config, {"email_subject": selected_subject})
                    # Refresh state
                    state = graph.get_state(config)
                    current_state = state.values

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

                # Iteration guard — restrict options if max reached
                iteration_count = current_state.get('iteration_count', 0)
                if iteration_count >= MAX_REFINEMENT_ITERATIONS:
                    console.print(
                        f"[bold yellow]Max refinements ({MAX_REFINEMENT_ITERATIONS}) reached. "
                        f"You can only approve or skip.[/bold yellow]"
                    )
                    action = Prompt.ask(
                        "[y] Approve / [s] Skip",
                        default="y"
                    )
                else:
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
                logger.info("Resuming workflow...")
                graph.invoke(None, config)
            else:
                graph.invoke(None, config)

        # AUTOMATIC MODE LOGIC
        else:
            if current_state.get("status") != "end":
                graph.invoke(None, config)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[bold red]Interrupted by user. Exiting...[/bold red]")
        console.print(f"\n{format_summary()}")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)