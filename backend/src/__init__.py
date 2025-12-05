try:
    from dotenv import find_dotenv, load_dotenv

    load_dotenv(find_dotenv())
except Exception:
    try:
        import importlib

        m = importlib.import_module("src.utils.env")
        if hasattr(m, "load_env"):
            m.load_env()
    except Exception:
        try:
            m = importlib.import_module("backend.src.utils.env")
            if hasattr(m, "load_env"):
                m.load_env()
        except Exception:
            pass
