"""
Vercel serverless function entry point
"""

import sys
import os

# Add the src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from hwpx_converter.web_app import app

# Vercel expects the app to be named 'app'
app = app
