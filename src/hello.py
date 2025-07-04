import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import shutil
import fnmatch
import json
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from config import (
    DEFAULT_GITIGNORE_PATTERNS, 
    AI_MODEL_NAME, 
    AI_PROMPT_TEMPLATE, 
    AI_MAX_WORKERS,
    SUPPORTED_CODE_EXTENSIONS
)

# Try to import AI analysis dependencies
try:
    import google.generativeai as genai
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False

# Try to import watchdog for file watching
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

class FileChangeHandler(FileSystemEventHandler):
    """Handles file system events for automatic re-analysis"""
    
    def __init__(self, app, folder_path):
        self.app = app
        self.folder_path = folder_path
        self.folder_index = None
        self.pending_files = set()
        self.debounce_timer = None
        
    def set_folder_index(self, index):
        self.folder_index = index
    
    def on_modified(self, event):
        if event.is_directory:
            return
        
        # Only watch for code file changes
        if not self.app.is_code_file(event.src_path):
            return
        
        # Check if file should be ignored
        gitignore_patterns = self.app.load_gitignore_patterns(self.folder_path)
        if self.app.is_ignored(event.src_path, self.folder_path, gitignore_patterns):
            return
        
        # Add to pending files for debounced analysis
        self.pending_files.add(event.src_path)
        
        # Cancel existing timer and start new one
        if self.debounce_timer:
            self.app.root.after_cancel(self.debounce_timer)
        
        # Debounce: wait 2 seconds before re-analyzing
        self.debounce_timer = self.app.root.after(2000, self.analyze_pending_files)
    
    def on_created(self, event):
        """Handle file creation events"""
        if event.is_directory:
            return
        
        # Check if file should be ignored
        gitignore_patterns = self.app.load_gitignore_patterns(self.folder_path)
        if self.app.is_ignored(event.src_path, self.folder_path, gitignore_patterns):
            return
        
        # Only analyze with AI if it's a code file
        if self.app.is_code_file(event.src_path):
            # Add to pending files for AI analysis
            self.pending_files.add(event.src_path)
            
            # Cancel existing timer and start new one
            if self.debounce_timer:
                self.app.root.after_cancel(self.debounce_timer)
            
            # Debounce: wait 2 seconds before analyzing
            self.debounce_timer = self.app.root.after(2000, self.analyze_pending_files)
        
        # Always update metadata and filetree
        self.trigger_full_update()
    
    def on_deleted(self, event):
        """Handle file deletion events"""
        if event.is_directory:
            return
        
        # Check if file should be ignored
        gitignore_patterns = self.app.load_gitignore_patterns(self.folder_path)
        if self.app.is_ignored(event.src_path, self.folder_path, gitignore_patterns):
            return
        
        # Remove deleted file from AI analysis if it was a code file
        if self.app.is_code_file(event.src_path) and self.folder_index is not None:
            if self.folder_index < len(self.app.folders):
                folder_info = self.app.folders[self.folder_index]
                existing_analysis = folder_info.get('ai_analysis', [])
                
                # Remove analysis for the deleted file
                deleted_file_rel = os.path.relpath(event.src_path, self.folder_path)
                existing_analysis = [item for item in existing_analysis 
                                   if item['file'] != deleted_file_rel]
                
                folder_info['ai_analysis'] = existing_analysis
        
        # Always update metadata and filetree
        self.trigger_full_update()
    
    def trigger_full_update(self):
        """Trigger a full folder update (metadata + AI analysis)"""
        if self.folder_index is None:
            return
        
        # Cancel any pending analysis
        if self.debounce_timer:
            self.app.root.after_cancel(self.debounce_timer)
            self.debounce_timer = None
        
        # Clear pending files since we're doing a full update
        self.pending_files.clear()
        
        # Schedule full update with debounce
        self.debounce_timer = self.app.root.after(2000, self.perform_full_update)
    
    def perform_full_update(self):
        """Perform a full folder update including metadata and filetree (no AI re-analysis)"""
        if self.folder_index is None or self.folder_index >= len(self.app.folders):
            return
        
        print(f"Performing full update for folder: {self.folder_path}")
        
        # Get current folder info
        folder_info = self.app.folders[self.folder_index]
        folder_path = folder_info['path']
        
        # Update folder metadata
        folder_info['file_count'] = self.app.count_files(folder_path)
        folder_info['size'] = self.app.get_folder_size(folder_path)
        
        # Update filetree (this is fast, no AI needed)
        folder_info['filetree'] = self.app.generate_filetree(folder_path)
        
        # Note: We don't re-analyze all files with AI here
        # AI analysis should only happen for specific changed files via analyze_pending_files()
        
        # Update RepoMap.md
        self.app.create_repomap_md(folder_path, folder_info)
        
        # Save and update display
        self.app.save_folders()
        self.app.root.after(0, self.app.update_display)
        
        print(f"Full update completed for {folder_path}")
        self.debounce_timer = None
    
    def analyze_pending_files(self):
        """Analyze all pending files that have changed"""
        if not self.pending_files or self.folder_index is None:
            return
        
        print(f"Re-analyzing {len(self.pending_files)} changed files...")
        
        # Get current folder info
        if self.folder_index >= len(self.app.folders):
            return
        
        folder_info = self.app.folders[self.folder_index]
        folder_path = folder_info['path']
        
        # Analyze changed files
        gitignore_patterns = self.app.load_gitignore_patterns(folder_path)
        new_analysis = []
        
        for file_path in self.pending_files:
            result = self.app.analyze_file_with_ai(file_path, folder_path, gitignore_patterns)
            if result:
                new_analysis.append(result)
        
        # Update the folder's AI analysis
        if new_analysis:
            # Merge with existing analysis, replacing changed files
            existing_analysis = folder_info.get('ai_analysis', [])
            existing_files = {item['file'] for item in existing_analysis}
            
            # Remove old analysis for changed files
            existing_analysis = [item for item in existing_analysis 
                               if item['file'] not in {os.path.relpath(fp, folder_path) for fp in self.pending_files}]
            
            # Add new analysis
            existing_analysis.extend(new_analysis)
            
            # Update folder info
            folder_info['ai_analysis'] = existing_analysis
            
            # Update RepoMap.md
            self.app.create_repomap_md(folder_path, folder_info)
            
            # Save and update display
            self.app.save_folders()
            self.app.root.after(0, self.app.update_display)
            
            print(f"Updated analysis for {len(new_analysis)} files")
        
        # Clear pending files
        self.pending_files.clear()
        self.debounce_timer = None

class RepomapApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Repomap")
        self.root.geometry("800x600")
        
        # Configure window style
        self.root.configure(bg='#2b2b2b')
        
        # Set up persistence
        self.storage_file = os.path.join(tempfile.gettempdir(), 'repomap_folders.json')
        
        # Store selected folders
        self.folders = []
        
        # Initialize AI analysis
        self.setup_ai_analysis()
        
        # Initialize file watchers
        self.file_watchers = {}  # folder_path -> (observer, handler)
        self.setup_file_watching()
        
        # Load saved folders
        self.load_saved_folders()
        
        # Create toolbar
        self.create_toolbar()
        
        # Main content area
        self.main_frame = tk.Frame(self.root, bg='#2b2b2b')
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Content area
        self.content_area = tk.Frame(self.main_frame, bg='#2b2b2b')
        self.content_area.pack(fill=tk.BOTH, expand=True)
        
        # Initialize display
        self.update_display()
        
    def create_toolbar(self):
        # Toolbar frame
        toolbar = tk.Frame(self.root, bg='#1e1e1e', height=50)
        toolbar.pack(fill=tk.X)
        toolbar.pack_propagate(False)
        
        # Folder button (using text as icon for now)
        folder_btn = tk.Button(toolbar, text="Add Folder", bg='#1e1e1e', fg='white', 
                              bd=0, font=('Arial', 12), command=self.select_folder)
        folder_btn.pack(side=tk.LEFT, padx=10, pady=10)
        
        # AI status indicator
        ai_status_text = "🤖 AI" if self.ai_enabled else "🤖 AI (No Key)"
        ai_status_color = '#00ff00' if self.ai_enabled else '#666666'
        self.ai_status_label = tk.Label(toolbar, text=ai_status_text, bg='#1e1e1e', 
                                       fg=ai_status_color, font=('Arial', 10))
        self.ai_status_label.pack(side=tk.LEFT, padx=10, pady=10)
        
    def select_folder(self):
        folder_path = filedialog.askdirectory(title="Select a folder")
        if folder_path:
            self.add_folder(folder_path)
    
    def add_folder(self, folder_path):
        # Get folder info
        folder_name = os.path.basename(folder_path)
        file_count = self.count_files(folder_path)
        folder_size = self.get_folder_size(folder_path)
        
        # Create folder info without AI analysis initially
        folder_info = {
            'name': folder_name,
            'path': folder_path,
            'file_count': file_count,
            'size': folder_size,
            'ai_analysis': [],
            'ai_analysis_complete': False
        }
        
        self.folders.append(folder_info)
        
        # Create RepoMap.md file without AI analysis
        self.create_repomap_md(folder_path, folder_info)
        
        # Save to persistent storage
        self.save_folders()
        
        # Start watching the new folder
        self.start_watching_folder(folder_path, len(self.folders) - 1)
        
        # Update display immediately
        self.update_display()
        
        # Run AI analysis in background if enabled
        if self.ai_enabled:
            print(f"Starting AI analysis for {folder_name} in background...")
            thread = threading.Thread(target=self.run_ai_analysis_async, args=(folder_path, len(self.folders) - 1))
            thread.daemon = True
            thread.start()
    
    def run_ai_analysis_async(self, folder_path, folder_index):
        """Run AI analysis in background thread"""
        try:
            print(f"Performing AI analysis on {os.path.basename(folder_path)}...")
            ai_analysis = self.analyze_folder_with_ai(folder_path)
            print(f"AI analysis complete: {len(ai_analysis)} files analyzed")
            
            # Update the folder info with AI analysis results
            if folder_index < len(self.folders):
                self.folders[folder_index]['ai_analysis'] = ai_analysis
                self.folders[folder_index]['ai_analysis_complete'] = True
                
                # Update RepoMap.md with AI results
                self.create_repomap_md(folder_path, self.folders[folder_index])
                
                # Save updated data
                self.save_folders()
                
                # Update display on main thread
                self.root.after(0, self.update_display)
                
        except Exception as e:
            print(f"Error in background AI analysis: {e}")
            if folder_index < len(self.folders):
                self.folders[folder_index]['ai_analysis_complete'] = True
                self.root.after(0, self.update_display)
    
    def load_gitignore_patterns(self, folder_path):
        """Load .gitignore patterns from the folder and its parent directories"""
        patterns = []
        current_path = folder_path
        gitignore_found = False
        
        while current_path and os.path.exists(current_path):
            gitignore_path = os.path.join(current_path, '.gitignore')
            if os.path.exists(gitignore_path):
                gitignore_found = True
                try:
                    with open(gitignore_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        lines = content.splitlines()
                        for line in lines:
                            line = line.strip()
                            if line and not line.startswith('#'):
                                patterns.append((line, current_path))
                        
                        # Check if repomap.md is already in this gitignore
                        if current_path == folder_path and 'repomap.md' not in content.lower():
                            self.add_repomap_to_gitignore(gitignore_path, content)
                except (IOError, UnicodeDecodeError):
                    pass
            
            # Move to parent directory
            parent = os.path.dirname(current_path)
            if parent == current_path:  # Reached root
                break
            current_path = parent
        
        # If no .gitignore found, create one with default patterns
        if not gitignore_found:
            self.create_default_gitignore(folder_path)
            # Add default patterns for the current folder
            for pattern in DEFAULT_GITIGNORE_PATTERNS:
                patterns.append((pattern, folder_path))
        
        return patterns
    
    def create_default_gitignore(self, folder_path):
        """Create a default .gitignore file in the folder with only relevant patterns"""
        gitignore_path = os.path.join(folder_path, '.gitignore')
        
        # Get all files and directories in the folder
        all_items = set()
        for root, dirs, files in os.walk(folder_path):
            # Add directories
            for dir_name in dirs:
                rel_path = os.path.relpath(os.path.join(root, dir_name), folder_path)
                all_items.add(rel_path)
                # Also add parent directories
                parts = rel_path.split(os.sep)
                for i in range(1, len(parts)):
                    all_items.add(os.sep.join(parts[:i]))
            
            # Add files
            for file_name in files:
                rel_path = os.path.relpath(os.path.join(root, file_name), folder_path)
                all_items.add(rel_path)
        
        # Find patterns that actually match existing items
        relevant_patterns = []
        for pattern in DEFAULT_GITIGNORE_PATTERNS:
            if self.pattern_matches_existing(pattern, all_items):
                relevant_patterns.append(pattern)
        
        try:
            with open(gitignore_path, 'w', encoding='utf-8') as f:
                f.write("# Auto-generated .gitignore by Repomap\n")
                f.write("# Common files and directories to ignore\n\n")
                for pattern in relevant_patterns:
                    f.write(f"{pattern}\n")
        except IOError:
            # Silently fail if we can't create the file
            pass
    
    def add_repomap_to_gitignore(self, gitignore_path, existing_content):
        """Add repomap.md to an existing .gitignore file"""
        try:
            with open(gitignore_path, 'a', encoding='utf-8') as f:
                f.write("\n# Repomap generated file\n")
                f.write("repomap.md\n")
        except IOError:
            # Silently fail if we can't modify the file
            pass
    
    def pattern_matches_existing(self, pattern, all_items):
        """Check if a gitignore pattern matches any existing files/directories"""
        # Use fnmatch for pattern matching (same as gitignore)
        for item in all_items:
            if fnmatch.fnmatch(item, pattern):
                return True
            # Check if it's a directory pattern and matches subdirectories
            if pattern.endswith('/'):
                pattern_name = pattern[:-1]  # Remove trailing slash
                if item == pattern_name or item.endswith(os.sep + pattern_name):
                    return True
        return False
    
    def create_repomap_md(self, folder_path, folder_info):
        """Create a repomap.md file with folder information"""
        repomap_path = os.path.join(folder_path, 'repomap.md')
        try:
            with open(repomap_path, 'w', encoding='utf-8') as f:
                f.write(f"# RepoMap - {folder_info['name']}\n\n")
                f.write(f"**Generated by Repomap**\n\n")
                f.write(f"## Folder Information\n\n")
                f.write(f"- **Name**: {folder_info['name']}\n")
                f.write(f"- **Path**: `{folder_info['path']}`\n")
                f.write(f"- **File Count**: {folder_info['file_count']:,} files\n")
                f.write(f"- **Size**: {folder_info['size']}\n")
                f.write(f"- **Generated**: {self.get_current_timestamp()}\n")
                if self.ai_enabled:
                    if folder_info.get('ai_analysis_complete', False):
                        f.write(f"- **AI Analysis**: Complete ({len(folder_info.get('ai_analysis', []))} files analyzed)\n\n")
                    else:
                        f.write(f"- **AI Analysis**: In Progress...\n\n")
                else:
                    f.write(f"- **AI Analysis**: Disabled (no API key found)\n\n")
                
                # Generate and add filetree
                f.write(f"## Filetree\n\n")
                tree_lines = self.generate_filetree(folder_path)
                for line in tree_lines:
                    f.write(f"{line}\n")
                f.write(f"\n")
                
                # Add AI analysis results if available
                if folder_info.get('ai_analysis') and folder_info.get('ai_analysis_complete', False):
                    f.write(f"## AI Analysis Results\n\n")
                    f.write(f"*Generated using Gemini API*\n\n")
                    
                    for file_analysis in folder_info['ai_analysis']:
                        f.write(f"### {file_analysis['file']}\n\n")
                        
                        if file_analysis['classes']:
                            f.write(f"**Classes:**\n")
                            for cls in file_analysis['classes']:
                                f.write(f"- **`{cls['name']}`**")
                                if cls.get('description'):
                                    f.write(f" - {cls['description']}")
                                f.write(f"\n")
                                
                                # Class methods
                                if cls.get('methods'):
                                    for method in cls['methods']:
                                        signature = method.get('signature', method['name'])
                                        f.write(f"  - `{signature}`")
                                        if method.get('description'):
                                            f.write(f" - {method['description']}")
                                        f.write(f"\n")
                                
                                # Class variables
                                if cls.get('class_variables'):
                                    for var in cls['class_variables']:
                                        f.write(f"  - `{var['name']}`")
                                        if var.get('type'):
                                            f.write(f" ({var['type']})")
                                        if var.get('description'):
                                            f.write(f" - {var['description']}")
                                        f.write(f"\n")
                                
                                f.write(f"\n")
                            f.write(f"\n")
                        
                        if file_analysis.get('standalone_functions'):
                            f.write(f"**Standalone Functions:**\n")
                            for func in file_analysis['standalone_functions']:
                                signature = func.get('signature', func['name'])
                                f.write(f"- `{signature}`")
                                if func.get('description'):
                                    f.write(f" - {func['description']}")
                                f.write(f"\n")
                            f.write(f"\n")
                        
                        if file_analysis.get('module_constants'):
                            f.write(f"**Module Constants:**\n")
                            for const in file_analysis['module_constants']:
                                f.write(f"- `{const['name']}`")
                                if const.get('value'):
                                    f.write(f" = {const['value']}")
                                if const.get('description'):
                                    f.write(f" - {const['description']}")
                                f.write(f"\n")
                            f.write(f"\n")
                        
                        if file_analysis.get('module_variables'):
                            f.write(f"**Module Variables:**\n")
                            for var in file_analysis['module_variables']:
                                f.write(f"- `{var['name']}`")
                                if var.get('type'):
                                    f.write(f" ({var['type']})")
                                if var.get('description'):
                                    f.write(f" - {var['description']}")
                                f.write(f"\n")
                            f.write(f"\n")
                        
                        f.write(f"---\n\n")
                elif self.ai_enabled and not folder_info.get('ai_analysis_complete', False):
                    f.write(f"## AI Analysis\n\n")
                    f.write(f"*AI analysis is currently in progress...*\n\n")
                    f.write(f"Check back later for detailed code structure analysis.\n\n")
        except IOError:
            # Silently fail if we can't create the file
            pass
    
    def get_current_timestamp(self):
        """Get current timestamp in a readable format"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def count_file_lines(self, file_path):
        """Count the number of lines in a file"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return len(f.readlines())
        except (IOError, UnicodeDecodeError):
            return 0
    
    def generate_filetree(self, folder_path):
        """Generate a hierarchical filetree structure with line counts"""
        gitignore_patterns = self.load_gitignore_patterns(folder_path)
        tree_lines = []
        
        def add_to_tree(path, prefix="", is_last=True):
            rel_path = os.path.relpath(path, folder_path)
            if rel_path == ".":
                # Skip the root folder itself, but process its contents
                try:
                    items = []
                    for item in os.listdir(path):
                        item_path = os.path.join(path, item)
                        if not self.is_ignored(item_path, folder_path, gitignore_patterns):
                            items.append(item_path)
                    
                    # Sort items (directories first, then files)
                    items.sort(key=lambda x: (not os.path.isdir(x), os.path.basename(x).lower()))
                    
                    # Add items to tree
                    for i, item_path in enumerate(items):
                        is_last_item = (i == len(items) - 1)
                        add_to_tree(item_path, prefix, is_last_item)
                        
                except (OSError, PermissionError):
                    pass
                return
            
            # Check if this path should be ignored
            if self.is_ignored(path, folder_path, gitignore_patterns):
                return
            
            # Always ignore .git directory and __pycache__
            if self.should_ignore_implicitly(path):
                return
            
            # Get display name
            display_name = os.path.basename(path)
            
            # Determine if it's a directory
            if os.path.isdir(path):
                # Directory
                tree_lines.append(f"{prefix}{'└── ' if is_last else '├── '}{display_name}/")
                
                # Get all items in directory
                try:
                    items = []
                    for item in os.listdir(path):
                        item_path = os.path.join(path, item)
                        if not self.is_ignored(item_path, folder_path, gitignore_patterns):
                            items.append(item_path)
                    
                    # Sort items (directories first, then files)
                    items.sort(key=lambda x: (not os.path.isdir(x), os.path.basename(x).lower()))
                    
                    # Add items to tree
                    for i, item_path in enumerate(items):
                        is_last_item = (i == len(items) - 1)
                        new_prefix = prefix + ('    ' if is_last else '│   ')
                        add_to_tree(item_path, new_prefix, is_last_item)
                        
                except (OSError, PermissionError):
                    pass
            else:
                # File - count lines
                line_count = self.count_file_lines(path)
                line_info = f" [{line_count} lines]" if line_count > 0 else ""
                
                tree_lines.append(f"{prefix}{'└── ' if is_last else '├── '}{display_name}{line_info}")
        
        # Start with the root folder
        add_to_tree(folder_path, "", True)
        
        return tree_lines
    
    def save_folders(self):
        """Save folders to persistent storage"""
        try:
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(self.folders, f, indent=2, ensure_ascii=False)
        except IOError:
            # Silently fail if we can't save
            pass
    
    def load_saved_folders(self):
        """Load folders from persistent storage"""
        try:
            if os.path.exists(self.storage_file):
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    saved_folders = json.load(f)
                    
                    # Validate and filter out non-existent folders
                    for folder_info in saved_folders:
                        if os.path.exists(folder_info.get('path', '')):
                            self.folders.append(folder_info)
                        # If folder doesn't exist, skip it (won't be saved back)
        except (IOError, json.JSONDecodeError):
            # If file doesn't exist or is corrupted, start with empty list
            self.folders = []
    
    def is_ignored(self, file_path, folder_path, gitignore_patterns):
        """Check if a file or directory should be ignored based on .gitignore patterns"""
        rel_path = os.path.relpath(file_path, folder_path)
        
        for pattern, pattern_folder in gitignore_patterns:
            # Convert pattern to match relative to the pattern's folder
            if pattern_folder != folder_path:
                pattern_rel_path = os.path.relpath(file_path, pattern_folder)
            else:
                pattern_rel_path = rel_path
            
            # Handle different pattern types
            if pattern.startswith('/'):
                # Pattern from root of gitignore file
                if fnmatch.fnmatch(rel_path, pattern[1:]) or fnmatch.fnmatch(rel_path, pattern[1:] + '/*'):
                    return True
            elif pattern.endswith('/'):
                # Directory pattern
                if fnmatch.fnmatch(rel_path, pattern[:-1]) or fnmatch.fnmatch(rel_path, pattern[:-1] + '/*'):
                    return True
            else:
                # File or general pattern
                if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(rel_path, pattern + '/*'):
                    return True
        
        return False
    
    def _walk_repository_files(self, folder_path):
        """Generator that yields all non-ignored files in a folder."""
        gitignore_patterns = self.load_gitignore_patterns(folder_path)
        for root, dirs, files in os.walk(folder_path):
            # Prune ignored directories from dirs list to prevent walking into them
            dirs[:] = [
                d for d in dirs 
                if not self.is_ignored(os.path.join(root, d), folder_path, gitignore_patterns) 
                and not self.should_ignore_implicitly(os.path.join(root, d))
            ]
            
            for file in files:
                file_path = os.path.join(root, file)
                if not self.is_ignored(file_path, folder_path, gitignore_patterns) and not self.should_ignore_implicitly(file_path):
                    yield file_path

    def count_files(self, folder_path):
        """Counts the number of non-ignored files in a folder."""
        return sum(1 for _ in self._walk_repository_files(folder_path))
    
    def should_ignore_implicitly(self, path):
        """Check if a path should be ignored implicitly (not based on gitignore)"""
        basename = os.path.basename(path)
        return basename in ['.git', '__pycache__']
    
    def get_folder_size(self, folder_path):
        total_size = 0
        for file_path in self._walk_repository_files(folder_path):
            try:
                total_size += os.path.getsize(file_path)
            except (OSError, FileNotFoundError):
                continue
        
        # Convert to MB or GB
        if total_size >= 1024**3:  # GB
            return f"{total_size / (1024**3):.2f} GB"
        else:  # MB
            return f"{total_size / (1024**2):.2f} MB"
    
    def show_empty_state(self):
        # Clear content area
        for widget in self.content_area.winfo_children():
            widget.destroy()
        
        # Create empty state
        empty_frame = tk.Frame(self.content_area, bg='#2b2b2b')
        empty_frame.pack(expand=True)
        
        # Add folder button
        add_btn = tk.Button(empty_frame, text="Add a folder", 
                           bg='#007acc', fg='white', font=('Arial', 14, 'bold'),
                           bd=0, padx=30, pady=15, command=self.select_folder)
        add_btn.pack(pady=50)
    
    def update_display(self):
        # Clear content area
        for widget in self.content_area.winfo_children():
            widget.destroy()
        
        if not self.folders:
            self.show_empty_state()
            return
        
        # Create scrollable frame
        canvas = tk.Canvas(self.content_area, bg='#2b2b2b', highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.content_area, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#2b2b2b')
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Add folder cards
        for i, folder in enumerate(self.folders):
            self.create_folder_card(scrollable_frame, folder, i)
        
        # Update scroll region after adding content
        canvas.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))
        
        canvas.pack(side="left", fill="both", expand=True)

        # Only show scrollbar if content exceeds canvas height
        if scrollable_frame.winfo_reqheight() > canvas.winfo_height():
            scrollbar.pack(side="right", fill="y")
    
    def create_folder_card(self, parent, folder, index):
        # Card frame with selection state
        card_bg = '#3c3c3c'
        card = tk.Frame(parent, bg=card_bg, relief=tk.RAISED, bd=1)
        card.pack(fill=tk.X, padx=10, pady=5)
        
        # Content frame
        content_frame = tk.Frame(card, bg=card_bg)
        content_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10, pady=10)

        # Top frame for title and delete button
        top_frame = tk.Frame(content_frame, bg=card_bg)
        top_frame.pack(fill=tk.X)
        
        # Folder name (truncated if too long)
        name = folder['name']
        if len(name) > 30:
            name = name[:27] + "..."
        
        name_label = tk.Label(top_frame, text=name, bg=card_bg, fg='white', 
                             font=('Arial', 12, 'bold'))
        name_label.pack(anchor=tk.W, side=tk.LEFT)
        
        # Remove button (individual)
        remove_btn = tk.Button(top_frame, text="🗑️", bg=card_bg, fg='#ff6b6b', 
                              bd=0, font=('Arial', 12, 'bold'), 
                              command=lambda: self.remove_folder(index))
        remove_btn.pack(side=tk.RIGHT)
        
        # Path (truncated)
        path = folder['path']
        if len(path) > 60:
            path = "..." + path[-57:]
        
        path_label = tk.Label(content_frame, text=path, bg=card_bg, fg='#cccccc', 
                             font=('Arial', 9))
        path_label.pack(anchor=tk.W, pady=(5, 5))
        
        # Info frame
        info_frame = tk.Frame(content_frame, bg=card_bg)
        info_frame.pack(fill=tk.X, pady=(5, 0))
        
        # File count
        count_label = tk.Label(info_frame, text=f"Files: {folder['file_count']}", 
                              bg=card_bg, fg='#cccccc', font=('Arial', 9))
        count_label.pack(side=tk.LEFT)
        
        # Size
        size_label = tk.Label(info_frame, text=f"Size: {folder['size']}", 
                             bg=card_bg, fg='#cccccc', font=('Arial', 9))
        size_label.pack(side=tk.LEFT, padx=(20, 0))
        
        # AI Analysis status
        if self.ai_enabled:
            if folder.get('ai_analysis_complete', False):
                ai_status = f"🤖 AI: {len(folder.get('ai_analysis', []))} files"
                ai_color = '#00ff00'
            else:
                ai_status = "🤖 AI: Analyzing..."
                ai_color = '#ffaa00'
            
            ai_label = tk.Label(info_frame, text=ai_status, 
                               bg=card_bg, fg=ai_color, font=('Arial', 9))
            ai_label.pack(side=tk.LEFT, padx=(20, 0))

    def _show_confirmation_dialog(self, title, message, delete_repomap_option, confirm_callback):
        """Shows a generic confirmation dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("400x180")
        dialog.configure(bg='#2b2b2b')
        dialog.transient(self.root)
        dialog.grab_set()

        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")

        # Main frame
        main_frame = tk.Frame(dialog, bg='#2b2b2b')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Warning text
        warning_label = tk.Label(main_frame, text=message, bg='#2b2b2b', fg='white', 
                                font=('Arial', 11), wraplength=350)
        warning_label.pack(pady=(0, 20))

        # Checkbox for deleting repomap.md file
        delete_repomap_var = tk.BooleanVar()
        if delete_repomap_option:
            delete_repomap_checkbox = tk.Checkbutton(main_frame, text="Also delete repomap.md file from the folder(s)", 
                                                    variable=delete_repomap_var, bg='#2b2b2b', fg='white', 
                                                    selectcolor='#4a4a4a', activebackground='#2b2b2b', 
                                                    activeforeground='white', font=('Arial', 10))
            delete_repomap_checkbox.pack(pady=(0, 20))

        # Button frame
        button_frame = tk.Frame(main_frame, bg='#2b2b2b')
        button_frame.pack(side=tk.BOTTOM, fill=tk.X)

        def on_confirm():
            confirm_callback(delete_repomap_var.get())
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        # Buttons
        cancel_btn = tk.Button(button_frame, text="Cancel", bg='#666666', fg='white', 
                              bd=0, padx=20, pady=8, command=on_cancel)
        cancel_btn.pack(side=tk.RIGHT, padx=(10, 0))

        delete_btn = tk.Button(button_frame, text="Delete", bg='#ff6b6b', fg='white', 
                              bd=0, padx=20, pady=8, command=on_confirm)
        delete_btn.pack(side=tk.RIGHT)

        # Focus on cancel button for safety
        cancel_btn.focus_set()
        
        # Bind Escape key to cancel
        dialog.bind('<Escape>', lambda e: on_cancel())
        
        # Wait for dialog to close
        dialog.wait_window()

    def remove_folder(self, index):
        """Remove a single folder with confirmation dialog"""
        if index >= len(self.folders):
            return
        
        folder_info = self.folders[index]
        folder_path = folder_info['path']
        folder_name = folder_info['name']
        
        message = f"Are you sure you want to remove '{folder_name}' from Repomap?"

        def confirm_delete(delete_repomap):
            # Stop watching the folder
            self.stop_watching_folder(folder_path)
            
            # Delete repomap.md if checkbox is checked
            if delete_repomap:
                repomap_path = os.path.join(folder_path, 'repomap.md')
                try:
                    if os.path.exists(repomap_path):
                        os.remove(repomap_path)
                        print(f"Deleted repomap.md from {folder_path}")
                except Exception as e:
                    print(f"Failed to delete repomap.md from {folder_path}: {e}")
            
            # Remove from folders list
            del self.folders[index]
            
            # Update watcher indices for remaining folders
            for i, folder_info in enumerate(self.folders):
                self.update_folder_watcher_index(folder_info['path'], i)
            
            self.save_folders()
            self.update_display()

        self._show_confirmation_dialog("Delete Folder", message, True, confirm_delete)
    
    def setup_ai_analysis(self):
        """Setup AI analysis if API keys are available"""
        self.ai_enabled = False
        
        if not AI_AVAILABLE:
            print("AI dependencies not available. Install with: pip install google-generativeai")
            return
        
        # Check for API keys
        gemini_key = os.getenv('GEMINI_API_KEY')
        google_key = os.getenv('GOOGLE_API_KEY')
        
        print(f"Checking API keys:")
        print(f"  GEMINI_API_KEY: {'Set' if gemini_key else 'Not set'}")
        print(f"  GOOGLE_API_KEY: {'Set' if google_key else 'Not set'}")
        
        api_key = gemini_key or google_key
        if api_key:
            try:
                genai.configure(api_key=api_key)
                self.ai_enabled = True
                print("AI Analysis enabled with Gemini API")
            except Exception as e:
                print(f"Failed to initialize AI analysis: {e}")
        else:
            print("No API key found. Set GEMINI_API_KEY or GOOGLE_API_KEY environment variable.")
    
    def setup_file_watching(self):
        """Setup file watching for all folders"""
        if not WATCHDOG_AVAILABLE:
            print("Watchdog not available. Install with: pip install watchdog")
            return
        
        # Start watching existing folders
        for i, folder_info in enumerate(self.folders):
            self.start_watching_folder(folder_info['path'], i)
    
    def start_watching_folder(self, folder_path, folder_index):
        """Start watching a specific folder for file changes"""
        if not WATCHDOG_AVAILABLE or folder_path in self.file_watchers:
            return
        
        try:
            observer = Observer()
            handler = FileChangeHandler(self, folder_path)
            handler.set_folder_index(folder_index)
            
            observer.schedule(handler, folder_path, recursive=True)
            observer.start()
            
            self.file_watchers[folder_path] = (observer, handler)
            print(f"Started watching folder: {folder_path}")
            
        except Exception as e:
            print(f"Failed to start watching {folder_path}: {e}")
    
    def stop_watching_folder(self, folder_path):
        """Stop watching a specific folder"""
        if folder_path in self.file_watchers:
            observer, handler = self.file_watchers[folder_path]
            observer.stop()
            observer.join()
            del self.file_watchers[folder_path]
            print(f"Stopped watching folder: {folder_path}")
    
    def update_folder_watcher_index(self, folder_path, new_index):
        """Update the folder index for a watcher"""
        if folder_path in self.file_watchers:
            _, handler = self.file_watchers[folder_path]
            handler.set_folder_index(new_index)
    
    def refresh_folder_metadata(self, folder_index):
        """Refresh folder metadata (file count, size, filetree)"""
        if folder_index >= len(self.folders):
            return
        
        folder_info = self.folders[folder_index]
        folder_path = folder_info['path']
        
        # Update metadata
        folder_info['file_count'] = self.count_files(folder_path)
        folder_info['size'] = self.get_folder_size(folder_path)
        
        # Update RepoMap.md
        self.create_repomap_md(folder_path, folder_info)
        
        # Save and update display
        self.save_folders()
        self.update_display()
    
    def analyze_file_with_ai(self, file_path, folder_path, gitignore_patterns):
        """Analyze a single file with AI to extract classes, functions, and important variables"""
        if not self.ai_enabled:
            return None
        
        try:
            # Check if file should be ignored
            if self.is_ignored(file_path, folder_path, gitignore_patterns):
                return None
            
            # Read file content
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            if not content.strip():
                return None
            
            # Use Gemini API to analyze the file
            model = genai.GenerativeModel(AI_MODEL_NAME)
            
            prompt = AI_PROMPT_TEMPLATE.format(
                file_name=os.path.basename(file_path),
                file_content=content
            )
            
            response = model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Try to parse JSON response
            try:
                import json
                # Clean up the response text to extract just the JSON
                if response_text.startswith('```json'):
                    response_text = response_text[7:]
                if response_text.endswith('```'):
                    response_text = response_text[:-3]
                response_text = response_text.strip()
                
                analysis_data = json.loads(response_text)
                
                result = {
                    'file': os.path.relpath(file_path, folder_path),
                    'classes': analysis_data.get('classes', []),
                    'standalone_functions': analysis_data.get('standalone_functions', []),
                    'module_constants': analysis_data.get('module_constants', []),
                    'module_variables': analysis_data.get('module_variables', [])
                }
                
                print(f"Successfully analyzed {os.path.basename(file_path)}: {len(result['classes'])} classes, {len(result['standalone_functions'])} standalone functions, {len(result['module_constants'])} constants")
                return result
                
            except json.JSONDecodeError as e:
                print(f"Failed to parse JSON response for {file_path}: {e}")
                print(f"Response was: {response_text[:200]}...")
                return self.parse_fallback_analysis(response_text, file_path, folder_path)
            
        except Exception as e:
            print(f"Error analyzing {file_path}: {e}")
            return None
    
    def parse_fallback_analysis(self, response_text, file_path, folder_path):
        """Fallback parsing when JSON response fails"""
        result = {
            'file': os.path.relpath(file_path, folder_path),
            'classes': [],
            'standalone_functions': [],
            'module_constants': [],
            'module_variables': []
        }
        
        # Simple text parsing as fallback
        lines = response_text.split('\n')
        current_section = None
        current_class = None
        
        for line in lines:
            line = line.strip()
            if 'classes' in line.lower() or 'class' in line.lower():
                current_section = 'classes'
                current_class = None
            elif 'standalone' in line.lower() and 'function' in line.lower():
                current_section = 'standalone_functions'
                current_class = None
            elif 'module' in line.lower() and 'constant' in line.lower():
                current_section = 'module_constants'
                current_class = None
            elif 'module' in line.lower() and 'variable' in line.lower():
                current_section = 'module_variables'
                current_class = None
            elif line.startswith('-') or line.startswith('*') or line.startswith('•'):
                # Extract name from list item
                name = line[1:].strip().strip('`').strip('"').strip("'")
                if name and current_section and name not in ['classes', 'standalone_functions', 'module_constants', 'module_variables']:
                    if current_section == 'classes':
                        # This is a class name
                        current_class = {
                            'name': name,
                            'methods': [],
                            'class_variables': []
                        }
                        result['classes'].append(current_class)
                    elif current_section == 'standalone_functions':
                        result['standalone_functions'].append({'name': name})
                    elif current_section == 'module_constants':
                        result['module_constants'].append({'name': name})
                    elif current_section == 'module_variables':
                        result['module_variables'].append({'name': name})
            elif line.startswith('  -') and current_class:
                # This is a method or class variable under a class
                name = line[3:].strip().strip('`').strip('"').strip("'")
                if name:
                    # Assume it's a method for now (could be improved)
                    current_class['methods'].append({'name': name})
        
        print(f"Fallback parsing for {os.path.basename(file_path)}: {len(result['classes'])} classes, {len(result['standalone_functions'])} standalone functions")
        return result
    
    def analyze_folder_with_ai(self, folder_path):
        """Analyze all files in a folder with AI using multithreading"""
        if not self.ai_enabled:
            return []
        
        # Load gitignore patterns first
        gitignore_patterns = self.load_gitignore_patterns(folder_path)
        analysis_results = []
        
        # Collect all files to analyze
        files_to_analyze = [
            fp for fp in self._walk_repository_files(folder_path) if self.is_code_file(fp)
        ]
        
        if not files_to_analyze:
            return []
        
        print(f"Analyzing {len(files_to_analyze)} files with multithreaded AI analysis...")
        
        # Use ThreadPoolExecutor for concurrent API requests
        # Limit to 5 concurrent requests to avoid overwhelming the API
        with ThreadPoolExecutor(max_workers=AI_MAX_WORKERS) as executor:
            # Submit all file analysis tasks
            future_to_file = {
                executor.submit(self.analyze_file_with_ai, file_path, folder_path, gitignore_patterns): file_path
                for file_path in files_to_analyze
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    result = future.result()
                    if result:
                        analysis_results.append(result)
                except Exception as e:
                    print(f"Error analyzing {os.path.basename(file_path)}: {e}")
        
        print(f"Completed analysis of {len(analysis_results)} files")
        return analysis_results
    
    def is_code_file(self, file_path):
        """Check if a file is a code file that should be analyzed"""
        _, ext = os.path.splitext(file_path.lower())
        return ext in SUPPORTED_CODE_EXTENSIONS
    
    def run(self):
        try:
            self.root.mainloop()
        finally:
            # Clean up file watchers when application closes
            self.cleanup_file_watchers()
    
    def cleanup_file_watchers(self):
        """Stop all file watchers"""
        for folder_path in list(self.file_watchers.keys()):
            self.stop_watching_folder(folder_path)

def main():
    app = RepomapApp()
    app.run()

if __name__ == "__main__":
    main()
