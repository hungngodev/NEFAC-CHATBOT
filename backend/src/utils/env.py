import os
from pathlib import Path
from typing import Optional

from dotenv import find_dotenv, load_dotenv


def load_env(force: bool = False) -> Optional[str]:
    """Load environment variables from the nearest .env file.

    Resolution order:
    1) ENV_FILE env var, if points to an existing file
    2) Repo root .env (at the repository root)
    3) First .env found by find_dotenv(usecwd=True)

    Returns the loaded path (if any), else None.
    """
    # 1) Explicit override
    env_file = os.environ.get("ENV_FILE")
    if env_file and Path(env_file).expanduser().exists():
        load_dotenv(dotenv_path=Path(env_file).expanduser(), override=force)
        return str(Path(env_file).expanduser())

    # 2) Repo root .env (back 4 levels from src/utils/env.py)
    # backend/src/utils/env.py -> utils -> src -> backend -> repo_root
    repo_env = Path(__file__).resolve().parent.parent.parent.parent / ".env"
    if repo_env.exists():
        load_dotenv(dotenv_path=repo_env, override=force)
        return str(repo_env)

    # 3) Fallback: search from CWD
    located = find_dotenv(usecwd=True)
    if located:
        load_dotenv(located, override=force)
        return located

    return None
