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