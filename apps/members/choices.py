from django.utils.translation import gettext_lazy as _

MEMBER_STATUS_CHOICES = (
    (1, _("ACTIVE")),
    (2, _("INACTIVE")),
    (3, _("SUSPENDED")),
)

PLATFORM_CHOICES = (
    (1, _("INSTAGRAM")),
    (2, _("TIKTOK")),
)

BANK_CHOICES = (
    (1, ("Maybank (Malayan Banking Berhad)")),
    (2, ("CIMB Bank")),
    (3, ("Public Bank")),
    (4, ("RHB Bank")),
    (5, ("Hong Leong Bank")),
    (6, ("Ambank")),
    (7, ("Bank Islam Malaysia")),
    (8, ("Bank Rakyat")),
    (9, ("Affin Bank")),
    (10, ("Alliance Bank")),
    (11, ("UOB (United Overseas Bank)")),
    (12, ("HSBC Bank")),
    (13, ("Standard Chartered Bank")),
    (14, ("OCBC Bank")),
    (15, ("Citibank")),
    (16, ("Agrobank")),
    (17, ("Bank Muamalat")),
    (18, ("BSN (Bank Simpanan Nasional)")),
    (19, ("Big Pay")),
    (20, ("Touch N Go")),
    (21, ("GX Bank")),
)
