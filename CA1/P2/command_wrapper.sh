#!/bin/bash

ALLOWED_COMMAND="health"
PS1="> "

while true; do
    read -p "$PS1" CMD

    if [[ "$CMD" == "exit" ]]; then
        echo "Exiting..."
        break
    elif [[ "$CMD" == "$ALLOWED_COMMAND" ]]; then
        $CMD
    else
        echo "Error: Command not allowed."
    fi
done
