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
        channel = client.invoke_shell(term='xterm-256color')
        channel.settimeout(1)
        commands_log = list()
        print(f"\nConnected to {host}. Press Ctrl+] to exit.\n")
        interactive_shell(channel, commands_log)
    except Exception as e:
        print(f"\nError: {str(e)}")
    finally:
        print("commands log:\n")
        for command in commands_log:
            print(command)
        client.close()

if __name__ == "__main__":
    main()
