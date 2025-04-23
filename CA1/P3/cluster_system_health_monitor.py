#!/usr/bin/env python3
import paramiko
import getpass
import sys
import socket
import tty
import termios
import select
import time
import logging
from pathlib import Path
import matplotlib.pyplot as plt
from datetime import datetime
import matplotlib
import threading
import argparse
import io

matplotlib.use('Agg')
history_length = 60
cpu_history = []
mem_history = []
disk_history = []
timestamps = []
monitoring_active = False
ssh_client = None
last_metrics = None
last_warnings = []

def setup_logging(log_file='/var/log/remote_system_monitor.log'):
    """Configure logging to only write to file"""
    logger = logging.getLogger()
    logger.setLevel(logging.WARNING)
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    try:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        ))
        logger.addHandler(file_handler)
    except PermissionError:
        logger.addHandler(logging.NullHandler())

def execute_remote_command(command):
    """Execute command on remote server and return output"""
    global ssh_client
    stdin, stdout, stderr = ssh_client.exec_command(command)
    return stdout.read().decode().strip()

def get_server_metrics():
    """Get server metrics via SSH"""
    try:
        cpu_percent = float(execute_remote_command(
            "top -bn1 | grep 'Cpu(s)' | awk '{print $2 + $4}'"
        ))
        mem_info = execute_remote_command(
            "free | grep Mem | awk '{print $3/$2 * 100.0}'"
        )
        mem_percent = float(mem_info)
        disk_percent = float(execute_remote_command(
            "df / | tail -1 | awk '{print $5}' | sed 's/%//'"
        ))
        top_cpu = execute_remote_command(
            "ps -eo pid,user,%cpu,%mem,comm --sort=-%cpu | head -n 4 | tail -n 3"
        )
        top_mem = execute_remote_command(
            "ps -eo pid,user,%cpu,%mem,comm --sort=-%mem | head -n 4 | tail -n 3"
        )
        return {
            'cpu': cpu_percent,
            'memory': mem_percent,
            'disk': disk_percent,
            'top_cpu': top_cpu,
            'top_mem': top_mem,
            'timestamp': datetime.now().strftime('%H:%M:%S')
        }
    except Exception as e:
        return None

def update_history(metrics):
    """Update historical data"""
    global cpu_history, mem_history, disk_history, timestamps, last_metrics, last_warnings
    if metrics:
        last_metrics = metrics
        timestamps.append(metrics['timestamp'])
        cpu_history.append(metrics['cpu'])
        mem_history.append(metrics['memory'])
        disk_history.append(metrics['disk'])
        if len(timestamps) > history_length:
            timestamps = timestamps[-history_length:]
            cpu_history = cpu_history[-history_length:]
            mem_history = mem_history[-history_length:]
            disk_history = disk_history[-history_length:]

def generate_plot(output_file='/var/lib/server_monitor/remote_system_health.png', 
                 cpu_thresh=80, mem_thresh=85, disk_thresh=80):
    """Generate plot of server metrics"""
    plt.figure(figsize=(12, 8))
    plt.subplot(2, 1, 1)
    plt.plot(timestamps, cpu_history, label='CPU %', marker='o')
    plt.plot(timestamps, mem_history, label='Memory %', marker='s')
    plt.plot(timestamps, disk_history, label='Disk %', marker='^')
    
    plt.title('Server Resource Usage Over Time')
    plt.ylabel('Usage (%)')
    plt.xticks(rotation=45)
    plt.legend()
    plt.grid(True)
    
    plt.axhline(y=cpu_thresh, color='r', linestyle='--', alpha=0.3)
    plt.axhline(y=mem_thresh, color='g', linestyle='--', alpha=0.3)
    plt.axhline(y=disk_thresh, color='b', linestyle='--', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=100, bbox_inches='tight')
    plt.close()
    return output_file

def monitor_server(cpu_thresh=80, mem_thresh=85, disk_thresh=80, interval=60):
    """Monitor server health with thresholds"""
    global monitoring_active, last_warnings
    logger = logging.getLogger()
    while monitoring_active:
        try:
            metrics = get_server_metrics()
            if metrics:
                update_history(metrics)
                generate_plot(cpu_thresh=cpu_thresh, mem_thresh=mem_thresh, disk_thresh=disk_thresh)
                last_warnings.clear()
                if metrics['cpu'] > cpu_thresh:
                    warning = f"CPU usage exceeded: {metrics['cpu']}% > {cpu_thresh}%"
                    last_warnings.append(warning)
                    logger.warning(warning)
                if metrics['memory'] > mem_thresh:
                    warning = f"Memory usage exceeded: {metrics['memory']}% > {mem_thresh}%"
                    last_warnings.append(warning)
                    logger.warning(warning)
                if metrics['disk'] > disk_thresh:
                    warning = f"Disk usage exceeded: {metrics['disk']}% > {disk_thresh}%"
                    last_warnings.append(warning)
                    logger.warning(warning)
            time.sleep(interval)
        except Exception as e:
            logger.error(f"Monitoring error: {str(e)}")
            time.sleep(5)

def print_status(args):
    """Print current server status and show any warnings"""
    global last_metrics, last_warnings
    if not last_metrics:
        print("No metrics available yet")
        return
    print("\n=== Server Status ===")
    if last_warnings:
        print("\n=== WARNINGS ===")
        for warning in last_warnings:
            print(f"! {warning}")
    print(f"\nCPU Usage: {last_metrics['cpu']:.1f}% (Threshold: {args.cpu}%)")
    print(f"Memory Usage: {last_metrics['memory']:.1f}% (Threshold: {args.mem}%)")
    print(f"Disk Usage: {last_metrics['disk']:.1f}% (Threshold: {args.disk}%)")
    print("\nTop CPU Processes:")
    print(last_metrics['top_cpu'])
    print("\nTop Memory Processes:")
    print(last_metrics['top_mem'])
    print(f"\nLast Check: {last_metrics['timestamp']}")
    print(f"Monitoring Interval: {args.interval} sec")
    print(f"Log file: {args.log}")
    print(f"Plot file: {args.plot}")

def interactive_shell(channel):
    """Handle interactive shell session"""
    old_attrs = termios.tcgetattr(sys.stdin)
    tty.setraw(sys.stdin.fileno())
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
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_attrs)
        print("\nShell session ended.")

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Server Health Monitor via SSH')
    parser.add_argument('--host', required=True, help='Server IP/Hostname')
    parser.add_argument('--user', required=True, help='SSH username')
    parser.add_argument('--password', help='SSH password (optional if using keys)')
    parser.add_argument('--cpu', type=float, default=80.0, help='CPU threshold %')
    parser.add_argument('--mem', type=float, default=85.0, help='Memory threshold %')
    parser.add_argument('--disk', type=float, default=80.0, help='Disk threshold %')
    parser.add_argument('--interval', type=int, default=60, help='Check interval in seconds')
    parser.add_argument('--log', default='/var/log/remote_system_monitor.log', help='Log file path')
    parser.add_argument('--plot', default='/var/lib/server_monitor/remote_system_health.png', help='Plot file path')
    return parser.parse_args()

def main():
    global monitoring_active, ssh_client
    args = parse_arguments()
    setup_logging(args.log)
    Path(args.plot).parent.mkdir(parents=True, exist_ok=True)
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        print(f"Connecting to {args.host} as {args.user}...")
        ssh_client.connect(
            hostname=args.host,
            username=args.user,
            password=args.password,
            look_for_keys=True if not args.password else False,
            timeout=10
        )
        print(f"\nConnected to {args.host}. Starting server monitoring...")
        print(f"Thresholds - CPU: {args.cpu}%, Memory: {args.mem}%, Disk: {args.disk}%")
        print(f"Interval: {args.interval} seconds")
        print("Enter 'shell' for interactive session, 'status' for metrics, or 'exit' to quit\n")
        monitoring_active = True
        monitor_thread = threading.Thread(
            target=monitor_server,
            kwargs={
                'cpu_thresh': args.cpu,
                'mem_thresh': args.mem,
                'disk_thresh': args.disk,
                'interval': args.interval
            },
            daemon=True
        )
        monitor_thread.start()
        while True:
            cmd = input("\nCommand [shell/status/exit]: ").strip().lower()
            if cmd == "shell":
                channel = ssh_client.invoke_shell(term='xterm-256color')
                channel.settimeout(1)
                print("Entering shell (Ctrl+] to exit)...")
                interactive_shell(channel)
            elif cmd == "status":
                print_status(args)
            elif cmd == "exit":
                break
            else:
                print("Invalid command. Please enter 'shell', 'status', or 'exit'")
    except Exception as e:
        print(f"\nError: {str(e)}")
    finally:
        monitoring_active = False
        if 'monitor_thread' in locals():
            monitor_thread.join(timeout=1)
        ssh_client.close()
        print("\nDisconnected from server.")

if __name__ == "__main__":
    main()