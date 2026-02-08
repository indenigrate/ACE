import sys
import os

# Add the current directory to python path to ensure imports work correctly
sys.path.append(os.getcwd())

# --- MOCKING (Optional, helps if dependencies are missing) ---
try:
    from unittest.mock import MagicMock
    mock_playwright = MagicMock()
    sys.modules["playwright"] = mock_playwright
    sys.modules["playwright.async_api"] = mock_playwright
except ImportError:
    pass
# -------------------------------------------------------------

try:
    from src.graph import create_graph
    
    print("Initializing ACE Graph...")
    # Note: This requires GOOGLE_API_KEY to be in your .env
    app = create_graph()
    
    print("Generating graph visualization...")
    try:
        # Try to generate PNG directly (requires pygraphviz or mermaid.ink API access)
        png_bytes = app.get_graph().draw_mermaid_png()
        with open("workflow_graph.png", "wb") as f:
            f.write(png_bytes)
        print("Successfully saved visualization to 'workflow_graph.png'")
    except Exception as e:
        print(f"Could not generate PNG: {e}")
        print("Falling back to Mermaid syntax...")
        
        # Fallback to text representation
        mermaid_text = app.get_graph().draw_mermaid()
        with open("workflow_graph.mmd", "w") as f:
            f.write(mermaid_text)
        print("Saved Mermaid syntax to 'workflow_graph.mmd'.")
        print("You can copy the content of 'workflow_graph.mmd' and paste it into https://mermaid.live/ to view it.")

except ImportError as e:
    print(f"Import Error: {e}")
    print("Please ensure you are running this from the project root using 'uv run'.")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
