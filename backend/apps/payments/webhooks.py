from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema

from apps.core.webhook_examples import ALL_EVENTS, INBOUND_WEBHOOKS, SIGNATURE_HEADER

from .services.webhooks import process_webhook


@extend_schema(
    tags=["Webhooks & événements"],
    summary="Réception d'un webhook agrégateur de paiement",
    description=(
        "Point d'entrée des notifications agrégateur (Orange Money, Wave, …).\n\n"
        "1. La signature `X-Kalyce-Signature` est vérifiée en temps constant ;\n"
        "2. **Pull-After-Push** : l'agrégateur est ré-interrogé avant toute "
        "transition d'état — la notification seule ne fait jamais foi ;\n"
        "3. Le rejeu du même `idempotency_key` est sans effet."
    ),
    parameters=[
        OpenApiParameter("aggregator", str, OpenApiParameter.PATH,
                         description="Identifiant de l'agrégateur, ex. `GENERIC`."),
        OpenApiParameter(SIGNATURE_HEADER, str, OpenApiParameter.HEADER, required=True,
                         description="HMAC-SHA256 du corps brut, préfixé `sha256=`."),
    ],
    examples=[OpenApiExample(name, summary=spec["summary"], value=spec["payload"],
                             request_only=True)
              for name, spec in INBOUND_WEBHOOKS.items()],
)
class PaymentWebhookView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, aggregator: str):
        raw = request.body
        result = process_webhook(
            aggregator=aggregator, raw_body=raw,
            signature_header=request.headers.get("X-Kalyce-Signature"),
            payload=request.data,
        )
        return Response({"status": result})


@extend_schema(
    tags=["Webhooks & événements"],
    summary="Catalogue des webhooks entrants et des événements sortants",
    description="Renvoie, pour chaque événement clé, un exemple de charge utile "
                "complet — utile pour préparer une intégration sans trafic réel.",
)
class WebhookEventCatalogView(APIView):
    """Documentation exécutable : `GET /api/v1/webhooks/events/`."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({
            "signature_header": SIGNATURE_HEADER,
            "envelope": "{event, event_id (ULID, idempotence), occurred_at, "
                        "reference, data}",
            "inbound": ALL_EVENTS["inbound"],
            "outbound": ALL_EVENTS["outbound"],
        })
