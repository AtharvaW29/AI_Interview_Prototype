import json

def read_file(file_path):
    """Read a file and return its content."""
    print(f"Starting to read the file: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as file:
        print(f"File read successfully: {file.name}")
        return file.read()

def read_json(file_path):
    """Read a JSON file and return its content."""
    print(f"Starting to read the JSON file: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as file:
        print(f"Starting to read the JSON file: {file.name}")
        return json.load(file)