"""Virtual environment management for protocol analysis."""

import subprocess
import sys
from pathlib import Path

from analyze.env_config import EnvironmentConfig


class VenvManager:
    """Manage virtual environments for different Opentrons versions."""

    def __init__(self, base_dir: Path = Path(".venvs")):
        """Initialize the venv manager.

        Args:
            base_dir: Base directory for storing virtual environments
        """
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def ensure_venv_exists(self, config: EnvironmentConfig) -> Path:
        """Ensure a virtual environment exists for the given configuration.

        Args:
            config: Environment configuration

        Returns:
            Path to the virtual environment's python executable

        Raises:
            RuntimeError: If venv creation or package installation fails
        """
        venv_path = self.base_dir / config.name

        if venv_path.exists():
            python_path = venv_path / "bin" / "python"
            if python_path.exists():
                print(f"Virtual environment already exists: {venv_path}")
                return python_path

        print(f"Creating virtual environment: {venv_path}")
        self._create_venv(venv_path, config.python_version)

        python_path = venv_path / "bin" / "python"
        print(f"Installing packages: {config.install_spec}")
        self._install_packages(python_path, config.install_spec)

        return python_path

    def _create_venv(self, venv_path: Path, python_version: str) -> None:
        """Create a virtual environment.

        Args:
            venv_path: Path where the venv should be created
            python_version: Python version requirement (e.g., "3.10")

        Raises:
            RuntimeError: If venv creation fails
        """
        try:
            # Use the current Python interpreter
            subprocess.run(
                [sys.executable, "-m", "venv", str(venv_path)],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Failed to create virtual environment: {e.stderr}"
            ) from e

    def _install_packages(self, python_path: Path, install_spec: str) -> None:
        """Install packages into a virtual environment.

        Args:
            python_path: Path to the venv's python executable
            install_spec: Package specification for pip install

        Raises:
            RuntimeError: If package installation fails
        """
        try:
            # Upgrade pip first
            subprocess.run(
                [str(python_path), "-m", "pip", "install", "--upgrade", "pip"],
                check=True,
                capture_output=True,
                text=True,
            )

            # Install the specified packages
            subprocess.run(
                [str(python_path), "-m", "pip", "install", install_spec],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to install packages: {e.stderr}") from e

    def get_python_path(self, config: EnvironmentConfig) -> Path:
        """Get the Python executable path for a configuration.

        Args:
            config: Environment configuration

        Returns:
            Path to the python executable
        """
        return self.base_dir / config.name / "bin" / "python"
