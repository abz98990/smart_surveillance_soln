"""python -m unittest discover -s tests -t .

Runs without OpenCV or PyTorch; everything but model inference is covered.
"""

import logging

# Some tests exercise failure paths that log tracebacks on purpose.
logging.disable(logging.ERROR)
