import arrow
import functools
import logging

log = logging.getLogger(__name__)


def to_datetime(value):
    if value is None:
        return None

    # Parse ISO8601 datetime
    dt = arrow.get(value)

    # Convert to UTC
    dt = dt.to('UTC')

    # Return naive datetime object
    return dt.naive


def synchronized(f_lock, mode='full'):
    if mode == 'full':
        mode = ['acquire', 'release']
    elif isinstance(mode, (str, unicode)):
        mode = [mode]

    def wrap(func):
        @functools.wraps(func)
        def wrapped(self, *args, **kwargs):
            lock = f_lock(self)

            def acquire():
                if 'acquire' not in mode:
                    return

                lock.acquire()

            def release():
                if 'release' not in mode:
                    return

                lock.release()

            # Acquire the lock
            acquire()

            try:
                # Execute wrapped function
                result = func(self, *args, **kwargs)
            finally:
                # Release the lock
                release()

            # Return the result
            return result

        return wrapped

    return wrap
