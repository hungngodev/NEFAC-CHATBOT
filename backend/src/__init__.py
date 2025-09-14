try:
    from dotenv import find_dotenv, load_dotenv

    load_dotenv(find_dotenv())
except Exception:
    try:
        import importlib

        m = importlib.import_module("backend.load_env")
        if hasattr(m, "load_env"):
            m.load_env()
    except Exception:
        pass
