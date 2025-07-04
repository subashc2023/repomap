"""
Configuration, constants, and data models for Repomap application.
"""

import os
import json
import time
import platform
import logging
import functools
import queue
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, asdict, field
from enum import Enum
from pydantic import BaseModel, Field


# ============================================================================
# CONSTANTS AND CONFIGURATION
# ============================================================================

class AppConstants:
    """Centralized application constants."""
    # App Info
    APP_NAME = "Repomap"
    VERSION = "3.0.1"
    CONFIG_FILE = "config.json"
    
    # Files
    GENERATED_FILES = {'repomap.md', '.ignore'}
    
    # Performance Limits
    MAX_FILE_SIZE_MB = 10
    MAX_DIRECTORY_DEPTH = 20
    MAX_FILES_PER_PROJECT = 10000
    
    # AI Analysis Limits
    MAX_ANALYZE_FILE_SIZE_MB = 1  # Smaller limit for AI analysis
    MAX_FUNCTIONS_PER_FILE = 50
    AI_ANALYSIS_TIMEOUT = 30  # seconds
    
    # Timing
    DEBOUNCE_DELAY_MS = 1000
    UPDATE_INTERVAL_MS = 100
    QUEUE_CHECK_INTERVAL_MS = 100
    SHUTDOWN_TIMEOUT_S = 5
    OBSERVER_TIMEOUT_S = 2
    
    # UI Layout
    WINDOW_SIZE = "900x700"
    CARD_PADDING = 10
    BUTTON_SPACING = 10
    LIST_HEIGHT = 400
    STATUS_CIRCLE_SIZE = 16
    
    # Processing
    MAX_MESSAGES_PER_CYCLE = 50
    PROGRESS_UPDATE_INTERVAL = 100


class Theme:
    """UI theme configuration."""
    COLORS = {
        'bg': '#2b2b2b',
        'fg': '#ffffff',
        'card_bg': '#3c3c3c',
        'card_border': '#555555',
        'selected_border': '#0078d4',
        'button_bg': '#404040',
        'button_fg': '#ffffff',
        'entry_bg': '#404040',
        'entry_fg': '#ffffff',
        'selected_bg': '#505050',
        'selected_fg': '#ffffff',
        'muted_fg': '#888888',
        'ai_accent': '#00d4aa'
    }
    
    STATUS_COLORS = {
        'ready': '#00ff41',
        'processing': '#ffeb3b',
        'analyzing': '#00d4aa',
        'error': '#ff5252'
    }


class LanguagePatterns:
    """Programming language and framework detection patterns."""
    LANGUAGES = {
        'Python': ['.py', '.pyw', '.pyi'],
        'JavaScript': ['.js', '.jsx', '.mjs'],
        'TypeScript': ['.ts', '.tsx'],
        'Java': ['.java'],
        'C++': ['.cpp', '.cc', '.cxx', '.hpp', '.h'],
        'C': ['.c', '.h'],
        'C#': ['.cs'],
        'Ruby': ['.rb'],
        'PHP': ['.php'],
        'Go': ['.go'],
        'Rust': ['.rs'],
        'Swift': ['.swift'],
        'Kotlin': ['.kt', '.kts'],
        'HTML': ['.html', '.htm'],
        'CSS': ['.css', '.scss', '.sass', '.less'],
        'Shell': ['.sh', '.bash', '.zsh'],
        'PowerShell': ['.ps1'],
        'YAML': ['.yml', '.yaml'],
        'JSON': ['.json'],
        'XML': ['.xml'],
        'Markdown': ['.md', '.markdown']
    }
    
    # Languages that support AI analysis
    ANALYZABLE_LANGUAGES = {
        'Python': ['.py', '.pyw'],
        'JavaScript': ['.js', '.jsx', '.mjs'],
        'TypeScript': ['.ts', '.tsx'],
        'Java': ['.java'],
        'C++': ['.cpp', '.cc', '.cxx'],
        'C': ['.c'],
        'C#': ['.cs'],
        'Ruby': ['.rb'],
        'PHP': ['.php'],
        'Go': ['.go'],
        'Rust': ['.rs'],
        'Swift': ['.swift'],
        'Kotlin': ['.kt', '.kts']
    }
    
    FRAMEWORKS = {
        'React': ['package.json'],
        'Vue': ['vue.config.js', 'package.json'],
        'Angular': ['angular.json', 'package.json'],
        'Django': ['manage.py', 'settings.py'],
        'Flask': ['app.py', 'application.py'],
        'FastAPI': ['main.py', 'app.py'],
        'Spring': ['pom.xml', 'build.gradle'],
        'Express': ['package.json'],
        'Laravel': ['composer.json', 'artisan'],
        'Rails': ['Gemfile', 'config.ru'],
        'Next.js': ['next.config.js', 'package.json'],
        'Nuxt': ['nuxt.config.js', 'package.json']
    }


# ============================================================================
# DATA MODELS
# ============================================================================

class ProjectStatus(Enum):
    """Project processing status."""
    READY = "ready"
    PROCESSING = "processing"
    ANALYZING = "analyzing"
    ERROR = "error"


@dataclass
class ProjectInfo:
    """Project information data class."""
    name: str
    path: str
    status: ProjectStatus = ProjectStatus.PROCESSING
    total_files: int = 0
    total_lines: int = 0
    analyzed_files: int = 0
    total_functions: int = 0
    primary_language: str = "Unknown"
    frameworks: List[str] = field(default_factory=list)
    error_message: str = ""
    last_updated: float = field(default_factory=time.time)
    ai_analysis_enabled: bool = False


@dataclass
class FileNode:
    """File tree node data class."""
    name: str
    type: str  # 'file' or 'directory'
    lines: int = 0
    analyzed: bool = False
    functions_count: int = 0
    children: Dict[str, 'FileNode'] = field(default_factory=dict)


@dataclass
class AppConfig:
    """Application configuration."""
    tracked_folders: List[str] = field(default_factory=list)
    window_geometry: str = AppConstants.WINDOW_SIZE
    version: str = AppConstants.VERSION
    ai_analysis_enabled: bool = False
    google_api_key: str = ""
    
    def save(self, path: Path):
        """Save configuration to file."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(asdict(self), f, indent=2)
            logging.info(f"Configuration saved to {path}")
        except Exception as e:
            logging.error(f"Could not save config: {e}")
    
    @classmethod
    def load(cls, path: Path):
        """Load configuration from file."""
        try:
            if not path.exists():
                logging.info("No config file found, creating default")
                return cls()
            
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                config = cls(**data)
                logging.info(f"Configuration loaded from {path}")
                return config
        except Exception as e:
            logging.error(f"Could not load config: {e}")
            return cls()


# ============================================================================
# AI ANALYSIS DATA MODELS
# ============================================================================

@dataclass
class FunctionInfo:
    """Information about a function extracted by AI."""
    name: str
    parameters: List[str]
    description: str
    return_type: Optional[str] = None
    line_number: Optional[int] = None
    is_method: bool = False
    class_name: Optional[str] = None


@dataclass
class ClassInfo:
    """Information about a class extracted by AI."""
    name: str
    description: str
    methods: List[FunctionInfo] = field(default_factory=list)
    line_number: Optional[int] = None


@dataclass
class FileAnalysis:
    """Complete analysis of a code file."""
    file_path: str
    language: str
    functions: List[FunctionInfo] = field(default_factory=list)
    classes: List[ClassInfo] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    description: str = ""
    complexity_score: Optional[int] = None
    analyzed_at: float = field(default_factory=time.time)


# Pydantic models for structured AI output
class FunctionInfoModel(BaseModel):
    """Pydantic model for function information."""
    name: str = Field(description="The name of the function")
    parameters: List[str] = Field(description="List of parameter names and types")
    description: str = Field(description="Brief description of what the function does")
    return_type: Optional[str] = Field(description="Return type if clearly specified")
    line_number: Optional[int] = Field(description="Line number where function starts")
    is_method: bool = Field(default=False, description="True if this is a class method")
    class_name: Optional[str] = Field(description="Class name if this is a method")


class ClassInfoModel(BaseModel):
    """Pydantic model for class information."""
    name: str = Field(description="The name of the class")
    description: str = Field(description="Brief description of the class purpose")
    line_number: Optional[int] = Field(description="Line number where class starts")


class CodeAnalysisModel(BaseModel):
    """Pydantic model for complete code analysis."""
    functions: List[FunctionInfoModel] = Field(description="List of functions found in the code")
    classes: List[ClassInfoModel] = Field(description="List of classes found in the code")
    imports: List[str] = Field(description="List of import statements")
    description: str = Field(description="Brief description of the file's purpose")
    complexity_score: Optional[int] = Field(description="Complexity score from 1-10")


# ============================================================================
# MESSAGE TYPES
# ============================================================================

@dataclass
class UIMessage:
    """Base class for thread-safe UI messages."""
    message_type: str = ""


@dataclass
class ProjectUpdateMessage(UIMessage):
    """Message to update project information."""
    project_path: str = ""
    project_info: ProjectInfo = None
    message_type: str = "project_update"


@dataclass
class StatusMessage(UIMessage):
    """Message to update status text."""
    status_text: str = ""
    message_type: str = "status_update"


@dataclass
class ProgressMessage(UIMessage):
    """Message to update progress."""
    project_path: str = ""
    progress_text: str = ""
    percent: Optional[int] = None
    message_type: str = "progress_update"


@dataclass
class AnalysisMessage(UIMessage):
    """Message for AI analysis updates."""
    project_path: str = ""
    file_path: str = ""
    analysis: FileAnalysis = None
    message_type: str = "analysis_update"


# ============================================================================
# UTILITY DECORATORS AND HELPERS
# ============================================================================

def handle_errors(operation_name: str, default_return=None, log_level=logging.ERROR):
    """Decorator for consistent error handling."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logging.log(log_level, f"Error in {operation_name}: {e}")
                return default_return
        return wrapper
    return decorator


def safe_queue_put(queue_obj: queue.Queue, item, timeout=0.1):
    """Safely put item in queue without blocking."""
    try:
        queue_obj.put_nowait(item)
        return True
    except queue.Full:
        logging.warning(f"Queue full, dropping message: {type(item).__name__}")
        return False


# ============================================================================
# CONFIGURATION MANAGER
# ============================================================================

class ConfigManager:
    """Handles application configuration persistence."""
    
    def __init__(self):
        self.config_dir = self._get_app_data_dir()
        self.config_file = self.config_dir / AppConstants.CONFIG_FILE
        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_app_data_dir(self) -> Path:
        """Get platform-appropriate application data directory."""
        system = platform.system()
        
        if system == "Windows":
            appdata = os.environ.get('LOCALAPPDATA') or os.environ.get('APPDATA', 
                str(Path.home() / 'AppData' / 'Roaming'))
            return Path(appdata) / AppConstants.APP_NAME
        elif system == "Darwin":  # macOS
            return Path.home() / 'Library' / 'Application Support' / AppConstants.APP_NAME
        else:  # Linux and other Unix-like systems
            xdg_data = os.environ.get('XDG_DATA_HOME')
            if xdg_data:
                return Path(xdg_data) / AppConstants.APP_NAME.lower()
            return Path.home() / '.local' / 'share' / AppConstants.APP_NAME.lower()
    
    @handle_errors("loading config")
    def load_config(self) -> AppConfig:
        """Load configuration data."""
        return AppConfig.load(self.config_file)
    
    @handle_errors("saving config")
    def save_config(self, config: AppConfig):
        """Save configuration data."""
        config.save(self.config_file) 