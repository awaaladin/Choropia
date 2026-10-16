class StorageUnavailable(Exception):
    """Raised by a storage backend when it cannot store or fetch a file (outage, bad credentials...).

    `common.exceptions.api_exception_handler` turns it into a clean 503 instead of a blank 500.
    """
