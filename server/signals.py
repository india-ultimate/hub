import atexit


def cleanup_on_exit() -> None:
    """Cleanup email worker thread when application exits"""
    # Import here to avoid circular imports
    from server.lib.email_worker import stop_email_worker

    stop_email_worker()


# Register cleanup function to run on application exit
atexit.register(cleanup_on_exit)
