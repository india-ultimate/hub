from django.core.exceptions import ValidationError
from ninja import Router, UploadedFile
from ninja.params.functions import File

from server.accreditation.certificate import read_certificate
from server.accreditation.models import Accreditation
from server.accreditation.schema import AccreditationFormSchema, AccreditationSchema
from server.core.models import Player
from server.schema import Response
from server.subscription.api import may_see
from server.transaction.models import AuthenticatedHttpRequest
from server.types import message_response

router = Router()


@router.post("/accreditation", response={200: AccreditationSchema, 400: Response})
def add_accreditation(
    request: AuthenticatedHttpRequest,
    accreditation: AccreditationFormSchema,
    certificate: UploadedFile = File(...),  # noqa: B008
) -> tuple[int, Accreditation | message_response]:
    try:
        player = Player.objects.get(id=accreditation.player_id)
    except Player.DoesNotExist:
        return 400, {"message": "Player does not exist"}
    if not may_see(request.user, player):
        return 400, {"message": "Only this player or their guardian can add their accreditation"}

    details = read_certificate(certificate)
    if details is None:
        return 400, {
            "message": "This isn't a WFDF Academy certificate we can read. "
            "Upload the PDF you downloaded from WFDF Academy."
        }
    if not details.is_for(player.user):
        return 400, {
            "message": f"This certificate is for {details.name}, not "
            f"{player.user.get_full_name() or 'this player'}. Upload the player's own certificate, or "
            "correct the name on their profile if it's wrong."
        }
    certificate.seek(0)

    try:
        acc = player.accreditation
    except Accreditation.DoesNotExist:
        acc = Accreditation(player=player)
    acc.certificate = certificate
    acc.certificate_code = details.code
    acc.level = details.level
    acc.date = details.issued
    acc.expiry_date = details.expires

    try:
        acc.save()
    except ValidationError as e:
        return 400, {"message": " ".join(e.messages)}
    return 200, acc
