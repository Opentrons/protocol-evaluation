"""Virtual environment management for protocol analysis."""

import os
import subprocess
import sys
from pathlib import Path

from evaluate.env_config import EnvironmentConfig


class VenvManager:
    """Manage virtual environments for different Opentrons versions."""

    def __init__(self, base_dir: Path = Path(".venvs")):
        """Initialize the venv manager.

        Args:
            base_dir: Base directory for storing virtual environments
        """
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.base_python = self._detect_base_python()

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
            python_path = self._python_bin(venv_path)
            if python_path.exists():
                print(f"Virtual environment already exists: {venv_path}")
                return python_path

        print(f"Creating virtual environment: {venv_path}")
        self._create_venv(venv_path, config.python_version)

        python_path = self._python_bin(venv_path)
        print("Installing packages: " + ", ".join(config.install_specs))
        self._install_packages(python_path, config.install_specs)

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
            # Use the uv-managed python interpreter when available
            subprocess.run(
                [str(self.base_python), "-m", "venv", str(venv_path)],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Failed to create virtual environment: {e.stderr}"
            ) from e

    def _install_packages(self, python_path: Path, install_specs: list[str]) -> None:
        """Install packages into a virtual environment.

        Args:
            python_path: Path to the venv's python executable
            install_specs: Package specifications for pip install

        Raises:
            RuntimeError: If package installation fails
        """
        current_spec = "--upgrade pip"
        try:
            # Upgrade pip first
            subprocess.run(
                [str(python_path), "-m", "pip", "install", "--upgrade", "pip"],
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )

            # Install the specified packages (with longer timeout for git installs)
            for spec in install_specs:
                current_spec = spec
                subprocess.run(
                    [
                        str(python_path),
                        "-m",
                        "pip",
                        "install",
                        "--timeout=300",
                        spec,
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=600,
                )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Failed to install packages '{current_spec}': {e.stderr}"
            ) from e
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(
                f"Package installation timed out for '{current_spec}'. "
                f"This often happens with git-based installs."
            ) from e

    def get_python_path(self, config: EnvironmentConfig) -> Path:
        """Get the Python executable path for a configuration.

        Args:
            config: Environment configuration

        Returns:
            Path to the python executable
        """
        return self._python_bin(self.base_dir / config.name)

    def _detect_base_python(self) -> Path:
        """Return the python interpreter managed by uv (fall back to sys.executable)."""

        candidates: list[Path] = []
        if os.name == "nt":
            candidates.append(Path(".venv") / "Scripts" / "python.exe")
        else:
            candidates.append(Path(".venv") / "bin" / "python")

        candidates.append(Path(sys.executable))

        for candidate in candidates:
            if candidate.exists():
                return candidate

        # Final fallback: rely on sys.executable even if path doesn't exist (will raise later)
        return Path(sys.executable)

    def _python_bin(self, venv_path: Path) -> Path:
        """Get the python binary inside a venv (handles POSIX/Windows)."""

        if os.name == "nt":
            return venv_path / "Scripts" / "python.exe"
        return venv_path / "bin" / "python"
