import psutil
import time
from datetime import datetime

def get_running_processes():
    """Get a set of (name, exe_path) for all currently running processes"""
    processes = set()
    for proc in psutil.process_iter(['name', 'exe']):
        try:
            if proc.info['exe']:  # Only record processes with exe paths
                processes.add((proc.info['name'], proc.info['exe']))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return processes

def get_process_details(proc_name, proc_path):
    """Get detailed information about a process"""
    for proc in psutil.process_iter(['name', 'exe', 'memory_info', 'cpu_percent', 'create_time', 'num_threads', 'ppid']):
        try:
            if proc.info['exe'] == proc_path:
                memory_mb = proc.info['memory_info'].rss / (1024 * 1024)  # Convert to MB
                create_time = datetime.fromtimestamp(proc.info['create_time']).strftime('%H:%M:%S')
                parent = psutil.Process(proc.info['ppid']).name() if proc.info['ppid'] else "No parent"
                return {
                    'memory_mb': round(memory_mb, 2),
                    'cpu_percent': proc.info['cpu_percent'],
                    'create_time': create_time,
                    'num_threads': proc.info['num_threads'],
                    'parent_process': parent
                }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return None

def find_new_game_process(before, after):
    """Compare before and after process sets, return new processes (excluding common system processes)"""
    new_processes = after - before
    # Filter common system processes (adjust as needed)
    system_keywords = [
        'svchost', 'explorer', 'dllhost', 'runtimebroker',
        'taskmgr', 'python', 'cmd', 'conhost', 'searchapp'
    ]
    return [
        (name, exe) for name, exe in new_processes
        if not any(keyword in name.lower() for keyword in system_keywords)
    ]

def main():
    print("=== Enhanced Game Process Detection Tool ===")
    print("This tool will help identify the main game executable by showing detailed process information.")
    input("1. Make sure the game is not running, press Enter to record state A (before game launch)...")
    state_a = get_running_processes()

    input("2. After launching the game, press Enter to record state B (after game launch)...")
    time.sleep(2)  # Give processes time to initialize
    state_b = get_running_processes()

    new_processes = find_new_game_process(state_a, state_b)
    
    if not new_processes:
        print("No new game processes detected!")
    else:
        print("\nDetected new game processes (sorted by memory usage):")
        process_details = []
        
        # Gather details for all processes
        for name, exe in new_processes:
            details = get_process_details(name, exe)
            if details:
                process_details.append((name, exe, details))
        
        # Sort processes by memory usage (usually the main game uses the most memory)
        process_details.sort(key=lambda x: x[2]['memory_mb'], reverse=True)
        
        for i, (name, exe, details) in enumerate(process_details, 1):
            print(f"\n{i}. Process name: {name}")
            print(f"   Path: {exe}")
            print(f"   Memory Usage: {details['memory_mb']} MB")
            print(f"   CPU Usage: {details['cpu_percent']}%")
            print(f"   Created at: {details['create_time']}")
            print(f"   Thread Count: {details['num_threads']}")
            print(f"   Parent Process: {details['parent_process']}")

if __name__ == "__main__":
    main()