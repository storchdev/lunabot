import re
import glob
import sys
from prettytable import PrettyTable

# Function to extract layout names and their line numbers
def find_layouts_in_file(file_path, regex_pattern):
    results = {}
    with open(file_path, 'r', encoding='utf-8') as f:
        for line_number, line in enumerate(f, start=1):
            match = regex_pattern.search(line)
            if match:
                layout_name = match.group(1)
                if layout_name not in results:
                    results[layout_name] = []
                results[layout_name].append(line_number)
    return results

if __name__ == "__main__":
    # Compile the regex pattern
    layout_pattern = re.compile(r"\.get_layout\(['\"](.*?)['\"]\)")
    
    # Gather files from command-line arguments
    files = []
    for pattern in sys.argv[1:]:
        files.extend(glob.glob(pattern))

    # Collect results
    table_data = []
    for file_path in files:
        layouts = find_layouts_in_file(file_path, layout_pattern)
        for layout_name, line_numbers in layouts.items():
            table_data.append([layout_name, file_path, " ".join(map(str, line_numbers))])
    
    # Create and print a nicely formatted table
    table = PrettyTable()
    table.field_names = ["Name", "File", "Line Numbers"]
    for row in table_data:
        table.add_row(row)
    
    print(table)
