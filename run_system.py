import threading
import uvicorn
import tkinter as tk
from main import App

def run_cv_engine():
    try:
        root = tk.Tk()
        app = App(root)
        root.mainloop()
    except Exception as e:
        print(f"Error running CV engine: {e}")

if __name__ == "__main__":
    cv_thread = threading.Thread(target=run_cv_engine, daemon=True)
    cv_thread.start()

    uvicorn.run("main_api:app", host="0.0.0.0", port=5000, reload=False)
