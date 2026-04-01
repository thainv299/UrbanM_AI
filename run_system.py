import threading
import uvicorn
import tkinter as tk
from main import App

def run_cv_engine():
    """
    Initialize and starts the OpenCV detection loop and Tkinter GUI.
    This runs completely inside a background daemon thread.
    """
    try:
        root = tk.Tk()
        app = App(root)
        root.mainloop()
    except Exception as e:
        print(f"Error running CV engine: {e}")

if __name__ == "__main__":
    # Start the CV engine in a separate daemon thread
    # This maintains the OpenCV realtime visualization
    cv_thread = threading.Thread(target=run_cv_engine, daemon=True)
    cv_thread.start()

    # Start the FastAPI server on the main thread
    # Port 5000 is used to ensure the frontend cookie or existing bookmarks still work
    uvicorn.run("main_api:app", host="0.0.0.0", port=5000, reload=False)
