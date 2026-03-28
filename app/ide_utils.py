import os
import sys

def is_running_under_ide():
    """
    Detect if the code is running under an IDE.

    Returns:
        bool: True if running under an IDE, False otherwise
    """
    # Check for IDE-specific environment variables
    ide_env_vars = ['PYCHARM_HOSTED', 'VSCODE_PID', 'SPYDER_ARGS', 'JUPYTER_CONFIG_DIR']
    for var in ide_env_vars:
        if var in os.environ:
            return True

    # Check for IDE-specific modules
    ide_modules = ['_pydev_bundle', 'pydevd', 'debugpy', 'spyder', 'IPython']
    for module in ide_modules:
        if module in sys.modules:
            return True

    return False
