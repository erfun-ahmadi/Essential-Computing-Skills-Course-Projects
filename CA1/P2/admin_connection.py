#!/usr/bin/env python3
import paramiko
import getpass
import sys
import socket
import tty
import termios
import select

def setup_terminal():
    """Set up terminal for raw input"""
    old_attrs = termios.tcgetattr(sys.stdin)
    tty.setraw(sys.stdin.fileno())
    return old_attrs

def restore_terminal(old_attrs):
    """Restore terminal settings"""
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_attrs)

def interactive_shell(channel, commands_log):
    """Handle the interactive shell session"""
    old_attrs = setup_terminal()
    command_buffer = ""  
    
    try:
        while True:
            r, w, e = select.select([channel, sys.stdin], [], [])
            if channel in r:
                try:
                    data = channel.recv(1024)
                    if not data:
                        break
                    sys.stdout.write(data.decode())
                    sys.stdout.flush()
                except socket.timeout:
                    continue
            if sys.stdin in r:
                char = sys.stdin.read(1)
                if char == '\x1d':  
                    break
                channel.send(char)              
                if char == '\r': 
                    if command_buffer.strip():  
                        commands_log.append(command_buffer.strip())
                    command_buffer = ""
                elif char in ['\x7f', '\b']:  
                    command_buffer = command_buffer[:-1]
                elif char.isprintable():
                    command_buffer += char

    finally:
        if command_buffer.strip(): 
            commands_log.append(command_buffer.strip())
        restore_terminal(old_attrs)
        print("\nConnection closed.")

def download_file(ftp_client, local_path, remote_path, commands_log):
    """Download file from remote server to local machine"""
    try:
        ftp_client.get(remote_path, local_path)
        print(f"File downloaded to {local_path}.")
        commands_log.append(f"downloaded {remote_path} to {local_path}")
    except Exception as e:
        print(f"Error downloading file: {str(e)}")

def upload_file(ftp_client, local_path, remote_path, commands_log):
    """Upload file from local machine to remote server"""
    try:
        ftp_client.put(local_path, remote_path)
        print(f"File uploaded to {remote_path}.")
        commands_log.append(f"uploaded {local_path} to {remote_path}")
    except Exception as e:
        print(f"Error uploading file: {str(e)}")

def main():
    print("=== Python SSH Client ===")
    host = input("Server IP/Hostname: ").strip()
    user = input("Username: ").strip()
    pwd = getpass.getpass("Password (leave empty for SSH key auth): ") or None
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=host,
            username=user,
            password=pwd,
            look_for_keys=True,
            allow_agent=True,
            timeout=10
        )
        print(f"\nConnected to {host}.\n")
        ftp_client = client.open_sftp()
        commands_log = list()
        while True:
            command = input("\nEnter command (Download/Upload)_file local_path remote_path, or 'shell' to enter interactive shell, or 'exit' to quit: ").strip()
            if command.lower().startswith("download_file") or command.lower().startswith("upload_file"):
                parts = command.split()
                if len(parts) == 3:
                    operation, local_path, remote_path = parts
                    if operation.lower() == "download_file":
                        download_file(ftp_client, local_path, remote_path, commands_log)
                    elif operation.lower() == "upload_file":
                        upload_file(ftp_client, local_path, remote_path, commands_log)
                else:
                    print("Invalid command format. Please use: <Download/Upload>_file local_path remote_path")
            elif command.lower() == "shell":
                channel = client.invoke_shell(term='xterm-256color')
                channel.settimeout(1)
                print("Entering interactive shell. Type 'exit' to leave.")
                interactive_shell(channel, commands_log)
            elif command.lower() == "exit":
                print("commands log:\n")
                for command in commands_log:
                    print(command)
                break
            else:
                print("Invalid command. Type 'Download_file', 'Upload_file', 'shell', or 'exit'.")
        ftp_client.close()

    except Exception as e:
        print(f"\nError: {str(e)}")
    finally:
        client.close()

if __name__ == "__main__":
    main()
