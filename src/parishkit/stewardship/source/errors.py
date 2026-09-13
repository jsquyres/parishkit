"""Closed, intentional source-read failures, distinct from arbitrary OS errors."""


class SourceScopeChanged(PermissionError):
    """Previously admitted source input changed while this read was in flight."""


class SourceCredentialChanged(PermissionError):
    """Loaded source bytes no longer match their explicitly bound fingerprint."""
