import re


def matches_directive(line, directive):
    """Return True when an INI line assigns the requested directive.

    A plain substring test also matches other directives that contain the name: PHP 8.5 added max_memory_limit next to memory_limit, and a comment such
    as "; memory_limit = 128M" contains it too. Only a line that starts with the directive (after optional white space) and an equals sign is an assignment.
    """
    pattern = r'^\s*' + re.escape(directive) + r'\s*='
    return re.match(pattern, line, re.IGNORECASE) is not None
