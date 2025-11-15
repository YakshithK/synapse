# synapse/agent_loader.py
import ast
import importlib.util
import os
import sys
from typing import Any, Callable, Dict, List, Optional

class AgentLoader:
    """
    Loads user-defined agent Python files with security checks.
    """

    # allowed imports (whitelist)
    ALLOWED_IMPORTS = {
        'json', 'datetime', 'time', 'random', 'math', 're', 'collections',
        'requests', 'beautifulsoup4', 'pandas', 'numpy',
        'typing', 'dataclasses', 'enum'
    }
    
    # Blocked imports (blacklist)
    BLOCKED_IMPORTS = {
        'subprocess', 'sys', 'shutil', 'os', 'fileinput', 'pickle',
        'socket', 'urllib', 'http', 'ftplib', 'smtplib', 'eval', 'exec'
    }
    
    # Dangerous operations to detect
    DANGEROUS_OPERATIONS = {
        'os.system', 'os.popen', 'subprocess', 'eval', 'exec',
        'compile', '__import__', 'open', 'file', 'input', 'raw_input'
    }

    def __init__(self, agent_dir: Optional[str] = None):
        self.agent_dir = agent_dir or os.getcwd()
        self._loaded_agents = {} # cache loaded agents

    def load_agent(self, agent_file: str) -> Dict[str, Any]:
        """
        Load agent from Python file.

        Args: 
            agent_file: Path to agent Python file
        
        Returns:
            Dictionary with:
                - func: Callable agent function
                - metadata: Agent metadata
                - security_report: Security analysis report
        """
        # check cache
        if agent_file in self._loaded_agents:
            return self._loaded_agents[agent_file]

        # resolve file path
        file_path = self._resolve_file_path(agent_file)

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Agent file not found: {file_path}")

        # security analysis
        security_report = self._analyze_security(file_path)

        # load agent function 
        func = self._load_agent_function(file_path)

        # extract metadata
        metadata = self._extract_metadata(file_path, func)

        result = {
            "func": func,
            "metadata": metadata,
            "security_report": security_report,
            "file_path": file_path
        }

        # cache result
        self._loaded_agents[agent_file] = result

        return result

    def _resolve_file_path(self, agent_file: str) -> str:
        """Resolve agent file path."""
        if os.path.isabs(agent_file):
            return agent_file
        
        # Try relative to agent_dir
        path = os.path.join(self.agent_dir, agent_file)
        if os.path.exists(path):
            return path
        
        # Try relative to agent_dir/agents (common structure)
        agents_dir = os.path.join(os.path.dirname(self.agent_dir), "agents")
        path = os.path.join(agents_dir, agent_file)
        if os.path.exists(path):
            return path
        
        # Try relative to current directory
        if os.path.exists(agent_file):
            return agent_file
        
        # If not found, return as-is (will raise FileNotFoundError)
        return agent_file

    def _analyze_security(self, file_path: str) -> Dict[str, Any]:
        """
        Analyze agent file for security issues.

        Returns:
            Dictionary with security analysis report
        """

        with open(file_path, "r") as f:
            source = f.read()

        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            return {
                "safe": False,
                "error": f"Syntax error: {str(e)}",
                "warnings": [],
                "dangerous_ops": [],
                "imports": []
            }

        analyzer = SecurityAnalyzer()
        analyzer.visit(tree)
        return analyzer.get_report()

    def _load_agent_function(self, file_path: str) -> Callable:
        """
        Load agent function from Python file.

        Expected signature: def run(context: dict) -> dict
        """

        # generate unique module name
        module_name = f"agent_{os.path.basename(file_path).replace('.', '_')}"

        # load module
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load agent from {file_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module

        try:
            spec.loader.exec_module(module)
        except Exception as e:
            raise ImportError(f"Error loading agent module {file_path}: {str(e)}")

        # Then check for run function:
        if not hasattr(module, 'run'):
            raise ValueError(f"Agent file {file_path} must export a 'run' function")

        func = getattr(module, 'run')

        # validate function signature
        if not callable(func):
            raise ValueError(f"Agent file {file_path} must export a callable 'run' function")

        return func

    def _extract_metadata(self, file_path: str, func: Callable) -> Dict[str, Any]: 
        """
        Extract metadata from agent file and function.
        """
        metadata = {
            'file_path': file_path,
            'file_name': os.path.basename(file_path),
            'function_name': func.__name__,
            'docstring': func.__doc__ or '',
            'module': func.__module__
        }

        # Try to extract more metadata from docstring
        if func.__doc__:
            # Parse docstring for metadata
            pass
        
        return metadata

class SecurityAnalyzer(ast.NodeVisitor):
    """
    AST visitor to analyze agent code for security issues.
    """

    def __init__(self):
        self.imports = []
        self.dangerous_ops = []
        self.warnings = []
        self.safe = True

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append(alias.name)
            if alias.name in AgentLoader.BLOCKED_IMPORTS:
                self.safe = False
                self.warnings.append(f"Blocked import: {alias.name}")

    def visit_ImportFrom(self, node):
        if node.module:
            self.imports.append(node.module)
            if node.module in AgentLoader.BLOCKED_IMPORTS:
                self.safe = False
                self.warnings.append(f"Blocked import: {node.module}")

    def visit_Call(self, node):
        # check for dangerous function calls
        if isinstance(node.func, ast.Name):
            if node.func.id in ['eval', 'exec', 'compile']:
                self.safe = False
                self.dangerous_ops.append(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            # check for os.system, subprocess, etc.
            if isinstance(node.func.value, ast.Name):
                full_name = f"{node.func.value.id}.{node.func.attr}"
                if full_name in AgentLoader.DANGEROUS_OPERATIONS:
                    self.safe = False
                    self.dangerous_ops.append(full_name)

        self.generic_visit(node)

    def get_report(self) -> Dict[str, Any]:
        """Get security analysis report."""
        return {
            'safe': self.safe,
            'warnings': self.warnings,
            'dangerous_ops': self.dangerous_ops,
            'imports': list(set(self.imports))
        }