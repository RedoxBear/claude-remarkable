"""
claude-remarkable — SSH + cloud library for Remarkable 2.

Public surface:
    from rm_bridge import ReMarkable
    rm = ReMarkable(host="10.11.99.1")          # SSH (USB)
    rm = ReMarkable.from_connect(email, pwd)    # Remarkable Connect
"""

__version__ = "0.1.0"
