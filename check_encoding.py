from pathlib import Path

extensions = {".py", ".js", ".html", ".css", ".txt", ".md", ".json"}

for path in Path(".").rglob("*"):
    if path.is_file() and path.suffix.lower() in extensions:
        try:
            path.read_text(encoding="utf-8")
        except UnicodeDecodeError as e:
            print(f"BAD UTF-8 FILE: {path}")
            print(f"ERROR: {e}")
