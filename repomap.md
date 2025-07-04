# repomap

## Project Context
- **Language**: Python
- **Framework**: None detected
- **Total Files**: 7
- **Total Lines**: 3581
- **AI Analysis**: ✅ Enabled
- **Analyzed Files**: 2
- **Total Functions**: 55
- **Last Updated**: 2025-07-03 19:46:13

## Ignore Configuration
This project uses a `.ignore` file that contains patterns from the original `.gitignore` plus any additional patterns you want to exclude from repomap analysis.

Edit the `.ignore` file to customize what gets included in your repomap.

## Project Structure
```
repomap/
├── src/
├── config.py (398 lines) (7 functions) 🤖
└── main.py (2340 lines) (48 functions) 🤖
├── .gitignore (11 lines)
├── .python-version (1 lines)
├── pyproject.toml (13 lines)
├── README.md (0 lines)
└── uv.lock (818 lines)
```

## File Type Distribution
- **.py**: 2 files (28.6%)
- **no extension**: 2 files (28.6%)
- **.toml**: 1 files (14.3%)
- **.md**: 1 files (14.3%)
- **.lock**: 1 files (14.3%)

## 🤖 AI Code Analysis

### Function Overview

#### src\config.py
*Configuration, constants, and data models for Repomap application.*

**save(path, Path)** (line 186)
- Save configuration to file.

**load(path, Path) → AppConfig** (line 196)
- Load configuration from file.

**handle_errors(operation_name, str, default_return, log_level, logging.ERROR) → wrapper** (line 293)
- Decorator for consistent error handling.

**safe_queue_put(queue_obj, queue.Queue, item, timeout, 0.1) → bool** (line 307)
- Safely put item in queue without blocking.

**_get_app_data_dir() → Path** (line 322)
- Get platform-appropriate application data directory.

**load_config() → AppConfig** (line 330)
- Load configuration data.

**save_config(config, AppConfig)** (line 335)
- Save configuration data.


#### src\main.py
*This Python code implements a code repository tracker with AI-powered code analysis. It uses the Agno framework and Google Gemini for intelligent function extraction. The code is structured into several classes, including UIHelpers for UI operations, Debouncer for debouncing rapid function calls, FileOperations for file operations, IgnorePatternMatcher for pattern matching, CodeAnalyzer for AI-powered code analysis, ProjectAnalyzer for project-level analysis, ProjectWatcher for file system monitoring, ProjectTracker for project management, and ProjectCard for UI representation of projects.*

**handle_errors(description, default_return)** (line 36)
- Decorator to handle exceptions gracefully.

**safe_queue_put(queue, item)** (line 37)
- Safely put an item into a queue.

**configure_themed_widget(widget, widget_type)** (line 47)
- Apply consistent theming to widgets.

**safe_configure(widget, kwargs)** (line 66)
- Safely configure widget if it exists.

**safe_destroy(widget)** (line 78)
- Safely destroy widget if it exists.

**bind_click_events(widgets, callback)** (line 89)
- Bind click events to multiple widgets.

**create_status_indicator(parent, status, size)** (line 102)
- Create a status indicator circle.

**debounce(key, func, args, kwargs)** (line 129)
- Debounce a function call by key.

**cancel_all()** (line 146)
- Cancel all pending debounced calls.

**count_lines(file_path) → int** (line 157)
- Safe line counting with size limits.

**read_file_content(file_path) → str** (line 172)
- Safely read file content for AI analysis.

**create_ignore_file(project_path)** (line 187)
- Create comprehensive .ignore file with improved Python support.

**_load_patterns(ignore_file_path)** (line 270)
- Load patterns from ignore file.

**is_ignored(file_path, base_path) → bool** (line 293)
- Check if a path should be ignored with improved logic.

**_match_pattern(path, pattern, is_directory) → bool** (line 339)
- Match a path against a gitignore-style pattern with improved support.

**_initialize_agent()** (line 400)
- Initialize the Agno agent with Gemini model.

**is_available() → bool** (line 420)
- Check if AI analysis is available.

**get_file_language(file_path) → Optional[str]** (line 424)
- Determine if file can be analyzed and return its language.

**analyze_file(file_path, content) → Optional[FileAnalysis]** (line 433)
- Analyze a code file using AI.

**_ensure_ignore_file()** (line 518)
- Ensure ignore file exists before any analysis.

**analyze() → ProjectInfo** (line 525)
- Perform complete project analysis with AI-powered code analysis.

**_send_progress(message, percent)** (line 550)
- Send progress update to UI thread.

**_perform_ai_analysis()** (line 568)
- Perform AI analysis on code files.

**_collect_analyzable_files(tree, current_path, result)** (line 602)
- Recursively collect files that can be analyzed.

**_scan_directory(directory, relative_path, depth) → Dict[str, FileNode]** (line 617)
- Recursively scan directory structure with safety limits and proper ignore handling.

**_detect_primary_language() → str** (line 684)
- Detect primary programming language.

**_detect_frameworks() → List[str]** (line 691)
- Detect frameworks used in the project.

**_generate_tree_structure(tree, indent, is_last_items) → List[str]** (line 698)
- Generate tree structure representation with proper formatting.

**_generate_documentation(project_info)** (line 736)
- Generate enhanced repomap.md documentation with AI analysis.

**_generate_ai_analysis_section() → str** (line 790)
- Generate the AI analysis section of the documentation.

**on_modified(event)** (line 880)
- Handle file modification events.

**load_saved_projects()** (line 911)
- Load previously saved projects.

**add_project(project_path, save_config) → bool** (line 926)
- Add a new project to track.

**remove_project(project_path, remove_files)** (line 972)
- Remove a project from tracking.

**mark_project_changed(project_path)** (line 1006)
- Mark a project as changed and schedule re-analysis.

**get_tracked_projects() → List[str]** (line 1016)
- Get list of tracked project paths.

**get_project_info(project_path) → Optional[ProjectInfo]** (line 1021)
- Get project information.

**get_all_projects() → Dict[str, ProjectInfo]** (line 1026)
- Get all projects (thread-safe copy).

**_send_project_update(project_path, project_info)** (line 1032)
- Send project update to UI thread.

**_start_monitoring(project_path)** (line 1043)
- Start file system monitoring for a project.

**_analyze_project(project_path)** (line 1052)
- Analyze a project in background thread.

**_save_config()** (line 1064)
- Save current configuration.

**set_code_analyzer(code_analyzer)** (line 1071)
- Set or update the code analyzer.

**cleanup()** (line 1077)
- Clean up resources safely.

**create()** (line 1096)
- Create the project card.

**_create_project_info()** (line 1117)
- Create project information section of the card.

**update(project_info)** (line 1145)
- Update the project card with new information.

**select()** (line 1162)
- Select or deselect the project card.


### Class Overview

#### src\config.py
**AppConstants** (line 40)
- Centralized application constants.

**Theme** (line 81)
- UI theme configuration.

**LanguagePatterns** (line 98)
- Programming language and framework detection patterns.

**ProjectStatus** (line 140)
- Project processing status.

**ProjectInfo** (line 146)
- Project information data class.

**FileNode** (line 160)
- File tree node data class.

**AppConfig** (line 170)
- Application configuration.

**FunctionInfo** (line 209)
- Information about a function extracted by AI.

**ClassInfo** (line 223)
- Information about a class extracted by AI.

**FileAnalysis** (line 232)
- Complete analysis of a code file.

**FunctionInfoModel** (line 243)
- Pydantic model for function information.

**ClassInfoModel** (line 256)
- Pydantic model for class information.

**CodeAnalysisModel** (line 263)
- Pydantic model for complete code analysis.

**UIMessage** (line 275)
- Base class for thread-safe UI messages.

**ProjectUpdateMessage** (line 280)
- Message to update project information.

**StatusMessage** (line 285)
- Message to update status text.

**ProgressMessage** (line 290)
- Message to update progress.

**AnalysisMessage** (line 295)
- Message for AI analysis updates.

**ConfigManager** (line 318)
- Handles application configuration persistence.


#### src\main.py
**UIHelpers** (line 44)
- Utility functions for UI operations.

**Debouncer** (line 123)
- Debounces rapid successive calls.

**FileOperations** (line 153)
- Utility class for safe file operations.

**IgnorePatternMatcher** (line 264)
- Handles file ignore pattern matching with improved gitignore support.

**CodeAnalyzer** (line 394)
- AI-powered code analyzer using Agno and Google Gemini.

**ProjectAnalyzer** (line 499)
- Thread-safe project analyzer with AI-powered code analysis.

**ProjectWatcher** (line 876)
- Watches for file system changes with debouncing.

**ProjectTracker** (line 905)
- Thread-safe project tracker with AI-enhanced analysis.

**ProjectCard** (line 1091)
- Individual project card UI component with AI analysis support.

