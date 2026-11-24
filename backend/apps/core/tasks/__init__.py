"""Tâches Celery du socle. L'import explicite garantit l'enregistrement."""
from .outbox import dispatch_outbox, replay_failed_outbox  # noqa: F401
from .partitions import *  # noqa: F401,F403
from .security import *  # noqa: F401,F403
