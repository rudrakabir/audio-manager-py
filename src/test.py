import tkinter as tk
from tkinter import ttk
import os

class TestApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Audio Manager Test")
        
        # Create main frame
        main_frame = ttk.Frame(root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Add test label
        self.label = ttk.Label(main_frame, text="Testing Audio Manager")
        self.label.grid(row=0, column=0, pady=10)
        
        # Add test button
        self.button = ttk.Button(main_frame, text="Click Me", 
                               command=self.on_button_click)
        self.button.grid(row=1, column=0, pady=5)
        
        # Configure grid weights
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
    
    def on_button_click(self):
        self.label.config(text="Button clicked!")

def main():
    print("Starting application...")
    root = tk.Tk()
    app = TestApp(root)
    print("Application initialized, starting mainloop...")
    root.mainloop()

if __name__ == "__main__":
    main()