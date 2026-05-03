import re
import unicodedata


def display_width(s: str) -> int:
    """Calculate the display width of a string

    unicodedata.east_asian_width() The width is 2 for F/W, and the other width is 1.

    Args:
        s: Target string
    Returns:
        Expression range（int）
    """
    width = 0
    for ch in s:
        eaw = unicodedata.east_asian_width(ch)
        width += 2 if eaw in ("F", "W") else 1
    return width


def pad(s: str, width: int) -> str:
    """Right space padding based on display width

    Args:
        s: Target string
        width: target display width
    Returns:
        String with spaces added on the right side
    """
    return s + " " * (width - display_width(s))


def format_md_table(text: str) -> str:
    """Align column widths in a single Markdown table

    Parse a pipe-delimited table string and fit it to the maximum display width of each column.
    Pad cells. If there is no separator line, return the input as is.

    Args:
        text: Markdown table string
    Returns:
        formatted table string
    """
    lines = text.strip().splitlines()
    if len(lines) < 2:
        return text

    # Detect separator line
    separator_idx = None
    for i, line in enumerate(lines):
        if re.match(r"^\|[\s\-:|]+(\|[\s\-:|]+)+\|?$", line.strip()):
            separator_idx = i
            break

    if separator_idx is None:
        return text

    # Split each row into cells (separator row is an empty list)
    parsed_rows: list[list[str]] = []
    for i, line in enumerate(lines):
        if i == separator_idx:
            parsed_rows.append([])
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        parsed_rows.append(cells)

    # Calculate the maximum display width of each column
    num_cols = max(len(row) for row in parsed_rows if row)
    col_widths = [0] * num_cols
    for row in parsed_rows:
        for j, cell in enumerate(row):
            col_widths[j] = max(col_widths[j], display_width(cell))

    # padding and rebuilding cells
    result_lines: list[str] = []
    for i, row in enumerate(parsed_rows):
        if i == separator_idx:
            parts = ["-" * w for w in col_widths]
            result_lines.append("| " + " | ".join(parts) + " |")
        else:
            padded = []
            for j in range(num_cols):
                cell = row[j] if j < len(row) else ""
                padded.append(pad(cell, col_widths[j]))
            result_lines.append("| " + " | ".join(padded) + " |")

    return "\n".join(result_lines)


def format_md_tables_in_text(text: str) -> str:
    """Detect and format all Markdown tables in text

    Skip tables within code blocks.

    Args:
        text: string for the entire Markdown document
    Returns:
        String formatted only for table part
    """
    lines = text.splitlines(keepends=True)
    result: list[str] = []
    i = 0
    in_code_block = False
    separator_re = re.compile(r"^\|[\s\-:|]+(\|[\s\-:|]+)+\|?\s*$")
    pipe_re = re.compile(r"^\|.+\|")

    while i < len(lines):
        stripped = lines[i].rstrip("\n")

        # Track start/end of code block
        if stripped.lstrip().startswith("```"):
            in_code_block = not in_code_block
            result.append(lines[i])
            i += 1
            continue

        if in_code_block or not pipe_re.match(stripped.strip()):
            result.append(lines[i])
            i += 1
            continue

        # Collect consecutive pipe rows as table candidates
        table_lines: list[str] = []
        j = i
        while j < len(lines):
            s = lines[j].rstrip("\n").strip()
            if pipe_re.match(s) or separator_re.match(s):
                table_lines.append(s)
                j += 1
            else:
                break

        # Determine whether it is an actual table based on the presence or absence of a separator
        has_separator = any(separator_re.match(line) for line in table_lines)
        if has_separator and len(table_lines) >= 2:
            formatted = format_md_table("\n".join(table_lines))
            result.append(formatted + "\n" if lines[j - 1].endswith("\n") else formatted)
            i = j
        else:
            result.append(lines[i])
            i += 1

    return "".join(result)
