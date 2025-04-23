#!/usr/bin/env python3
import psutil

def get_health():
    cpu = f"CPU: {psutil.cpu_percent()}%"
    mem = f"RAM: {psutil.virtual_memory().percent}%"
    disk = f"Disk: {psutil.disk_usage('/').percent}%"
    return "\n".join([cpu, mem, disk])

if __name__ == "__main__":
    print("=== System Health ===")
    print(get_health())
