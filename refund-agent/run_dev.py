import subprocess
import sys
import os

def run_dev():
    # Find relative paths
    root_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(root_dir, "backend")
    frontend_dir = os.path.join(root_dir, "frontend")
    
    print("=" * 80)
    print("STARTING AI REFUND AGENT DEVELOPMENT SERVERS")
    print("=" * 80)
    
    # Start backend server
    print("[BACKEND] Launching FastAPI server on http://localhost:8080...")
    backend_process = subprocess.Popen(
        [sys.executable, "main.py"],
        cwd=backend_dir
    )
    
    # Start frontend server
    print("[FRONTEND] Launching Vite React dev server on http://localhost:5173...")
    is_windows = os.name == 'nt'
    frontend_process = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=frontend_dir,
        shell=is_windows
    )
    
    try:
        # Wait for both processes
        backend_process.wait()
        frontend_process.wait()
    except KeyboardInterrupt:
        print("\n" + "=" * 80)
        print("SHUTTING DOWN SERVERS...")
        print("=" * 80)
        
        # Graceful termination
        backend_process.terminate()
        frontend_process.terminate()
        
        backend_process.wait()
        frontend_process.wait()
        print("All servers stopped successfully.")

if __name__ == "__main__":
    run_dev()
