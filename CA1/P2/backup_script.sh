#!/bin/bash

if [ "$#" -ne 3 ]; then
    echo "Usage: $0 input_directory output_directory time_interval_minutes"
    echo "Example: $0 /home/user/documents /backups 60"
    exit 1
fi

input_dir="$1"
output_dir="$2"
interval_minutes="$3"

interval_seconds=$((interval_minutes * 60))

if [ ! -d "$input_dir" ]; then
    echo "Error: Input directory $input_dir does not exist"
    exit 1
fi

mkdir -p "$output_dir"

echo "Starting backup process:"
echo "  Source:      $input_dir"
echo "  Destination: $output_dir"
echo "  Interval:    every $interval_minutes minutes"
echo "Press Ctrl+C to stop"

while true; do
    timestamp=$(date +"%Y%m%d_%H%M%S")
    backup_name="backup_${timestamp}.tar.gz"
    backup_path="${output_dir}/${backup_name}"
    
    echo -n "$(date '+%Y-%m-%d %H:%M:%S') - Creating backup..."
    tar -czf "$backup_path" -C "$(dirname "$input_dir")" "$(basename "$input_dir")"
    
    if [ $? -eq 0 ] && [ -f "$backup_path" ]; then
        backup_size=$(du -h "$backup_path" | cut -f1)
        echo " done! (size: $backup_size)"
    else
        echo " failed!"
        exit 1
    fi
    
    sleep "$interval_seconds"
done
