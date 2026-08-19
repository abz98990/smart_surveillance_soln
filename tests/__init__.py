"""Test suite for the Smart Surveillance System.

Run with:  python -m unittest discover -s tests -t .

The suite deliberately avoids OpenCV and PyTorch so it runs on any machine.
Everything except the model inference itself is covered.
"""

import logging

# Several tests exercise failure paths that log tracebacks on purpose.
logging.disable(logging.ERROR)
