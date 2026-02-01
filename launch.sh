#!/bin/bash
# Simple launcher script for the Pokedex application

# Activate the virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Run the application as a Python module from the project root
python3 -m src.main
