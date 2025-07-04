# Default gitignore patterns for when no .gitignore exists
DEFAULT_GITIGNORE_PATTERNS = [
    # Repomap generated files
    "RepoMap.md",
    # Dependencies
    "node_modules/",
    "venv/",
    "env/",
    ".venv/",
    ".env/",
    "__pycache__/",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    ".Python",
    "pip-log.txt",
    "pip-delete-this-directory.txt",
    ".tox/",
    ".coverage",
    ".pytest_cache/",
    
    # Build outputs
    "build/",
    "dist/",
    "*.egg-info/",
    "*.egg",
    "target/",
    "out/",
    "bin/",
    "obj/",
    "Debug/",
    "Release/",
    "x64/",
    "x86/",
    
    # IDE and editor files
    ".vscode/",
    ".idea/",
    "*.swp",
    "*.swo",
    "*~",
    ".DS_Store",
    "Thumbs.db",
    "*.sublime-project",
    "*.sublime-workspace",
    
    # Logs
    "*.log",
    "logs/",
    "log/",
    
    # Temporary files
    "*.tmp",
    "*.temp",
    ".tmp/",
    ".temp/",
    
    # OS generated files
    ".DS_Store?",
    "._*",
    ".Spotlight-V100",
    ".Trashes",
    "ehthumbs.db",
    
    # Package manager files
    "package-lock.json",
    "yarn.lock",
    "composer.lock",
    "Pipfile.lock",
    "poetry.lock",
    
    # Environment files
    ".env.local",
    ".env.development.local",
    ".env.test.local",
    ".env.production.local",
    
    # Database files
    "*.db",
    "*.sqlite",
    "*.sqlite3",
    
    # Backup files
    "*.bak",
    "*.backup",
    "*~",
    
    # Compiled files
    "*.com",
    "*.class",
    "*.dll",
    "*.exe",
    "*.o",
    "*.so",
    "*.dylib",
    
    # Archives
    "*.7z",
    "*.dmg",
    "*.gz",
    "*.iso",
    "*.jar",
    "*.rar",
    "*.tar",
    "*.zip",
    
    # Media files (optional - uncomment if you want to ignore these)
    # "*.mp3",
    # "*.mp4",
    # "*.avi",
    # "*.mov",
    # "*.wmv",
    # "*.flv",
    # "*.webm",
    # "*.jpg",
    # "*.jpeg",
    # "*.png",
    # "*.gif",
    # "*.bmp",
    # "*.tiff",
    # "*.svg",
    
    # Documentation builds
    "docs/_build/",
    "site/",
    "_site/",
    
    # Cache directories
    ".cache/",
    "cache/",
    ".parcel-cache/",
    ".next/",
    ".nuxt/",
    
    # Coverage reports
    "coverage/",
    ".nyc_output/",
    "htmlcov/",
    
    # Jupyter Notebook checkpoints
    ".ipynb_checkpoints",
    
    # Local configuration files
    ".envrc",
    ".direnv/",
    
    # Terraform
    "*.tfstate",
    "*.tfstate.*",
    ".terraform/",
    
    # Docker
    ".dockerignore",
    
    # Kubernetes
    "*.kubeconfig",
    
    # AWS
    ".aws/",
    
    # Google Cloud
    ".gcloud/",
    
    # Azure
    ".azure/",
]

# AI Analysis Configuration
AI_MODEL_NAME = "gemini-2.5-pro"
AI_MAX_WORKERS = 5

SUPPORTED_CODE_EXTENSIONS = {
    '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.h', '.hpp',
    '.cs', '.php', '.rb', '.go', '.rs', '.swift', '.kt', '.scala', '.clj',
    '.hs', '.ml', '.fs', '.vb', '.sql', '.r', '.m', '.mm', '.pl', '.sh',
    '.bash', '.zsh', '.fish', '.ps1', '.bat', '.cmd', '.lua', '.vim',
    '.el', '.scm', '.rkt', '.dart', '.nim', '.zig', '.v', '.sv', '.vhd'
}

AI_PROMPT_TEMPLATE = """
Analyze this code file and return ONLY a valid JSON object with the following structure:

{{
    "classes": [
        {{
            "name": "ClassName",
            "description": "brief description of what this class does",
            "methods": [
                {{
                    "name": "method_name",
                    "signature": "method_name(self, param1: type, param2: type) -> return_type",
                    "description": "what this method does"
                }}
            ],
            "class_variables": [
                {{
                    "name": "variable_name",
                    "type": "type",
                    "description": "what this class variable stores"
                }}
            ]
        }}
    ],
    "standalone_functions": [
        {{
            "name": "function_name",
            "signature": "function_name(param1: type, param2: type) -> return_type",
            "description": "what this standalone function does"
        }}
    ],
    "module_constants": [
        {{"name": "CONSTANT_NAME", "value": "value", "description": "what this constant represents"}}
    ],
    "module_variables": [
        {{"name": "variable_name", "type": "type", "description": "what this module-level variable stores"}}
    ]
}}

Rules:
- Return ONLY the JSON object, no other text
- Group methods under their respective classes
- Put functions that are NOT inside classes in "standalone_functions"
- Include complete signatures with parameter types and return types
- For class methods, include 'self' in the signature
- Focus on meaningful descriptions, not obvious ones
- For class_variables, include important instance/class variables
- For module_constants/variables, only include important ones
- If a category is empty, use an empty array []
- Keep descriptions concise but informative
- Don't describe obvious parameters like 'self'

IMPORTANT: For configuration files, data files, or files with simple data structures:
- If the file contains lists, dictionaries, or other data structures, describe their purpose
- For configuration constants, explain what they configure or control
- For data files, describe what kind of data they contain
- Even simple files should have meaningful descriptions of their content and purpose
- For files that only contain constants or data structures (no classes/functions), put them in module_constants
- Examples: DEFAULT_GITIGNORE_PATTERNS should be documented as a module_constant explaining it's a list of gitignore patterns
- Configuration constants should be documented with their purpose and what they control

File: {file_name}
Content:
{file_content}
""" 