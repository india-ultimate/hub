import re
import shutil
from pathlib import Path


def create_empty_directory(directory_path: Path) -> None:
    shutil.rmtree(directory_path, ignore_errors=True)
    directory_path.mkdir(exist_ok=True)


def get_otp_from_email_logs(directory_path: Path) -> str:
    files = list(directory_path.glob("*"))

    if not files:
        raise ValueError("File not found")

    html_content = files[0].read_text()

    # Use regular expression to find content between <strong> tags
    strong_contents = re.findall(
        r'<strong style="font-size: 130%">(.*?)</strong>', html_content, re.DOTALL
    )

    return strong_contents[0]
