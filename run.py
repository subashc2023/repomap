#!/usr/bin/env python3
"""
Run script for the repomap project.
Imports and executes the main function from src/hello.py
"""

import sys
import os

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from hello import main, RepomapApp

if __name__ == "__main__":
    print("Starting repomap application...")
    print("=" * 50)
    
    # Run the main function from hello.py
    main()
    
    print("\n" + "=" * 50)
    print("Application completed successfully!") 