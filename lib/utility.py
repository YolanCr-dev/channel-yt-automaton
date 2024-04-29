import os
import re

MAX_FILENAME_LENGTH = 75
MAX_JSON_SIZE = 400 * 1024  # 400 KB in bytes

def sanitize_filename(filename):
    # Replace problematic characters with underscores
    sanitized_name = re.sub(r'[\\/:"*?<>|\'\[\]# ]+', '_', filename)
    # Trim the filename if it exceeds the maximum length
    if len(sanitized_name) > MAX_FILENAME_LENGTH:
        sanitized_name = sanitized_name[:MAX_FILENAME_LENGTH]
    return sanitized_name

def sanitize_files(topic_dir):
    print("in sanitize")
    # Iterate over all files in the topic directory
    for root, dirs, files in os.walk(topic_dir):
        for file in files:
            file_path = os.path.join(root, file)
            print(file_path)
            # Check if the file has an extension
            if '.' not in file:
                # Get the size of the file
                file_size = os.path.getsize(file_path)
                # Assign extension based on file size
                if file_size > MAX_JSON_SIZE:
                    file_extension = ".mp4"
                else:
                    file_extension = ".json"
            else:
                # Use regular expressions to match ".m" or ".j" followed by any characters
                match = re.search(r'\.(m|j)([^.]+)?$', file)
                if match:
                    if match.group(1) == "m":
                        file_extension = ".mp4"
                    elif match.group(1) == "j":
                        file_extension = ".json"
                else:
                    # If no match is found, keep the original extension
                    file_extension = os.path.splitext(file)[1]

            # Get the sanitized filename
            sanitized_filename = sanitize_filename(file)
            # Remove any existing occurrences of ".json" or ".mp4"
            sanitized_filename = re.sub(r'\.json*|\.mp4*', '', sanitized_filename)
            # Construct the new file path with the sanitized filename and new extension
            new_file_path = os.path.join(root, sanitized_filename + file_extension)
            # Check if the sanitized filename already exists
            if os.path.exists(new_file_path):
                # print(f"File '{file}' already exists with sanitized filename '{sanitized_filename}'. Skipping.")
                continue  # Skip over this file and move to the next one
            # Rename the file
            os.rename(file_path, new_file_path)
            print(f"File '{file}' sanitized to '{sanitized_filename + file_extension}'")

# Example usage:
# topic_directory = "/path/to/your/topic/directory"
# sanitize_files(topic_directory)
