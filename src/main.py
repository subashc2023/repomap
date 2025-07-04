#!/usr/bin/env python3
"""
Repomap - Code Repository Tracker with AI-Powered Code Analysis
Enhanced with Agno framework and Google Gemini for intelligent function extraction.
Refactored for better maintainability and DRY principles.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import threading
import time
import queue
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from collections import defaultdict
import fnmatch
from typing import Dict, List, Optional, Callable, Any, Set
import logging
import copy

# Import from our config module
from config import (
    AppConstants, Theme, LanguagePatterns, ProjectStatus, ProjectInfo, 
    FileNode, AppConfig, FunctionInfo, ClassInfo, FileAnalysis,
    FunctionInfoModel, ClassInfoModel, CodeAnalysisModel,
    UIMessage, ProjectUpdateMessage, StatusMessage, ProgressMessage, AnalysisMessage,
    handle_errors, safe_queue_put, ConfigManager
)

# Agno and AI imports
try:
    from agno.agent import Agent
    from agno.models.google import Gemini
    from pydantic import BaseModel, Field
    AGNO_AVAILABLE = True
except ImportError:
    AGNO_AVAILABLE = False
    print("Warning: Agno not installed. AI analysis features will be disabled.")
    print("Install with: pip install agno google-generativeai")


class UIHelpers:
    """Utility functions for UI operations."""
    
    @staticmethod
    def configure_themed_widget(widget, widget_type='default'):
        """Apply consistent theming to widgets."""
        if not widget or not widget.winfo_exists():
            return
            
        colors = Theme.COLORS
        try:
            if widget_type == 'card':
                widget.configure(bg=colors['card_bg'], fg=colors['fg'])
            elif widget_type == 'button':
                widget.configure(bg=colors['button_bg'], fg=colors['button_fg'])
            elif widget_type == 'selected':
                widget.configure(bg=colors['selected_bg'], fg=colors['selected_fg'])
            elif widget_type == 'ai_accent':
                widget.configure(bg=colors['ai_accent'], fg=colors['bg'])
            else:
                widget.configure(bg=colors['bg'], fg=colors['fg'])
        except tk.TclError:
            pass  # Widget may have been destroyed
    
    @staticmethod
    def safe_configure(widget, **kwargs):
        """Safely configure widget if it exists."""
        if widget and widget.winfo_exists():
            try:
                widget.configure(**kwargs)
                return True
            except tk.TclError:
                return False
        return False
    
    @staticmethod
    def safe_destroy(widget):
        """Safely destroy widget if it exists."""
        if widget and widget.winfo_exists():
            try:
                widget.destroy()
                return True
            except tk.TclError:
                return False
        return False
    
    @staticmethod
    def bind_click_events(widgets: List[tk.Widget], callback: Callable):
        """Bind click events to multiple widgets."""
        def click_handler(event):
            callback()
        
        for widget in widgets:
            if widget and widget.winfo_exists():
                widget.bind("<Button-1>", click_handler)
    
    @staticmethod
    def create_status_indicator(parent, status: str, size=AppConstants.STATUS_CIRCLE_SIZE):
        """Create a status indicator circle."""
        canvas = tk.Canvas(
            parent,
            width=size, height=size,
            highlightthickness=0,
            bg=Theme.COLORS['card_bg']
        )
        
        color = Theme.STATUS_COLORS.get(status, Theme.STATUS_COLORS['error'])
        padding = 2
        canvas.create_oval(
            padding, padding, 
            size - padding, size - padding, 
            fill=color, outline=""
        )
        
        return canvas


# ============================================================================
# UTILITY CLASSES
# ============================================================================


class Debouncer:
    """Debounces rapid successive calls."""
    
    def __init__(self, delay_ms: int = AppConstants.DEBOUNCE_DELAY_MS):
        self.delay_ms = delay_ms
        self._timers: Dict[str, threading.Timer] = {}
        self._lock = threading.Lock()
    
    def debounce(self, key: str, func: Callable, *args, **kwargs):
        """Debounce a function call by key."""
        with self._lock:
            # Cancel existing timer for this key
            if key in self._timers:
                self._timers[key].cancel()
            
            # Start new timer
            timer = threading.Timer(
                self.delay_ms / 1000.0,
                func,
                args,
                kwargs
            )
            self._timers[key] = timer
            timer.start()
    
    def cancel_all(self):
        """Cancel all pending debounced calls."""
        with self._lock:
            for timer in self._timers.values():
                timer.cancel()
            self._timers.clear()


class FileOperations:
    """Utility class for safe file operations."""
    
    @staticmethod
    @handle_errors("counting lines", default_return=0)
    def count_lines(file_path: str) -> int:
        """Safe line counting with size limits."""
        file_size = os.path.getsize(file_path)
        if file_size > AppConstants.MAX_FILE_SIZE_MB * 1024 * 1024:
            logging.warning(f"Skipping large file: {file_path} ({file_size} bytes)")
            return 0
        
        with open(file_path, 'rb') as f:
            return sum(1 for _ in f)
    
    @staticmethod
    @handle_errors("reading file", default_return="")
    def read_file_content(file_path: str) -> str:
        """Safely read file content for AI analysis."""
        file_size = os.path.getsize(file_path)
        if file_size > AppConstants.MAX_ANALYZE_FILE_SIZE_MB * 1024 * 1024:
            logging.warning(f"File too large for AI analysis: {file_path} ({file_size} bytes)")
            return ""
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            logging.warning(f"Could not read file {file_path}: {e}")
            return ""
    
    @staticmethod
    @handle_errors("creating ignore file")
    def create_ignore_file(project_path: str):
        """Create comprehensive .ignore file with improved Python support."""
        ignore_path = os.path.join(project_path, '.ignore')
        gitignore_path = os.path.join(project_path, '.gitignore')
        
        # Enhanced ignore patterns with better Python virtual environment handling
        content = f"""# Repomap Ignore File
# This file was automatically created by copying your .gitignore
# and adding some default patterns. You can edit this file to
# customize what gets included in your repomap analysis.

# Repomap generated files (automatically ignored):
repomap.md
.ignore

# Python Virtual Environments (CRITICAL - these contain thousands of files):
venv/
env/
.venv/
.env/
ENV/
env.bak/
venv.bak/
.virtualenv/
virtualenv/
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# Node.js dependencies:
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*

# IDE and Editor files:
.vscode/
.idea/
*.swp
*.swo
*~
.DS_Store
Thumbs.db

# Git:
.git/

# Cache and temporary files:
.pytest_cache/
.mypy_cache/
.tox/
.coverage
.coverage.*
.cache
.nox/
htmlcov/
.nyc_output/

# Compiled and built files:
*.min.js
*.min.css
*.map
*.bundle.js

"""
        
        # Add .gitignore content if it exists
        if os.path.exists(gitignore_path):
            content += "# Patterns copied from .gitignore:\n\n"
            try:
                with open(gitignore_path, 'r', encoding='utf-8', errors='ignore') as f:
                    gitignore_content = f.read().strip()
                    if gitignore_content:
                        content += gitignore_content + "\n"
            except Exception as e:
                logging.warning(f"Could not read .gitignore: {e}")
        
        # Add additional useful patterns
        content += """
# Additional patterns for repomap (you can edit these):
*.log
*.tmp
*.temp
*.cache
*.so
.env
.env.local
*.lock
package-lock.json
yarn.lock
"""
        
        with open(ignore_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logging.info(f"Created .ignore file at {ignore_path}")


class IgnorePatternMatcher:
    """Handles file ignore pattern matching with improved gitignore support."""
    
    def __init__(self, ignore_file_path: str):
        self.patterns = []
        self.negation_patterns = []
        self.directory_patterns = []
        self.ignore_file_path = ignore_file_path
        self._load_patterns(ignore_file_path)
    
    @handle_errors("loading ignore patterns")
    def _load_patterns(self, ignore_file_path: str):
        """Load patterns from ignore file."""
        if not os.path.exists(ignore_file_path):
            logging.warning(f"Ignore file not found: {ignore_file_path}")
            return
        
        try:
            with open(ignore_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    try:
                        if line.startswith('!'):
                            self.negation_patterns.append(line[1:])
                        elif line.endswith('/'):
                            self.directory_patterns.append(line[:-1])
                        else:
                            self.patterns.append(line)
                    except Exception as e:
                        logging.warning(f"Invalid pattern on line {line_num}: {line} - {e}")
            
            logging.info(f"Loaded {len(self.patterns)} patterns, {len(self.directory_patterns)} directory patterns, {len(self.negation_patterns)} negation patterns")
        except Exception as e:
            logging.error(f"Failed to load ignore patterns: {e}")
    
    @handle_errors("checking ignore pattern", default_return=False)
    def is_ignored(self, file_path: str, base_path: str) -> bool:
        """Check if a path should be ignored with improved logic."""
        try:
            rel_path = os.path.relpath(file_path, base_path)
            is_directory = os.path.isdir(file_path)
            filename = os.path.basename(file_path)
            
            # Normalize path separators for cross-platform compatibility
            rel_path = rel_path.replace('\\', '/')
            
            # Always ignore our generated files first
            if filename in AppConstants.GENERATED_FILES:
                return True
            
            # Check directory patterns first (these are most critical for performance)
            if is_directory:
                for pattern in self.directory_patterns:
                    if self._match_pattern(rel_path, pattern, is_directory) or self._match_pattern(filename, pattern, is_directory):
                        logging.debug(f"Directory ignored by pattern '{pattern}': {rel_path}")
                        return True
            
            # Check if any parent directory matches a directory pattern
            path_parts = rel_path.split('/')
            for i, part in enumerate(path_parts[:-1]):  # Exclude the filename itself
                for pattern in self.directory_patterns:
                    if self._match_pattern(part, pattern, True):
                        logging.debug(f"Ignored due to parent directory '{part}' matching pattern '{pattern}': {rel_path}")
                        return True
            
            # Check general patterns
            ignored = False
            for pattern in self.patterns:
                if (self._match_pattern(rel_path, pattern, is_directory) or 
                    self._match_pattern(filename, pattern, is_directory)):
                    ignored = True
                    logging.debug(f"File ignored by pattern '{pattern}': {rel_path}")
                    break
            
            # Check negation patterns (these override ignores)
            if ignored:
                for pattern in self.negation_patterns:
                    if (self._match_pattern(rel_path, pattern, is_directory) or 
                        self._match_pattern(filename, pattern, is_directory)):
                        logging.debug(f"File un-ignored by negation pattern '{pattern}': {rel_path}")
                        ignored = False
                        break
            
            return ignored
            
        except Exception as e:
            logging.error(f"Error checking ignore pattern for {file_path}: {e}")
            return False
    
    @handle_errors("matching pattern", default_return=False)
    def _match_pattern(self, path: str, pattern: str, is_directory: bool = False) -> bool:
        """Match a path against a gitignore-style pattern with improved support."""
        try:
            # Handle leading slash (root-relative)
            if pattern.startswith('/'):
                pattern = pattern[1:]
                # For root-relative patterns, only match at the start
                return fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path.split('/')[0], pattern)
            
            # Handle globstar patterns (**)
            if '**' in pattern:
                # Convert ** to match any number of directories
                pattern_parts = pattern.split('**')
                if len(pattern_parts) == 2:
                    prefix, suffix = pattern_parts
                    prefix = prefix.rstrip('/')
                    suffix = suffix.lstrip('/')
                    
                    # Match if path starts with prefix and ends with suffix
                    if prefix and not path.startswith(prefix):
                        return False
                    if suffix and not path.endswith(suffix):
                        return False
                    return True
            
            # Standard fnmatch patterns - try multiple matching strategies
            matches = (
                fnmatch.fnmatch(path, pattern) or 
                fnmatch.fnmatch(os.path.basename(path), pattern) or
                (is_directory and fnmatch.fnmatch(path + '/', pattern + '/'))
            )
            
            # For directory patterns, also check if any part of the path matches
            if not matches and is_directory:
                path_parts = path.split('/')
                matches = any(fnmatch.fnmatch(part, pattern) for part in path_parts)
            
            return matches
            
        except Exception as e:
            logging.error(f"Error matching pattern '{pattern}' against '{path}': {e}")
            return False


# ============================================================================
# AI CODE ANALYZER
# ============================================================================

class CodeAnalyzer:
    """AI-powered code analyzer using Agno and Google Gemini."""
    
    def __init__(self, api_key: str = None):
        self.agent = None
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        self._initialize_agent()
    
    @handle_errors("initializing AI agent")
    def _initialize_agent(self):
        """Initialize the Agno agent with Gemini model."""
        if not AGNO_AVAILABLE:
            logging.warning("Agno not available - AI analysis disabled")
            return
        
        if not self.api_key:
            logging.warning("No Google API key found - AI analysis disabled")
            return
        
        try:
            self.agent = Agent(
                model=Gemini(
                    id="gemini-1.5-flash",
                    api_key=self.api_key
                ),
                instructions=[
                    "You are a code analysis expert. Analyze the provided code and extract information about functions, classes, and overall structure.",
                    "Be precise and concise in your descriptions.",
                    "Focus on the functional purpose of each element.",
                    "If a function or class is unclear, provide your best interpretation.",
                    "Always provide the line number where functions/classes start if visible.",
                    "For parameters, include both name and type when visible."
                ],
                response_model=CodeAnalysisModel,
                markdown=False,
                show_tool_calls=False
            )
            
            logging.info("AI agent initialized successfully")
            
        except Exception as e:
            logging.error(f"Failed to initialize AI agent: {e}")
            self.agent = None
    
    def is_available(self) -> bool:
        """Check if AI analysis is available."""
        return self.agent is not None
    
    def get_file_language(self, file_path: str) -> Optional[str]:
        """Determine if file can be analyzed and return its language."""
        ext = os.path.splitext(file_path)[1].lower()
        
        for language, extensions in LanguagePatterns.ANALYZABLE_LANGUAGES.items():
            if ext in extensions:
                return language
        
        return None
    
    @handle_errors("analyzing code", default_return=None)
    def analyze_file(self, file_path: str, content: str = None) -> Optional[FileAnalysis]:
        """Analyze a code file using AI."""
        if not self.is_available():
            return None
        
        # Get language
        language = self.get_file_language(file_path)
        if not language:
            return None
        
        # Read content if not provided
        if content is None:
            content = FileOperations.read_file_content(file_path)
        
        if not content or len(content.strip()) == 0:
            return None
        
        # Truncate very long files
        if len(content) > 50000:  # ~50KB limit
            content = content[:50000] + "\n# ... (file truncated for analysis)"
        
        try:
            # Create analysis prompt
            prompt = f"""
Analyze this {language} code file: {os.path.basename(file_path)}

Code:
```{language.lower()}
{content}
```

Extract all functions, classes, and provide a brief description of the file's purpose.
For each function, include:
- Name
- Parameters (with types if visible)
- Brief description of what it does
- Return type if clear
- Line number where it starts
- Whether it's a class method

For each class, include:
- Name  
- Brief description of its purpose
- Line number where it starts

Also provide:
- List of import statements
- Overall file description
- Complexity score (1-10, where 1 is very simple and 10 is very complex)
"""
            
            # Get AI response
            response = self.agent.run(prompt, stream=False)
            
            if response and hasattr(response, 'content'):
                # Parse the structured response
                analysis_data = response.content
                
                # Convert to our internal format
                functions = []
                for func_model in analysis_data.functions:
                    func_info = FunctionInfo(
                        name=func_model.name,
                        parameters=func_model.parameters,
                        description=func_model.description,
                        return_type=func_model.return_type,
                        line_number=func_model.line_number,
                        is_method=func_model.is_method,
                        class_name=func_model.class_name
                    )
                    functions.append(func_info)
                
                classes = []
                for class_model in analysis_data.classes:
                    class_info = ClassInfo(
                        name=class_model.name,
                        description=class_model.description,
                        line_number=class_model.line_number
                    )
                    classes.append(class_info)
                
                logging.info(f"AI analysis completed for {os.path.basename(file_path)}: {len(functions)} functions, {len(classes)} classes")
                
                return FileAnalysis(
                    file_path=file_path,
                    language=language,
                    functions=functions,
                    classes=classes,
                    imports=analysis_data.imports,
                    description=analysis_data.description,
                    complexity_score=analysis_data.complexity_score
                )
            
        except Exception as e:
            logging.error(f"AI analysis failed for {file_path}: {e}")
            return None
        
        return None


# ============================================================================
# PROJECT ANALYSIS
# ============================================================================

class ProjectAnalyzer:
    """Thread-safe project analyzer with AI-powered code analysis."""
    
    def __init__(self, project_path: str, message_queue: queue.Queue, 
                 code_analyzer: Optional[CodeAnalyzer] = None):
        self.project_path = project_path
        self.project_name = os.path.basename(project_path)
        self.message_queue = message_queue
        self.code_analyzer = code_analyzer
        
        # Analysis results
        self.file_tree = {}
        self.file_types = defaultdict(int)
        self.total_files = 0
        self.total_lines = 0
        self.analyzed_files = 0
        self.total_functions = 0
        self.file_analyses: Dict[str, FileAnalysis] = {}
        
        # Create ignore file FIRST, then initialize matcher
        self._ensure_ignore_file()
        self.ignore_matcher = IgnorePatternMatcher(os.path.join(project_path, '.ignore'))
    
    def _ensure_ignore_file(self):
        """Ensure ignore file exists before any analysis."""
        ignore_path = os.path.join(self.project_path, '.ignore')
        if not os.path.exists(ignore_path):
            self._send_progress("Creating ignore file...")
            FileOperations.create_ignore_file(self.project_path)
        else:
            logging.info(f"Using existing .ignore file: {ignore_path}")
    
    @handle_errors("project analysis")
    def analyze(self) -> ProjectInfo:
        """Perform complete project analysis with AI-powered code analysis."""
        # Ignore file should already exist from __init__
        
        self._send_progress("Scanning directory structure...")
        self.file_tree = self._scan_directory(self.project_path)
        
        if self.total_files == 0:
            logging.warning(f"No files found in {self.project_path} - check ignore patterns")
        
        self._send_progress("Detecting languages and frameworks...")
        primary_language = self._detect_primary_language()
        frameworks = self._detect_frameworks()
        
        # AI Analysis phase
        ai_enabled = self.code_analyzer and self.code_analyzer.is_available()
        if ai_enabled:
            self._send_progress("Running AI code analysis...")
            self._perform_ai_analysis()
        else:
            logging.info("AI analysis not available or disabled")
        
        self._send_progress("Generating documentation...")
        project_info = ProjectInfo(
            name=self.project_name,
            path=self.project_path,
            status=ProjectStatus.READY,
            total_files=self.total_files,
            total_lines=self.total_lines,
            analyzed_files=self.analyzed_files,
            total_functions=self.total_functions,
            primary_language=primary_language,
            frameworks=frameworks,
            ai_analysis_enabled=ai_enabled,
            last_updated=time.time()
        )
        
        self._generate_documentation(project_info)
        self._send_progress("Analysis complete!")
        
        logging.info(f"Analysis complete for {self.project_name}: {self.total_files} files, {self.total_lines} lines, {self.total_functions} functions")
        return project_info
    
    def _send_progress(self, message: str, percent: Optional[int] = None):
        """Send progress update to UI thread."""
        logging.info(f"Progress: {message}")
        progress_msg = ProgressMessage(
            project_path=self.project_path,
            progress_text=message,
            percent=percent
        )
        safe_queue_put(self.message_queue, progress_msg)
    
    @handle_errors("AI analysis")
    def _perform_ai_analysis(self):
        """Perform AI analysis on code files."""
        if not self.code_analyzer or not self.code_analyzer.is_available():
            return
        
        # Collect analyzable files
        analyzable_files = []
        self._collect_analyzable_files(self.file_tree, "", analyzable_files)
        
        if not analyzable_files:
            logging.info("No analyzable files found")
            return
        
        # Limit analysis to reasonable number of files
        max_files = min(len(analyzable_files), 100)  # Analyze up to 100 files
        analyzable_files = analyzable_files[:max_files]
        
        logging.info(f"Analyzing {len(analyzable_files)} files with AI")
        
        for i, (file_path, file_node) in enumerate(analyzable_files):
            try:
                self._send_progress(f"Analyzing {os.path.basename(file_path)}... ({i+1}/{len(analyzable_files)})")
                
                analysis = self.code_analyzer.analyze_file(file_path)
                if analysis:
                    self.file_analyses[file_path] = analysis
                    file_node.analyzed = True
                    file_node.functions_count = len(analysis.functions)
                    self.analyzed_files += 1
                    self.total_functions += len(analysis.functions)
                
            except Exception as e:
                logging.error(f"Failed to analyze {file_path}: {e}")
                continue
    
    def _collect_analyzable_files(self, tree: Dict[str, FileNode], current_path: str, result: List):
        """Recursively collect files that can be analyzed."""
        for name, node in tree.items():
            full_path = os.path.join(self.project_path, current_path, name) if current_path else os.path.join(self.project_path, name)
            
            if node.type == 'file':
                # Check if file can be analyzed
                if self.code_analyzer and self.code_analyzer.get_file_language(full_path):
                    result.append((full_path, node))
            elif node.type == 'directory':
                next_path = os.path.join(current_path, name) if current_path else name
                self._collect_analyzable_files(node.children, next_path, result)
    
    @handle_errors("directory scanning", default_return={})
    def _scan_directory(self, directory: str, relative_path: str = "", depth: int = 0) -> Dict[str, FileNode]:
        """Recursively scan directory structure with safety limits and proper ignore handling."""
        if depth > AppConstants.MAX_DIRECTORY_DEPTH:
            logging.warning(f"Maximum directory depth reached: {directory}")
            return {}
        
        if self.total_files > AppConstants.MAX_FILES_PER_PROJECT:
            logging.warning(f"Maximum file count reached: {self.total_files}")
            return {}
        
        try:
            items = os.listdir(directory)
            result = {}
            
            # Progress update
            if depth <= 2:  # Only show progress for top-level directories
                self._send_progress(f"Scanning: {relative_path or 'root'}")
            
            # Separate and sort directories and files
            directories = []
            files = []
            
            for item in items:
                item_path = os.path.join(directory, item)
                
                # CHECK IGNORE FIRST - this is critical for performance
                if self.ignore_matcher.is_ignored(item_path, self.project_path):
                    logging.debug(f"Ignored: {relative_path}/{item}" if relative_path else f"Ignored: {item}")
                    continue
                
                if os.path.isdir(item_path):
                    directories.append(item)
                else:
                    files.append(item)
            
            # Process directories
            for item in sorted(directories, key=str.lower):
                item_path = os.path.join(directory, item)
                rel_item_path = os.path.join(relative_path, item) if relative_path else item
                
                children = self._scan_directory(item_path, rel_item_path, depth + 1)
                if children:  # Only add directories that have non-ignored children
                    result[item] = FileNode(name=item, type='directory', children=children)
            
            # Process files
            for item in sorted(files, key=str.lower):
                item_path = os.path.join(directory, item)
                line_count = FileOperations.count_lines(item_path)
                
                result[item] = FileNode(name=item, type='file', lines=line_count)
                
                # Update statistics
                ext = os.path.splitext(item)[1].lower()
                self.file_types[ext] += 1
                self.total_files += 1
                self.total_lines += line_count
                
                # Progress update every N files
                if self.total_files % AppConstants.PROGRESS_UPDATE_INTERVAL == 0:
                    self._send_progress(f"Processed {self.total_files} files...")
            
            return result
            
        except PermissionError:
            logging.warning(f"Permission denied: {directory}")
            return {}
        except Exception as e:
            logging.error(f"Error scanning directory {directory}: {e}")
            return {}
    
    def _detect_primary_language(self) -> str:
        """Detect primary programming language."""
        language_scores = defaultdict(int)
        
        for ext, count in self.file_types.items():
            for language, extensions in LanguagePatterns.LANGUAGES.items():
                if ext in extensions:
                    language_scores[language] += count
        
        return max(language_scores, key=language_scores.get) if language_scores else "Unknown"
    
    def _detect_frameworks(self) -> List[str]:
        """Detect frameworks used in the project."""
        detected = []
        
        for framework, indicators in LanguagePatterns.FRAMEWORKS.items():
            if any(os.path.exists(os.path.join(self.project_path, indicator)) 
                   for indicator in indicators):
                detected.append(framework)
        
        return detected if detected else ["None detected"]
    
    def _generate_tree_structure(self, tree: Dict[str, FileNode], indent: int = 0, is_last_items: List[bool] = None) -> List[str]:
        """Generate tree structure representation with proper formatting."""
        if is_last_items is None:
            is_last_items = []
        
        lines = []
        
        # Separate directories and files
        directories = [(name, node) for name, node in tree.items() if node.type == 'directory']
        files = [(name, node) for name, node in tree.items() if node.type == 'file']
        
        all_items = sorted(directories, key=lambda x: x[0].lower()) + sorted(files, key=lambda x: x[0].lower())
        
        for i, (name, node) in enumerate(all_items):
            is_last = i == len(all_items) - 1
            
            # Build prefix based on tree structure
            prefix = ""
            for j, is_last_parent in enumerate(is_last_items):
                if j < len(is_last_items) - 1:
                    prefix += "    " if is_last_parent else "│   "
                else:
                    prefix += "└── " if is_last else "├── "
            
            if indent == 0:
                prefix = "└── " if is_last else "├── "
            
            if node.type == 'directory':
                lines.append(f"{prefix}{name}/")
                # Recursively process children
                new_is_last = is_last_items + [is_last]
                lines.extend(self._generate_tree_structure(node.children, indent + 1, new_is_last))
            else:
                analysis_indicator = " 🤖" if node.analyzed else ""
                functions_info = f" ({node.functions_count} functions)" if node.functions_count > 0 else ""
                lines.append(f"{prefix}{name} ({node.lines} lines){functions_info}{analysis_indicator}")
        
        return lines
    
    @handle_errors("generating documentation")
    def _generate_documentation(self, project_info: ProjectInfo):
        """Generate enhanced repomap.md documentation with AI analysis."""
        content = f"""# {project_info.name}

## Project Context
- **Language**: {project_info.primary_language}
- **Framework**: {', '.join(project_info.frameworks)}
- **Total Files**: {project_info.total_files}
- **Total Lines**: {project_info.total_lines}
- **AI Analysis**: {'✅ Enabled' if project_info.ai_analysis_enabled else '❌ Disabled'}
- **Analyzed Files**: {project_info.analyzed_files}
- **Total Functions**: {project_info.total_functions}
- **Last Updated**: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(project_info.last_updated))}

## Ignore Configuration
This project uses a `.ignore` file that contains patterns from the original `.gitignore` plus any additional patterns you want to exclude from repomap analysis.

Edit the `.ignore` file to customize what gets included in your repomap.

## Project Structure
```
{project_info.name}/
"""
        
        tree_lines = self._generate_tree_structure(self.file_tree)
        content += "\n".join(tree_lines)
        
        content += """
```

## File Type Distribution
"""
        
        # Add file type statistics
        if self.file_types:
            for ext, count in sorted(self.file_types.items(), key=lambda x: x[1], reverse=True)[:10]:
                percentage = (count / self.total_files) * 100 if self.total_files > 0 else 0
                ext_display = ext if ext else "no extension"
                content += f"- **{ext_display}**: {count} files ({percentage:.1f}%)\n"
        
        # Add AI Analysis section if available
        if project_info.ai_analysis_enabled and self.file_analyses:
            content += self._generate_ai_analysis_section()
        else:
            content += """
## Code Analysis
*AI-powered code analysis is available! Set your Google API key in the settings to enable automatic function extraction and code insights.*

*When enabled, this section will include:*
- Function definitions with parameters and descriptions
- Class structures and methods 
- Import dependencies
- Detailed file-by-file analysis
"""
        
        # Write documentation
        repomap_path = os.path.join(self.project_path, 'repomap.md')
        with open(repomap_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logging.info(f"Generated repomap.md at {repomap_path}")
    
    def _generate_ai_analysis_section(self) -> str:
        """Generate the AI analysis section of the documentation."""
        content = """
## 🤖 AI Code Analysis

### Function Overview
"""
        
        # Collect all functions by file
        all_functions = []
        for file_path, analysis in self.file_analyses.items():
            rel_path = os.path.relpath(file_path, self.project_path)
            for func in analysis.functions:
                all_functions.append((rel_path, func))
        
        if all_functions:
            # Group functions by file
            functions_by_file = defaultdict(list)
            for file_path, func in all_functions:
                functions_by_file[file_path].append(func)
            
            for file_path in sorted(functions_by_file.keys()):
                content += f"\n#### {file_path}\n"
                
                file_analysis = None
                for analysis in self.file_analyses.values():
                    if analysis.file_path.endswith(file_path):
                        file_analysis = analysis
                        break
                
                if file_analysis and file_analysis.description:
                    content += f"*{file_analysis.description}*\n\n"
                
                functions = functions_by_file[file_path]
                for func in sorted(functions, key=lambda f: f.line_number or 0):
                    # Format parameters
                    if func.parameters:
                        params_str = ", ".join(func.parameters)
                    else:
                        params_str = ""
                    
                    # Format function signature
                    return_info = f" → {func.return_type}" if func.return_type else ""
                    line_info = f" (line {func.line_number})" if func.line_number else ""
                    
                    content += f"**{func.name}({params_str}){return_info}**{line_info}\n"
                    if func.description:
                        content += f"- {func.description}\n"
                    content += "\n"
        
        # Add classes section
        all_classes = []
        for file_path, analysis in self.file_analyses.items():
            rel_path = os.path.relpath(file_path, self.project_path)
            for cls in analysis.classes:
                all_classes.append((rel_path, cls))
        
        if all_classes:
            content += "\n### Class Overview\n"
            
            classes_by_file = defaultdict(list)
            for file_path, cls in all_classes:
                classes_by_file[file_path].append(cls)
            
            for file_path in sorted(classes_by_file.keys()):
                content += f"\n#### {file_path}\n"
                
                classes = classes_by_file[file_path]
                for cls in sorted(classes, key=lambda c: c.line_number or 0):
                    line_info = f" (line {cls.line_number})" if cls.line_number else ""
                    content += f"**{cls.name}**{line_info}\n"
                    if cls.description:
                        content += f"- {cls.description}\n"
                    content += "\n"
        
        
        return content


# ============================================================================
# PROJECT TRACKING AND MONITORING
# ============================================================================

class ProjectWatcher(FileSystemEventHandler):
    """Watches for file system changes with debouncing."""
    
    def __init__(self, project_tracker, debouncer: Debouncer):
        self.project_tracker = project_tracker
        self.debouncer = debouncer
    
    def on_modified(self, event):
        if event.is_directory:
            return
        
        filename = os.path.basename(event.src_path)
        if filename in AppConstants.GENERATED_FILES:
            return
        
        # Find which project this file belongs to
        for project_path in self.project_tracker.get_tracked_projects():
            if event.src_path.startswith(project_path):
                # Debounce the change to avoid rapid re-analysis
                self.debouncer.debounce(
                    project_path,
                    self.project_tracker.mark_project_changed,
                    project_path
                )
                break


class ProjectTracker:
    """Thread-safe project tracker with AI-enhanced analysis."""
    
    def __init__(self, config_manager: ConfigManager, message_queue: queue.Queue, 
                 code_analyzer: Optional[CodeAnalyzer] = None):
        self.config_manager = config_manager
        self.message_queue = message_queue
        self.code_analyzer = code_analyzer
        self.projects: Dict[str, ProjectInfo] = {}
        self.observers: Dict[str, Observer] = {}
        self.debouncer = Debouncer()
        
        # Thread safety
        self._projects_lock = threading.RLock()
        self._running = True
    
    @handle_errors("loading saved projects")
    def load_saved_projects(self):
        """Load previously saved projects."""
        config = self.config_manager.load_config()
        saved_projects = config.tracked_folders
        
        logging.info(f"Loading {len(saved_projects)} saved projects")
        
        for project_path in saved_projects:
            if os.path.exists(project_path) and os.path.isdir(project_path):
                logging.info(f"Loading saved project: {project_path}")
                self.add_project(project_path, save_config=False)
            else:
                logging.warning(f"Skipping non-existent folder: {project_path}")
    
    @handle_errors("adding project", default_return=False)
    def add_project(self, project_path: str, save_config: bool = True) -> bool:
        """Add a new project to track."""
        with self._projects_lock:
            if project_path in self.projects:
                logging.warning(f"Project already tracked: {project_path}")
                return False
            
            # Validate path
            if not os.path.exists(project_path) or not os.path.isdir(project_path):
                logging.error(f"Invalid project path: {project_path}")
                return False
            
            logging.info(f"Adding project: {project_path}")
            
            # Create initial project info
            project_info = ProjectInfo(
                name=os.path.basename(project_path),
                path=project_path,
                status=ProjectStatus.PROCESSING,
                ai_analysis_enabled=self.code_analyzer and self.code_analyzer.is_available()
            )
            self.projects[project_path] = project_info
            
            # Send immediate update to UI
            self._send_project_update(project_path, project_info)
            
            # Start monitoring
            self._start_monitoring(project_path)
            
            # Analyze in background
            if self._running:
                threading.Thread(
                    target=self._analyze_project,
                    args=(project_path,),
                    daemon=True
                ).start()
            
            if save_config:
                self._save_config()
            
            logging.info(f"Successfully added project: {project_path}")
            return True
    
    @handle_errors("removing project")
    def remove_project(self, project_path: str, remove_files: bool = True):
        """Remove a project from tracking."""
        with self._projects_lock:
            if project_path not in self.projects:
                return
            
            # Stop monitoring
            if project_path in self.observers:
                try:
                    self.observers[project_path].stop()
                    self.observers[project_path].join(timeout=AppConstants.OBSERVER_TIMEOUT_S)
                except Exception as e:
                    logging.warning(f"Error stopping observer: {e}")
                finally:
                    del self.observers[project_path]
            
            # Remove project
            del self.projects[project_path]
            
            # Cancel any pending analysis
            self.debouncer.debounce(project_path, lambda: None)
            
            # Clean up generated files if requested
            if remove_files:
                for filename in AppConstants.GENERATED_FILES:
                    file_path = os.path.join(project_path, filename)
                    if os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                        except Exception as e:
                            logging.warning(f"Could not remove {filename}: {e}")
            
            self._save_config()
    
    def mark_project_changed(self, project_path: str):
        """Mark a project as changed and schedule re-analysis."""
        with self._projects_lock:
            if project_path in self.projects and self._running:
                self.projects[project_path].status = ProjectStatus.PROCESSING
                self._send_project_update(project_path, self.projects[project_path])
                
                threading.Thread(
                    target=self._analyze_project,
                    args=(project_path,),
                    daemon=True
                ).start()
    
    def get_tracked_projects(self) -> List[str]:
        """Get list of tracked project paths."""
        with self._projects_lock:
            return list(self.projects.keys())
    
    def get_project_info(self, project_path: str) -> Optional[ProjectInfo]:
        """Get project information."""
        with self._projects_lock:
            return self.projects.get(project_path)
    
    def get_all_projects(self) -> Dict[str, ProjectInfo]:
        """Get all projects (thread-safe copy)."""
        with self._projects_lock:
            return copy.deepcopy(self.projects)
    
    def _send_project_update(self, project_path: str, project_info: ProjectInfo):
        """Send project update to UI thread."""
        project_info_copy = copy.deepcopy(project_info)
        message = ProjectUpdateMessage(
            project_path=project_path, 
            project_info=project_info_copy
        )
        safe_queue_put(self.message_queue, message)
    
    @handle_errors("starting file monitoring")
    def _start_monitoring(self, project_path: str):
        """Start file system monitoring for a project."""
        observer = Observer()
        handler = ProjectWatcher(self, self.debouncer)
        observer.schedule(handler, project_path, recursive=True)
        observer.start()
        self.observers[project_path] = observer
    
    @handle_errors("analyzing project")
    def _analyze_project(self, project_path: str):
        """Analyze a project in background thread."""
        analyzer = ProjectAnalyzer(project_path, self.message_queue, self.code_analyzer)
        project_info = analyzer.analyze()
        
        with self._projects_lock:
            if project_path in self.projects and self._running:
                self.projects[project_path] = project_info
                self._send_project_update(project_path, project_info)
    
    @handle_errors("saving configuration")
    def _save_config(self):
        """Save current configuration."""
        with self._projects_lock:
            config = self.config_manager.load_config()  # Load current config to preserve other settings
            config.tracked_folders = list(self.projects.keys())
            self.config_manager.save_config(config)
    
    def set_code_analyzer(self, code_analyzer: CodeAnalyzer):
        """Set or update the code analyzer."""
        self.code_analyzer = code_analyzer
        logging.info(f"Code analyzer updated: {'available' if code_analyzer and code_analyzer.is_available() else 'unavailable'}")
    
    def cleanup(self):
        """Clean up resources safely."""
        self._running = False
        
        # Cancel debounced operations
        self.debouncer.cancel_all()
        
        # Stop all observers with timeout
        for project_path, observer in list(self.observers.items()):
            try:
                observer.stop()
                observer.join(timeout=AppConstants.OBSERVER_TIMEOUT_S)
            except Exception as e:
                logging.warning(f"Error stopping observer for {project_path}: {e}")
        
        self.observers.clear()


# ============================================================================
# UI COMPONENTS
# ============================================================================

class ProjectCard:
    """Individual project card UI component with AI analysis support."""
    
    def __init__(self, parent, project_info: ProjectInfo, on_select: Callable):
        self.parent = parent
        self.project_info = project_info
        self.on_select = on_select
        self.selected = False
        self.progress_text = ""
        
        # UI elements
        self.widget = None
        self.status_canvas = None
        self.info_frame = None
        self.name_label = None
        self.status_label = None
        self.ai_indicator = None
    
    def create(self):
        """Create the project card."""
        self.widget = tk.Frame(
            self.parent,
            bg=Theme.COLORS['card_bg'],
            relief="flat",
            bd=1
        )
        
        # Status indicator
        self.status_canvas = UIHelpers.create_status_indicator(
            self.widget, 
            self.project_info.status.value
        )
        self.status_canvas.pack(side="left", padx=(AppConstants.CARD_PADDING, 8), pady=8)
        
        # Project information
        self._create_project_info()
        
        # AI indicator
        if self.project_info.ai_analysis_enabled:
            self.ai_indicator = tk.Label(
                self.widget,
                text="🤖",
                font=('Arial', 12),
                bg=Theme.COLORS['card_bg'],
                fg=Theme.COLORS['ai_accent']
            )
            self.ai_indicator.pack(side="right", padx=(0, AppConstants.CARD_PADDING), pady=8)
        
        # Bind click events to all widgets
        self._bind_click_events()
        
        return self.widget
    
    def _create_project_info(self):
        """Create project information display."""
        self.info_frame = tk.Frame(self.widget, bg=Theme.COLORS['card_bg'])
        self.info_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        
        # Project name and path
        self.name_label = tk.Label(
            self.info_frame,
            text=f"{self.project_info.name} - {self.project_info.path}",
            font=('Arial', 10),
            bg=Theme.COLORS['card_bg'],
            fg=Theme.COLORS['fg'],
            anchor='w'
        )
        self.name_label.pack(fill="x")
        
        # Status/progress text
        self.status_label = tk.Label(
            self.info_frame,
            text=self._get_status_text(),
            font=('Arial', 8),
            bg=Theme.COLORS['card_bg'],
            fg=Theme.STATUS_COLORS[self.project_info.status.value],
            anchor='w'
        )
        self.status_label.pack(fill="x")
    
    def _bind_click_events(self):
        """Bind click events to all relevant widgets."""
        widgets_to_bind = [self.widget, self.info_frame, self.name_label, self.status_label]
        if self.ai_indicator:
            widgets_to_bind.append(self.ai_indicator)
        
        UIHelpers.bind_click_events(
            widgets_to_bind,
            lambda: self.on_select(self.project_info.path)
        )
    
    def _get_status_text(self) -> str:
        """Get appropriate status text."""
        if self.progress_text:
            return self.progress_text
        
        if self.project_info.status == ProjectStatus.READY:
            ai_info = f", {self.project_info.total_functions} functions" if self.project_info.ai_analysis_enabled else ""
            return f"Ready - {self.project_info.total_files} files, {self.project_info.total_lines} lines{ai_info}"
        elif self.project_info.status == ProjectStatus.PROCESSING:
            return "Processing..."
        elif self.project_info.status == ProjectStatus.ANALYZING:
            return "Running AI analysis..."
        else:  # ERROR
            return f"Error: {self.project_info.error_message}"
    
    def set_selected(self, selected: bool):
        """Update visual selection state."""
        self.selected = selected
        widget_type = 'selected' if selected else 'card'
        
        widgets_to_update = [self.widget, self.info_frame, self.name_label, 
                           self.status_label, self.status_canvas]
        if self.ai_indicator:
            widgets_to_update.append(self.ai_indicator)
            
        for widget in widgets_to_update:
            UIHelpers.configure_themed_widget(widget, widget_type)
    
    def update_project_info(self, project_info: ProjectInfo):
        """Update project information efficiently."""
        old_status = self.project_info.status
        self.project_info = project_info
        
        # Update status indicator if status changed
        if old_status != project_info.status and self.status_canvas:
            UIHelpers.safe_destroy(self.status_canvas)
            self.status_canvas = UIHelpers.create_status_indicator(
                self.widget,
                project_info.status.value
            )
            self.status_canvas.pack(side="left", padx=(AppConstants.CARD_PADDING, 8), pady=8)
        
        # Update status text
        UIHelpers.safe_configure(
            self.status_label,
            text=self._get_status_text(),
            fg=Theme.STATUS_COLORS[project_info.status.value]
        )
        
        # Add/remove AI indicator
        if project_info.ai_analysis_enabled and not self.ai_indicator:
            self.ai_indicator = tk.Label(
                self.widget,
                text="🤖",
                font=('Arial', 12),
                bg=Theme.COLORS['card_bg'],
                fg=Theme.COLORS['ai_accent']
            )
            self.ai_indicator.pack(side="right", padx=(0, AppConstants.CARD_PADDING), pady=8)
        elif not project_info.ai_analysis_enabled and self.ai_indicator:
            UIHelpers.safe_destroy(self.ai_indicator)
            self.ai_indicator = None
        
        # Rebind click events to include any new widgets
        self._bind_click_events()
    
    def update_progress(self, progress_text: str):
        """Update progress text."""
        self.progress_text = progress_text
        UIHelpers.safe_configure(self.status_label, text=progress_text)


class ProjectListView:
    """Project list view component with AI indicators."""
    
    def __init__(self, parent):
        self.parent = parent
        self.project_cards: Dict[str, ProjectCard] = {}
        self.selected_project = None
        self.on_selection_change: Optional[Callable] = None
        
        # UI elements
        self.widget = None
        self.scrollable_frame = None
        self.no_projects_label = None
    
    def create(self):
        """Create the project list view."""
        # Main container
        container = ttk.LabelFrame(self.parent, text="Tracked Folders", padding=str(AppConstants.CARD_PADDING))
        
        # Scrollable area
        canvas = tk.Canvas(container, height=AppConstants.LIST_HEIGHT, bg=Theme.COLORS['bg'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.widget = container
        return container
    
    def update_projects(self, projects: Dict[str, ProjectInfo]):
        """Update the project list efficiently."""
        # Check if selected project was removed
        removed_selected = False
        
        # Remove cards for projects that no longer exist
        for project_path in list(self.project_cards.keys()):
            if project_path not in projects:
                if project_path == self.selected_project:
                    self.selected_project = None
                    removed_selected = True
                
                card = self.project_cards[project_path]
                UIHelpers.safe_destroy(card.widget)
                del self.project_cards[project_path]
        
        # Add or update cards for current projects
        for project_path, project_info in projects.items():
            if project_path in self.project_cards:
                self.project_cards[project_path].update_project_info(project_info)
            else:
                self._create_project_card(project_path, project_info)
        
        # Show message if no projects
        self._update_empty_state(projects)
        
        # Notify about selection change if selected project was removed
        if removed_selected and self.on_selection_change:
            self.on_selection_change(None)
    
    @handle_errors("creating project card")
    def _create_project_card(self, project_path: str, project_info: ProjectInfo):
        """Create a new project card."""
        card = ProjectCard(
            self.scrollable_frame,
            project_info,
            self._on_project_selected
        )
        card.create()
        card.widget.pack(fill="x", pady=2, padx=5)
        self.project_cards[project_path] = card
    
    def _update_empty_state(self, projects: Dict[str, ProjectInfo]):
        """Update empty state message."""
        if not projects:
            if not self.no_projects_label or not self.no_projects_label.winfo_exists():
                # Create a styled empty state frame
                empty_frame = tk.Frame(self.scrollable_frame, bg=Theme.COLORS['bg'])
                empty_frame.pack(pady=40, padx=20, fill='both', expand=True)
                
                # Title
                title_label = tk.Label(
                    empty_frame,
                    text="No folders tracked",
                    font=('Arial', 14, 'bold'),
                    bg=Theme.COLORS['bg'],
                    fg=Theme.COLORS['fg']
                )
                title_label.pack(pady=(0, 10))
                
                # Instructions
                instruction_label = tk.Label(
                    empty_frame,
                    text="Click 'Add Folder' to get started",
                    font=('Arial', 10),
                    bg=Theme.COLORS['bg'],
                    fg=Theme.COLORS['muted_fg']
                )
                instruction_label.pack(pady=(0, 20))
                
                # AI status
                ai_available = AGNO_AVAILABLE and os.getenv('GEMINI_API_KEY')
                ai_text = "🤖 AI analysis ready! Add a folder to begin." if ai_available else "🤖 Enable AI analysis in settings for intelligent code insights!"
                ai_label = tk.Label(
                    empty_frame,
                    text=ai_text,
                    font=('Arial', 10),
                    bg=Theme.COLORS['bg'],
                    fg=Theme.COLORS['ai_accent']
                )
                ai_label.pack()
                
                self.no_projects_label = empty_frame
        elif self.no_projects_label:
            UIHelpers.safe_destroy(self.no_projects_label)
            self.no_projects_label = None
    
    def _on_project_selected(self, project_path: str):
        """Handle project selection."""
        # Update visual state
        for path, card in self.project_cards.items():
            card.set_selected(path == project_path)
        
        self.selected_project = project_path
        
        if self.on_selection_change:
            self.on_selection_change(project_path)
    
    def get_selected_project(self) -> Optional[str]:
        """Get currently selected project path."""
        return self.selected_project
    
    def set_selection_callback(self, callback: Callable):
        """Set callback for selection changes."""
        self.on_selection_change = callback
    
    def update_progress(self, project_path: str, progress_text: str):
        """Update progress for a specific project."""
        if project_path in self.project_cards:
            self.project_cards[project_path].update_progress(progress_text)


# ============================================================================
# SETTINGS DIALOG
# ============================================================================

class SettingsDialog:
    """Settings dialog for AI configuration."""
    
    def __init__(self, parent, config: AppConfig, on_save: Callable):
        self.parent = parent
        self.config = config
        self.on_save = on_save
        self.dialog = None
        self.api_key_var = None
        self.ai_enabled_var = None
    
    def show(self):
        """Show the settings dialog."""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Repomap Settings")
        self.dialog.geometry("550x400")
        self.dialog.resizable(True, True)
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        
        # Center the dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")
        
        self._create_ui()
    
    def _create_ui(self):
        """Create the settings UI."""
        # Configure dialog grid
        self.dialog.grid_rowconfigure(0, weight=1)
        self.dialog.grid_columnconfigure(0, weight=1)
        
        # Main frame with grid layout for better control
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        main_frame.grid_columnconfigure(0, weight=1)
        
        # Title
        title_label = ttk.Label(
            main_frame,
            text="Repomap Settings",
            font=('Arial', 16, 'bold')
        )
        title_label.grid(row=0, column=0, pady=(0, 20), sticky="w")
        
        # AI Analysis Section
        ai_frame = ttk.LabelFrame(main_frame, text="AI Analysis Configuration", padding="15")
        ai_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 20))
        ai_frame.grid_columnconfigure(0, weight=1)
        
        # Current status
        current_status = "Available" if AGNO_AVAILABLE else "Unavailable (install agno)"
        status_label = ttk.Label(
            ai_frame,
            text=f"AI Framework Status: {current_status}",
            font=('Arial', 9),
            foreground="green" if AGNO_AVAILABLE else "red"
        )
        status_label.grid(row=0, column=0, sticky="w", pady=(0, 10))
        
        # AI Enabled checkbox
        self.ai_enabled_var = tk.BooleanVar(value=self.config.ai_analysis_enabled)
        ai_checkbox = ttk.Checkbutton(
            ai_frame,
            text="Enable AI-powered code analysis (requires Google API key)",
            variable=self.ai_enabled_var,
            state='normal' if AGNO_AVAILABLE else 'disabled'
        )
        ai_checkbox.grid(row=1, column=0, sticky="w", pady=(0, 15))
        
        # Google API Key
        api_key_label = ttk.Label(ai_frame, text="Google API Key:")
        api_key_label.grid(row=2, column=0, sticky="w", pady=(0, 5))
        
        self.api_key_var = tk.StringVar(value=self.config.google_api_key)
        api_key_entry = ttk.Entry(
            ai_frame,
            textvariable=self.api_key_var,
            show="*",
            width=60,
            state='normal' if AGNO_AVAILABLE else 'disabled'
        )
        api_key_entry.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 15))
        
        # Instructions
        instructions = ttk.Label(
            ai_frame,
            text="Get your free API key from: https://aistudio.google.com/app/apikey\n"
                 "AI analysis extracts functions, classes, and generates intelligent code insights.",
            font=('Arial', 9),
            foreground="gray",
            wraplength=500
        )
        instructions.grid(row=4, column=0, sticky="w")
        
        # Button frame at the bottom
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(20, 0))
        button_frame.grid_columnconfigure(1, weight=1)  # Spacer column
        
        # Test button (left side)
        test_button = ttk.Button(
            button_frame,
            text="Test API Key",
            command=self._test_api_key,
            state='normal' if AGNO_AVAILABLE else 'disabled'
        )
        test_button.grid(row=0, column=0, padx=(0, 10))
        
        # Save button (right side)
        save_button = ttk.Button(
            button_frame,
            text="Save",
            command=self._save_settings
        )
        save_button.grid(row=0, column=2, padx=(10, 0))
        
        # Cancel button (right side)
        cancel_button = ttk.Button(
            button_frame,
            text="Cancel",
            command=self.dialog.destroy
        )
        cancel_button.grid(row=0, column=3, padx=(10, 0))
        
        # Make the entry widget expand
        ai_frame.grid_columnconfigure(0, weight=1)
    
    def _test_api_key(self):
        """Test the API key."""
        if not AGNO_AVAILABLE:
            messagebox.showerror("Error", "Agno framework not available. Please install with: pip install agno google-generativeai")
            return
            
        api_key = self.api_key_var.get().strip()
        if not api_key:
            messagebox.showwarning("Warning", "Please enter an API key to test.")
            return
        
        try:
            # Test the API key by creating a simple agent
            test_analyzer = CodeAnalyzer(api_key)
            if test_analyzer.is_available():
                messagebox.showinfo("Success", "API key is valid and working!")
            else:
                messagebox.showerror("Error", "API key test failed. Please check your key.")
        except Exception as e:
            messagebox.showerror("Error", f"API key test failed: {str(e)}")
    
    def _save_settings(self):
        """Save the settings."""
        # Update config
        self.config.ai_analysis_enabled = self.ai_enabled_var.get() if AGNO_AVAILABLE else False
        self.config.google_api_key = self.api_key_var.get().strip() if AGNO_AVAILABLE else ""
        
        # Set environment variable
        if self.config.google_api_key:
            os.environ['GEMINI_API_KEY'] = self.config.google_api_key
        
        # Call save callback
        self.on_save(self.config)
        
        # Close dialog
        self.dialog.destroy()
        
        messagebox.showinfo("Success", "Settings saved! Restart analysis to apply AI changes.")


# ============================================================================
# APPLICATION CONTROLLERS
# ============================================================================

class StatusUpdater:
    """Centralized status update management to prevent inconsistencies."""
    
    def __init__(self, status_label: ttk.Label):
        self.status_label = status_label
    
    def update_status_for_project(self, project_info: ProjectInfo):
        """Update status label for a specific project."""
        if project_info.status == ProjectStatus.READY:
            ai_info = f", {project_info.total_functions} functions analyzed" if project_info.ai_analysis_enabled else ""
            status_text = (f"Selected: {project_info.name} - "
                          f"{project_info.total_files} files, {project_info.total_lines} lines "
                          f"({project_info.primary_language}){ai_info}")
        elif project_info.status == ProjectStatus.PROCESSING:
            status_text = f"Selected: {project_info.name} - Processing..."
        elif project_info.status == ProjectStatus.ANALYZING:
            status_text = f"Selected: {project_info.name} - Running AI analysis..."
        else:  # ERROR
            status_text = f"Selected: {project_info.name} - Error: {project_info.error_message}"
        
        UIHelpers.safe_configure(self.status_label, text=status_text)
    
    def update_general_status(self, status_text: str):
        """Update status with general message."""
        UIHelpers.safe_configure(self.status_label, text=status_text)


class MessageHandler:
    """Handles message queue processing and UI updates."""
    
    def __init__(self, message_queue: queue.Queue, project_list_view: ProjectListView, 
                 status_updater: StatusUpdater, project_tracker: ProjectTracker):
        self.message_queue = message_queue
        self.project_list_view = project_list_view
        self.status_updater = status_updater
        self.project_tracker = project_tracker
        self.running = True
    
    def start_processing(self, root: tk.Tk):
        """Start message processing loop."""
        self._process_messages()
        root.after(AppConstants.QUEUE_CHECK_INTERVAL_MS, 
                  lambda: self.start_processing(root) if self.running else None)
    
    def stop_processing(self):
        """Stop message processing."""
        self.running = False
    
    @handle_errors("processing messages")
    def _process_messages(self):
        """Process messages from background threads."""
        if not self.running:
            return
        
        # Process all pending messages
        processed = 0
        while processed < AppConstants.MAX_MESSAGES_PER_CYCLE:
            try:
                message = self.message_queue.get_nowait()
                self._handle_message(message)
                processed += 1
            except queue.Empty:
                break
    
    @handle_errors("handling message")
    def _handle_message(self, message: UIMessage):
        """Handle individual messages from background threads."""
        if isinstance(message, ProjectUpdateMessage):
            self._handle_project_update(message)
        elif isinstance(message, StatusMessage):
            self._handle_status_update(message)
        elif isinstance(message, ProgressMessage):
            self._handle_progress_update(message)
        elif isinstance(message, AnalysisMessage):
            self._handle_analysis_update(message)
        else:
            logging.warning(f"Unknown message type: {type(message)}")
    
    def _handle_project_update(self, message: ProjectUpdateMessage):
        """Handle project update message."""
        projects = self.project_tracker.get_all_projects()
        self.project_list_view.update_projects(projects)
        
        # Update status if this project is selected
        if message.project_path == self.project_list_view.get_selected_project():
            self.status_updater.update_status_for_project(message.project_info)
    
    def _handle_status_update(self, message: StatusMessage):
        """Handle status update message."""
        self.status_updater.update_general_status(message.status_text)
    
    def _handle_progress_update(self, message: ProgressMessage):
        """Handle progress update message."""
        self.project_list_view.update_progress(message.project_path, message.progress_text)
    
    def _handle_analysis_update(self, message: AnalysisMessage):
        """Handle AI analysis update message."""
        # Could be used for real-time analysis updates
        pass


class EventController:
    """Handles user interface events and actions."""
    
    def __init__(self, project_tracker: ProjectTracker, project_list_view: ProjectListView, 
                 status_updater: StatusUpdater, add_button: ttk.Button, 
                 remove_button: ttk.Button, refresh_button: ttk.Button, 
                 config_manager: ConfigManager):
        self.project_tracker = project_tracker
        self.project_list_view = project_list_view
        self.status_updater = status_updater
        self.add_button = add_button
        self.remove_button = remove_button
        self.refresh_button = refresh_button
        self.config_manager = config_manager
    
    @handle_errors("adding folder")
    def add_folder(self):
        """Add a new folder to track."""
        try:
            UIHelpers.safe_configure(self.add_button, state='disabled')
            folder_path = filedialog.askdirectory(title="Select folder to track")
            
            if folder_path:
                if self.project_tracker.add_project(folder_path):
                    ai_status = " with AI analysis" if self.project_tracker.code_analyzer and self.project_tracker.code_analyzer.is_available() else ""
                    self.status_updater.update_general_status(f"Added folder: {os.path.basename(folder_path)} - Starting analysis{ai_status}...")
                else:
                    messagebox.showerror(
                        "Error",
                        "Failed to add folder or folder already tracked"
                    )
        finally:
            UIHelpers.safe_configure(self.add_button, state='normal')
    
    @handle_errors("removing folder")
    def remove_folder(self):
        """Remove selected folder from tracking."""
        selected = self.project_list_view.get_selected_project()
        if selected:
            # Custom confirmation dialog with option to delete generated files
            root = self.remove_button.winfo_toplevel()
            dialog = tk.Toplevel(root)
            dialog.title("Confirm Removal")
            dialog.transient(root)
            dialog.grab_set()
            # Message
            msg = ttk.Label(dialog, text=f"Remove tracking for:\n{selected}", justify="left")
            msg.pack(padx=20, pady=(20, 10))
            # Checkbox for deleting files
            remove_var = tk.BooleanVar(value=True)
            chk = ttk.Checkbutton(dialog, text="Also delete repomap.md and .ignore files", variable=remove_var)
            chk.pack(padx=20, pady=(0, 10))
            # Buttons
            btn_frame = ttk.Frame(dialog)
            btn_frame.pack(pady=(0, 20))
            response = {"confirmed": False}
            def on_remove():
                response["confirmed"] = True
                dialog.destroy()
            def on_cancel():
                dialog.destroy()
            remove_btn = ttk.Button(btn_frame, text="Remove", command=on_remove)
            remove_btn.pack(side=tk.LEFT, padx=(0, 10))
            cancel_btn = ttk.Button(btn_frame, text="Cancel", command=on_cancel)
            cancel_btn.pack(side=tk.LEFT)
            # Ensure appropriate sizing
            dialog.update_idletasks()
            dialog.geometry(f"{dialog.winfo_width()}x{dialog.winfo_height()}")
            root.wait_window(dialog)
            if response["confirmed"]:
                self.project_tracker.remove_project(selected, remove_var.get())
                self.status_updater.update_general_status(f"Removed folder: {os.path.basename(selected)}")
        else:
            messagebox.showwarning("Warning", "Please select a folder to remove")
    
    @handle_errors("refreshing folder")
    def refresh_folder(self):
        """Refresh analysis for selected folder."""
        selected = self.project_list_view.get_selected_project()
        if selected:
            self.project_tracker.mark_project_changed(selected)
            ai_status = " with AI analysis" if self.project_tracker.code_analyzer and self.project_tracker.code_analyzer.is_available() else ""
            self.status_updater.update_general_status(f"Refreshing analysis{ai_status} for: {os.path.basename(selected)}")
        else:
            messagebox.showwarning("Warning", "Please select a folder to refresh")
    
    def show_settings(self, root: tk.Tk):
        """Show settings dialog."""
        config = self.config_manager.load_config()
        
        def on_settings_save(new_config: AppConfig):
            self.config_manager.save_config(new_config)
            
            # Update code analyzer
            if new_config.ai_analysis_enabled and new_config.google_api_key and AGNO_AVAILABLE:
                code_analyzer = CodeAnalyzer(new_config.google_api_key)
                self.project_tracker.set_code_analyzer(code_analyzer)
                if code_analyzer.is_available():
                    logging.info("AI analysis enabled")
                else:
                    logging.warning("AI analysis failed to initialize")
            else:
                self.project_tracker.set_code_analyzer(None)
                logging.info("AI analysis disabled")
        
        settings_dialog = SettingsDialog(root, config, on_settings_save)
        settings_dialog.show()
    
    def on_project_selected(self, project_path: Optional[str]):
        """Handle project selection."""
        # Update button states
        self._update_button_states(project_path is not None)
        
        if project_path:
            project_info = self.project_tracker.get_project_info(project_path)
            if project_info:
                self.status_updater.update_status_for_project(project_info)
        else:
            # No project selected
            ai_status = "AI analysis available!" if self.project_tracker.code_analyzer and self.project_tracker.code_analyzer.is_available() else "Enable AI in settings"
            self.status_updater.update_general_status(f"Ready - {ai_status}")
    
    def _update_button_states(self, has_selection: bool):
        """Update button states based on selection."""
        state = 'normal' if has_selection else 'disabled'
        UIHelpers.safe_configure(self.remove_button, state=state)
        UIHelpers.safe_configure(self.refresh_button, state=state)


class UIManager:
    """Manages UI creation and theming."""
    
    def __init__(self, root: tk.Tk, config_manager: ConfigManager):
        self.root = root
        self.config_manager = config_manager
        
        # UI Components
        self.project_list_view = None
        self.status_label = None
        self.add_button = None
        self.remove_button = None
        self.refresh_button = None
        self.settings_button = None
    
    def setup_ui(self):
        """Setup the complete user interface."""
        self._configure_window()
        self._apply_theme()
        self._create_layout()
        return (self.project_list_view, self.status_label, self.add_button, 
                self.remove_button, self.refresh_button, self.settings_button)
    
    def _configure_window(self):
        """Configure main window properties."""
        self.root.title(f"{AppConstants.APP_NAME} - AI-Enhanced Code Repository Tracker v{AppConstants.VERSION}")
        self.root.geometry(AppConstants.WINDOW_SIZE)
    
    def _apply_theme(self):
        """Apply dark theme to the application."""
        self.root.configure(bg=Theme.COLORS['bg'])
        
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure styles
        style.configure('TFrame', background=Theme.COLORS['bg'])
        style.configure('TLabel', background=Theme.COLORS['bg'], foreground=Theme.COLORS['fg'])
        style.configure('TButton', background=Theme.COLORS['button_bg'], foreground=Theme.COLORS['button_fg'])
        style.configure('TLabelFrame', background=Theme.COLORS['bg'], foreground=Theme.COLORS['fg'])
        style.configure('TLabelFrame.Label', background=Theme.COLORS['bg'], foreground=Theme.COLORS['fg'])
        style.configure('TCheckbutton', background=Theme.COLORS['bg'], foreground=Theme.COLORS['fg'])
        style.configure('TEntry', fieldbackground=Theme.COLORS['entry_bg'], foreground=Theme.COLORS['entry_fg'])
        
        # Button hover effects
        style.map('TButton',
                 background=[('active', '#505050'), ('pressed', '#606060')])
        
        # Scrollbar styling
        style.configure('Vertical.TScrollbar', 
                       background=Theme.COLORS['button_bg'],
                       troughcolor=Theme.COLORS['bg'],
                       arrowcolor=Theme.COLORS['fg'])
    
    def _create_layout(self):
        """Create the main UI layout."""
        # Main frame
        main_frame = ttk.Frame(self.root, padding=str(AppConstants.CARD_PADDING))
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title with AI indicator
        title_text = f"{AppConstants.APP_NAME} - AI-Enhanced Repository Tracker v{AppConstants.VERSION}"
        if AGNO_AVAILABLE:
            title_text += " 🤖"
        
        title_label = ttk.Label(
            main_frame,
            text=title_text,
            font=('Arial', 16, 'bold')
        )
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # Control buttons
        self._create_control_buttons(main_frame)
        
        # Project list
        self.project_list_view = ProjectListView(main_frame)
        self.project_list_view.create()
        self.project_list_view.widget.grid(
            row=2, column=0, columnspan=2,
            sticky=(tk.W, tk.E, tk.N, tk.S),
            pady=(0, AppConstants.BUTTON_SPACING)
        )
        
        # Status bar
        ai_available = AGNO_AVAILABLE and os.getenv('GEMINI_API_KEY')
        initial_status = "Ready - AI analysis available!" if ai_available else "Ready - Enable AI in settings for code insights"
        self.status_label = ttk.Label(main_frame, text=initial_status)
        self.status_label.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)
    
    def _create_control_buttons(self, parent):
        """Create control button panel."""
        button_frame = ttk.Frame(parent)
        button_frame.grid(row=1, column=0, columnspan=2, pady=(0, 20))
        
        # Add folder button
        self.add_button = ttk.Button(
            button_frame,
            text="Add Folder"
        )
        self.add_button.pack(side=tk.LEFT, padx=(0, AppConstants.BUTTON_SPACING))
        
        # Remove folder button (initially disabled)
        self.remove_button = ttk.Button(
            button_frame,
            text="Remove Selected",
            state='disabled'
        )
        self.remove_button.pack(side=tk.LEFT, padx=(0, AppConstants.BUTTON_SPACING))
        
        # Refresh button (initially disabled)
        self.refresh_button = ttk.Button(
            button_frame,
            text="Refresh Selected",
            state='disabled'
        )
        self.refresh_button.pack(side=tk.LEFT, padx=(0, AppConstants.BUTTON_SPACING))
        
        # Settings button
        self.settings_button = ttk.Button(
            button_frame,
            text="⚙️ Settings"
        )
        self.settings_button.pack(side=tk.LEFT)
        
        # AI status and config info
        info_frame = ttk.Frame(button_frame)
        info_frame.pack(side=tk.RIGHT, padx=(AppConstants.BUTTON_SPACING, 0))
        
        # AI status
        ai_key_available = bool(os.getenv('GEMINI_API_KEY'))
        if AGNO_AVAILABLE and ai_key_available:
            ai_status = "✅ AI Ready"
            ai_color = Theme.COLORS['ai_accent']
        elif AGNO_AVAILABLE:
            ai_status = "⚠️ AI Available (No API Key)"
            ai_color = Theme.COLORS['muted_fg']
        else:
            ai_status = "❌ AI Unavailable"
            ai_color = Theme.COLORS['muted_fg']
            
        ai_info = ttk.Label(
            info_frame,
            text=ai_status,
            font=('Arial', 8),
            foreground=ai_color
        )
        ai_info.pack(side=tk.TOP, anchor='e')
        
        # Config path
        config_path = str(self.config_manager.config_dir).replace(str(Path.home()), "~")
        config_info = ttk.Label(
            info_frame,
            text=f"Config: {config_path}",
            font=('Arial', 8),
            foreground=Theme.COLORS['muted_fg']
        )
        config_info.pack(side=tk.TOP, anchor='e')


# ============================================================================
# MAIN APPLICATION
# ============================================================================

class RepomapApplication:
    """Main application class with AI-enhanced code analysis."""
    
    def __init__(self):
        self._setup_logging()
        logging.info("Initializing Enhanced Repomap application...")
        
        # Core components
        self.root = tk.Tk()
        self.message_queue = queue.Queue(maxsize=1000)
        self.config_manager = ConfigManager()
        
        # Initialize AI components
        self.code_analyzer = self._initialize_ai()
        self.project_tracker = ProjectTracker(self.config_manager, self.message_queue, self.code_analyzer)
        
        # UI and Controllers
        self.ui_manager = UIManager(self.root, self.config_manager)
        self.status_updater = None
        self.message_handler = None
        self.event_controller = None
        
        # State
        self.running = True
        
        self._initialize_ui()
        self._setup_event_handlers()
        
        # Load saved projects
        logging.info("Loading saved projects...")
        self.project_tracker.load_saved_projects()
        
        logging.info("Application initialization complete")
    
    def _setup_logging(self):
        """Setup application logging."""
        log_level = logging.DEBUG if not os.environ.get('PRODUCTION') else logging.INFO
        
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler()]
        )
    
    def _initialize_ai(self) -> Optional[CodeAnalyzer]:
        """Initialize AI code analyzer."""
        if not AGNO_AVAILABLE:
            logging.warning("Agno not available - AI features disabled")
            return None
        
        # Load config to get API key
        config = self.config_manager.load_config()
        logging.info(f"Loaded config: AI enabled = {config.ai_analysis_enabled}, API key present = {bool(config.google_api_key)}")
        
        # Check if AI is enabled and API key is available
        if config.ai_analysis_enabled and config.google_api_key:
            os.environ['GEMINI_API_KEY'] = config.google_api_key
            analyzer = CodeAnalyzer(config.google_api_key)
            if analyzer.is_available():
                logging.info("AI code analyzer initialized successfully")
                return analyzer
            else:
                logging.warning("AI code analyzer initialization failed")
        else:
            # Check for API key in environment even if not in config
            env_key = os.getenv('GEMINI_API_KEY')
            if env_key:
                logging.info("Found API key in environment, initializing AI analyzer")
                analyzer = CodeAnalyzer(env_key)
                if analyzer.is_available():
                    # Update config to reflect that AI is available
                    config.google_api_key = env_key
                    config.ai_analysis_enabled = True
                    self.config_manager.save_config(config)
                    logging.info("AI code analyzer initialized from environment key")
                    return analyzer
        
        logging.info("AI code analyzer not initialized")
        return None
    
    def _initialize_ui(self):
        """Initialize the user interface."""
        (self.project_list_view, self.status_label, self.add_button, 
         self.remove_button, self.refresh_button, self.settings_button) = self.ui_manager.setup_ui()
    
    def _setup_event_handlers(self):
        """Setup event handlers and controllers."""
        # Create status updater
        self.status_updater = StatusUpdater(self.status_label)
        
        # Create controllers
        self.event_controller = EventController(
            self.project_tracker, 
            self.project_list_view, 
            self.status_updater,
            self.add_button,
            self.remove_button,
            self.refresh_button,
            self.config_manager
        )
        
        self.message_handler = MessageHandler(
            self.message_queue,
            self.project_list_view,
            self.status_updater,
            self.project_tracker
        )
        
        # Connect button events
        self.add_button.configure(command=self.event_controller.add_folder)
        self.remove_button.configure(command=self.event_controller.remove_folder)
        self.refresh_button.configure(command=self.event_controller.refresh_folder)
        self.settings_button.configure(command=lambda: self.event_controller.show_settings(self.root))
        
        # Setup callbacks
        self.project_list_view.set_selection_callback(self.event_controller.on_project_selected)
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        # Start message processing
        self.message_handler.start_processing(self.root)
    
    @handle_errors("application shutdown")
    def _on_closing(self):
        """Handle application closing."""
        self.running = False
        self.message_handler.stop_processing()
        
        # Show progress dialog for cleanup
        progress_window = tk.Toplevel(self.root)
        progress_window.title("Shutting down...")
        progress_window.geometry("300x100")
        progress_window.transient(self.root)
        progress_window.grab_set()
        
        ttk.Label(progress_window, text="Cleaning up resources...").pack(pady=20)
        progress_bar = ttk.Progressbar(progress_window, mode='indeterminate')
        progress_bar.pack(pady=AppConstants.BUTTON_SPACING, padx=20, fill='x')
        progress_bar.start()
        
        # Update display
        progress_window.update()
        
        # Cleanup in background
        def cleanup_and_exit():
            try:
                self.project_tracker.cleanup()
            finally:
                self.root.after(0, self.root.destroy)
        
        threading.Thread(target=cleanup_and_exit, daemon=True).start()
        
        # Force exit after timeout
        self.root.after(AppConstants.SHUTDOWN_TIMEOUT_S * 1000, lambda: self.root.destroy())
    
    def run(self):
        """Run the application."""
        try:
            logging.info(f"Starting {AppConstants.APP_NAME} v{AppConstants.VERSION}")
            if self.code_analyzer and self.code_analyzer.is_available():
                logging.info("AI-powered code analysis is available")
            else:
                logging.info("Running without AI analysis")
            self.root.mainloop()
        except Exception as e:
            logging.error(f"Application error: {e}")
            raise
        finally:
            logging.info("Application shutdown complete")


# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    """Application entry point."""
    try:
        # Check for dependencies
        if not AGNO_AVAILABLE:
            print("Warning: Agno framework not found.")
            print("AI-powered code analysis will be disabled.")
            print("To enable AI features, install with:")
            print("  pip install agno google-generativeai")
            print()
        
        app = RepomapApplication()
        app.run()
    except KeyboardInterrupt:
        logging.info("Application interrupted by user")
    except Exception as e:
        logging.error(f"Fatal application error: {e}")
        raise


if __name__ == "__main__":
    main()
