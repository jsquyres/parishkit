"""Initial credential installation bindings, distinct from runtime completion."""

from django.db import models

from parishkit.stewardship.storage import ImmutableRecord


class SetupCredentialInstallation(ImmutableRecord):
    """One frozen readiness input owns one target-isolated credential request.

    The request ID matches the sealed credential ID to preserve its authenticated
    handoff namespace. The target alone copies its own sealed bytes into ordinary
    installation staging. This receipt is not permission to discard rollback
    material before the atomic configured marker exists.
    """

    readiness = models.ForeignKey("SetupReadinessBinding", on_delete=models.PROTECT)
    credential = models.OneToOneField("SetupSealedCredential", on_delete=models.PROTECT)
    request = models.OneToOneField("SecretReplacementRequest", on_delete=models.PROTECT)
    target = models.CharField(max_length=32)
    credential_version = models.PositiveBigIntegerField()
    fingerprint = models.CharField(max_length=64)

    class Meta:
        db_table = "stewardship_setup_credential_install"
        constraints = [
            models.UniqueConstraint(
                fields=["readiness", "target"], name="setup_install_one_target"
            ),
            models.CheckConstraint(
                condition=models.Q(
                    target__in=["parishsoft", "google_workspace", "slack"]
                ),
                name="setup_install_known_target",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    credential_version__gte=1, fingerprint__regex=r"^[0-9a-f]{64}$"
                ),
                name="setup_install_bound_version",
            ),
        ]


class SetupPreparationReceipt(ImmutableRecord):
    """Safe evidence from the config installer to the separate finalization worker.

    Its guarded insert proves exact prepared YAML and all initial consumer ACKs.
    It does not expose target context/ciphertext or claim that setup is complete.
    Original attempt expiry invalidates it for activation without deleting history.
    """

    readiness = models.OneToOneField("SetupReadinessBinding", on_delete=models.PROTECT)
    configuration = models.OneToOneField(
        "AppliedConfigurationVersion", on_delete=models.PROTECT
    )

    class Meta:
        db_table = "stewardship_setup_prepared"
