"""Typed errors surfaced by the YinChao ComfyUI nodes."""


class YinChaoError(RuntimeError):
    """Base class for errors that can be shown directly to a node user."""


class ConfigurationError(YinChaoError):
    """The node cannot run because local configuration is incomplete."""


class AuthenticationError(YinChaoError):
    """The API key is missing, invalid, or unauthorized."""


class InsufficientBalanceError(YinChaoError):
    """The YinChao account does not have enough balance/credits."""


class InvalidRequestError(YinChaoError):
    """The API rejected the request parameters or uploaded media."""


class ModerationError(YinChaoError):
    """The provider rejected the request during content moderation."""


class TaskFailedError(YinChaoError):
    """An asynchronous YinChao task reached a failed terminal state."""


class TaskTimeoutError(YinChaoError):
    """An asynchronous YinChao task did not finish before the local deadline."""


class TransportError(YinChaoError):
    """The request could not reach the YinChao API or download the result."""


class ApiResponseError(YinChaoError):
    """The API returned a response that does not match the documented contract."""
