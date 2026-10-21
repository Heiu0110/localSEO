class GSCError(Exception):
    def __init__(self, code: str, message: str, status: int = 400, retryable: bool = False, retry_after: float | None = None):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status
        self.retryable, self.retry_after = retryable, retry_after
