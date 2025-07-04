AI_MODEL_NAME = "gemini-2.5-flash"

# Default gitignore patterns for when no .gitignore exists
DEFAULT_GITIGNORE_PATTERNS = [
    # Repomap generated files
    "repomap.md",
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
AI_MAX_WORKERS = 5

SUPPORTED_CODE_EXTENSIONS = {
    '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.h', '.hpp',
    '.cs', '.php', '.rb', '.go', '.rs', '.swift', '.kt', '.scala', '.clj',
    '.hs', '.ml', '.fs', '.vb', '.sql', '.r', '.m', '.mm', '.pl', '.sh',
    '.bash', '.zsh', '.fish', '.ps1', '.bat', '.cmd', '.lua', '.vim',
    '.el', '.scm', '.rkt', '.dart', '.nim', '.zig', '.v', '.sv', '.vhd'
}

AI_PROMPT_TEMPLATE = """
Analyze the code for `{file_name}` and return ONLY a valid JSON object summarizing its structure.

**JSON Structure:**
{{
    "classes": [
        {{
            "name": "ClassName",
            "description": "A brief, one-sentence summary of the class.",
            "methods": [
                {{"name": "method_name", "signature": "full_signature() -> type", "description": "..."}}
            ],
            "class_variables": [
                {{"name": "variable_name", "type": "...", "description": "..."}}
            ]
        }}
    ],
    "standalone_functions": [
        {{"name": "function_name", "signature": "...", "description": "..."}}
    ],
    "module_constants": [
        {{"name": "CONSTANT_NAME", "value": "...", "description": "..."}}
    ],
    "module_variables": [
        {{"name": "variable_name", "type": "...", "description": "..."}}
    ]
}}

**Key Instructions:**
1.  **Signatures**: Provide the full function/method signature.
2.  **Descriptions**: Keep them concise and meaningful.
3.  **Summarize Large Values**: For variables/constants with large values (e.g., long lists, multi-line strings), OMIT the `value` field and summarize the content in the `description`.
4.  **Data/Config Files**: For non-code files, describe the data's purpose under `module_constants` or `module_variables`.
5.  **Empty Categories**: If a category has no items, use an empty array `[]`.

**File Content:**
```
{file_content}
```
""" 