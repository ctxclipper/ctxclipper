#!/usr/bin/env python3
import os
import sys
import subprocess
import argparse

def is_binary(file_path):
    """
    Simple check to see if a file is binary.
    Reads the first 1024 bytes and checks for null bytes.
    """
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(1024)
            if b'\0' in chunk:
                return True
            # Check for other common binary signatures if needed, 
            # but null byte is a good heuristic for now.
    except Exception:
        return True # Treat errors (like permission denied) as binary/unreadable
    return False

def copy_to_clipboard(text):
    """
    Copies text to the macOS clipboard using pbcopy.
    """
    try:
        process = subprocess.Popen(
            'pbcopy', env={'LANG': 'en_US.UTF-8'}, stdin=subprocess.PIPE
        )
        process.communicate(text.encode('utf-8'))
        return True
    except Exception as e:
        print(f"Error copying to clipboard: {e}", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(description="Convert directory contents to a flat text format for LLM context.")
    parser.add_argument("path", nargs="?", default=".", help="Path to the directory to process (default: current directory)")
    
    # extensive default ignore list
    default_ignore = [
        ".git", ".DS_Store", "__pycache__", "node_modules", 
        ".venv", "venv", ".idea", ".vscode", 
        "dist", "build", "target", "coverage", ".next"
    ]
    
    parser.add_argument("--ignore", nargs="*", default=default_ignore, help="List of directory or file names to ignore")
    parser.add_argument("--no-copy", action="store_true", help="Do not copy output to clipboard")
    
    args = parser.parse_args()
    
    base_path = os.path.abspath(args.path)
    ignore_list = set(args.ignore)
    
    output_lines = []
    
    if not os.path.exists(base_path):
        print(f"Error: Path '{base_path}' does not exist.", file=sys.stderr)
        sys.exit(1)

    print(f"Processing directory: {base_path}...", file=sys.stderr)
    
    files_to_process = []
    use_git_strategy = False
    
    # Try to use git to list files (respects .gitignore)
    try:
        # Check if it's a git repo
        subprocess.check_call(['git', '-C', base_path, 'rev-parse'], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        
        # Get list of files from git
        # -c: cached (tracked)
        # -o: others (untracked)
        # --exclude-standard: respect .gitignore
        cmd = ['git', '-C', base_path, 'ls-files', '-c', '-o', '--exclude-standard']
        result = subprocess.check_output(cmd, encoding='utf-8', stderr=subprocess.DEVNULL)
        
        files_to_process = [os.path.join(base_path, f) for f in result.splitlines() if f.strip()]
        use_git_strategy = True
        print("Using git index to list files (respects .gitignore).", file=sys.stderr)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Not a git repository or git not found. Falling back to simple scan.", file=sys.stderr)
        pass

    if use_git_strategy:
        # Process files found by git
        for file_path in files_to_process:
            # Still apply manual ignore list on the filename
            if os.path.basename(file_path) in ignore_list:
                continue
                
            relative_path = os.path.relpath(file_path, base_path)
            
            if is_binary(file_path):
                print(f"Skipping binary file: {relative_path}", file=sys.stderr)
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                
                output_lines.append(f"=== FILE: {relative_path} ===")
                output_lines.append(content)
                output_lines.append("\n")
            except Exception as e:
                print(f"Error reading {relative_path}: {e}", file=sys.stderr)
                
    else:
        # Fallback to os.walk
        for root, dirs, files in os.walk(base_path):
            # Modify dirs in-place to skip ignored directories
            dirs[:] = [d for d in dirs if d not in ignore_list and not d.startswith('.')]
            
            for file in files:
                if file in ignore_list or file.startswith('.'):
                    continue
                    
                file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, base_path)
            
            if is_binary(file_path):
                print(f"Skipping binary file: {relative_path}", file=sys.stderr)
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                    
                output_lines.append(f"=== FILE: {relative_path} ===")
                output_lines.append(content)
                output_lines.append("\n") # Add extra newline between files
                
            except Exception as e:
                print(f"Error reading {relative_path}: {e}", file=sys.stderr)

    full_output = "\n".join(output_lines)
    
    # Print to stdout
    print(full_output)
    
    # Copy to clipboard
    if not args.no_copy:
        if copy_to_clipboard(full_output):
            print("\n[SUCCESS] Output copied to clipboard!", file=sys.stderr)
        else:
            print("\n[WARNING] Failed to copy to clipboard.", file=sys.stderr)

if __name__ == "__main__":
    main()
