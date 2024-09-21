from enum import Enum


class BColor(Enum):
    HEADER = "\033[95m"
    OK_BLUE = "\033[94m"
    OK_CYAN = "\033[96m"
    OK_GREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    END = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def with_color(text: str, color: BColor) -> str:
    return f"{color.value}{text}{BColor.END.value}"
