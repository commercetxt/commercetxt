"""
Resource limits for CommerceTXT parser.
Keep it fast. Keep it safe.
"""

# Stop huge files. 10MB limit.
MAX_FILE_SIZE = 10 * 1024 * 1024

# Kill long lines. Prevent ReDoS. 100KB limit.
MAX_LINE_LENGTH = 100 * 1024

# Limit total sections. Avoid logic exhaustion.
MAX_SECTIONS = 1000

# Cap nesting depth. Guard the stack.
MAX_NESTING_DEPTH = 100
