#!/usr/bin/env python3
import psutil
import time
import argparse
import logging
import sys
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
import matplotlib
matplotlib.use('Agg')

history_length = 60
cpu_history = []
mem_history = []
disk_history = []
timestamps = []

def setup_logging():
    """Configure logging to work with systemd's journal and a log file"""
    logger = logging.getLogger()
    logger.setLevel(logging.WARNING)     
    stderr_handler = logging.StreamHandler()
    stderr_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    ))
    logger.addHandler(stderr_handler)
    log_file = '/var/log/system_monitor.log'
    try:
        Path(log_file).parent.mkdir(exist_ok=True, mode=0o755)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        ))
        logger.addHandler(file_handler)
    except PermissionError:
        logger.warning(f"Couldn't open log file {log_file}, using only journald logging")

def get_top_processes(n=3):
    """Get top n processes by CPU and memory usage"""
    procs = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            procs.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    top_cpu = sorted(procs, key=lambda p: p['cpu_percent'], reverse=True)[:n]
    top_mem = sorted(procs, key=lambda p: p['memory_percent'], reverse=True)[:n]
    return top_cpu, top_mem

def update_history(cpu, mem, disk):
    """Update historical data"""
    global cpu_history, mem_history, disk_history, timestamps
    now = datetime.now()
    timestamps.append(now.strftime('%H:%M:%S'))
    cpu_history.append(cpu)
    mem_history.append(mem)
    disk_history.append(disk)
    if len(timestamps) > history_length:
        timestamps = timestamps[-history_length:]
        cpu_history = cpu_history[-history_length:]
        mem_history = mem_history[-history_length:]
        disk_history = disk_history[-history_length:]

def generate_plot(output_file='/var/lib/system_monitor/system_health.png'):
    """Generate a plot of system metrics"""
    plt.figure(figsize=(12, 8))
    plt.subplot(2, 1, 1)
    plt.plot(timestamps, cpu_history, label='CPU %', marker='o')
    plt.plot(timestamps, mem_history, label='Memory %', marker='s')
    plt.plot(timestamps, disk_history, label='Disk %', marker='^')

    plt.title('System Resource Usage Over Time')
    plt.ylabel('Usage (%)')
    plt.xticks(rotation=45)
    plt.legend()
    plt.grid(True)
    
    args = parse_arguments()
    plt.axhline(y=args.cpu, color='r', linestyle='--', alpha=0.3)
    plt.axhline(y=args.mem, color='g', linestyle='--', alpha=0.3)
    plt.axhline(y=args.disk, color='b', linestyle='--', alpha=0.3)
    
    top_cpu, top_mem = get_top_processes(3)
    process_text = "Top CPU Processes:\n"
    for proc in top_cpu:
        process_text += f"{proc['name']}: {proc['cpu_percent']:.1f}%\n"
    process_text += "\nTop Memory Processes:\n"
    for proc in top_mem:
        process_text += f"{proc['name']}: {proc['memory_percent']:.1f}%\n"
    plt.subplot(2, 1, 2)
    plt.text(0.1, 0.1, process_text, fontfamily='monospace', fontsize=10)
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(output_file, dpi=100, bbox_inches='tight')
    plt.close()
    return output_file

def monitor_system(cpu_threshold, mem_threshold, disk_threshold, interval=5):
    """Monitor system health with thresholds"""
    logger = logging.getLogger()
    try:
        while True:
            try:
                cpu_percent = psutil.cpu_percent(interval=1)
                cpu_count = psutil.cpu_count()
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                net_io = psutil.net_io_counters()
                top_cpu, top_mem = get_top_processes()
                update_history(cpu_percent, memory.percent, disk.percent)
                plot_file = generate_plot()
                print(f"\n--- System Health at {time.strftime('%Y-%m-%d %H:%M:%S')} ---")
                print(f"CPU Usage: {cpu_percent}% ({cpu_count} cores)")
                print(f"Memory: {memory.percent}% used ({memory.used/1024/1024:.2f} MB / {memory.total/1024/1024:.2f} MB)")
                print(f"Disk: {disk.percent}% used ({disk.used/1024/1024/1024:.2f} GB / {disk.total/1024/1024/1024:.2f} GB)")
                print(f"Network: Sent {net_io.bytes_sent/1024/1024:.2f} MB | Received {net_io.bytes_recv/1024/1024:.2f} MB")
                print(f"Status plot saved to: {plot_file}")
                print("\nTop CPU processes:")
                for proc in top_cpu:
                    print(f"  {proc['name']} (PID:{proc['pid']}): {proc['cpu_percent']:.1f}% CPU")
                print("\nTop Memory processes:")
                for proc in top_mem:
                    print(f"  {proc['name']} (PID:{proc['pid']}): {proc['memory_percent']:.1f}% Memory")
                if cpu_percent > cpu_threshold:
                    msg = f"CPU usage exceeded threshold: {cpu_percent}% > {cpu_threshold}%"
                    logger.warning(msg)
                    print(f"\nWARNING: {msg}")
                if memory.percent > mem_threshold:
                    msg = f"Memory usage exceeded threshold: {memory.percent}% > {mem_threshold}%"
                    logger.warning(msg)
                    print(f"\nWARNING: {msg}")
                if disk.percent > disk_threshold:
                    msg = f"Disk usage exceeded threshold: {disk.percent}% > {disk_threshold}%"
                    logger.warning(msg)
                    print(f"\nWARNING: {msg}")
                time.sleep(interval)
            except psutil.Error as e:
                logger.error(f"Error getting system metrics: {str(e)}")
                print(f"ERROR: {str(e)}")
                time.sleep(interval)
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Unexpected error: {str(e)}")
        print(f"CRITICAL ERROR: {str(e)}")
        sys.exit(1)

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='System Health Monitor with Threshold Alerts')
    parser.add_argument('--cpu', type=float, default=80.0, 
                       help='CPU usage threshold percentage (default: 80)')
    parser.add_argument('--mem', type=float, default=80.0, 
                       help='Memory usage threshold percentage (default: 80)')
    parser.add_argument('--disk', type=float, default=80.0, 
                       help='Disk usage threshold percentage (default: 80)')
    parser.add_argument('--interval', type=int, default=5, 
                       help='Monitoring interval in seconds (default: 5)')
    parser.add_argument('--top', type=int, default=3,
                       help='Number of top processes to show (default: 3)')
    return parser.parse_args()

def main():
    args = parse_arguments()
    setup_logging()
    print(f"Starting system monitor with thresholds - CPU: {args.cpu}%, Memory: {args.mem}%, Disk: {args.disk}%")
    print(f"Monitoring interval: {args.interval} seconds")
    print(f"Showing top {args.top} processes by CPU/Memory usage")
    print("Press Ctrl+C to stop monitoring\n")
    generate_plot()
    monitor_system(args.cpu, args.mem, args.disk, args.interval)

if __name__ == "__main__":
    main()
