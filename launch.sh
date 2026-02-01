#!/bin/bash
# Simple launcher script for the Pokedex application

# Activate the virtual environment
source pokedex-aarch64/.venv/bin/activate

# Run the application as a Python module from the project root
python3 -m pokedex-aarch64.src.main
