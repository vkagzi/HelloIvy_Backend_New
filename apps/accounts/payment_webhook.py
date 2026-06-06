"""
HDFC Webhook Handler for Asynchronous Payment Notifications

Handles payment status callbacks from HDFC SmartGateway.
This is the safety net — if the user closes their browser before the
PaymentStatusView polling can confirm the payment, this webhook will
still mark the payment as completed and provision subscriptions.

Setup:
1. Register the webhook URL in your urls.py (already done below)
2. In HDFC SmartGateway dashboard → Settings → Webhooks, add:
   https://your-domain.com/api/accounts/webhooks/hdfc/
3. HDFC sends a POST with the order status whenever it changes.
   The payload is signed with the RESPONSE_KEY (not the API_KEY).
"""

import logging
import json
from typing import Any

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.conf import settings
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .models import UserPayment, SchoolPayment
from .payment_gateway import get_payment_gateway
from .payment_views import (
    _provision_user_subscriptions, 
    _provision_school_subscriptions_with_students, 
    _slim_webhook_payload, 
    HDFC_TERMINAL_FAILURE_STATUSES,
    _send_payment_status_email
)

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class HDFCWebhookView(APIView):
    """
    Handle HDFC SmartGateway webhook notifications.

    HDFC posts the full order object whenever status changes.
    The response body is signed using the RESPONSE_KEY via HMAC-SHA256.
    """

    permission_classes = [AllowAny]
    authentication_classes = []  # No auth — signature verified via gateway

    # ------------------------------------------------------------------
    # POST handler
    # ------------------------------------------------------------------
    def post(self, request):
        """
        Process an HDFC webhook callback.

        Expected headers:
            x-signature: HMAC-SHA256 of the raw body using RESPONSE_KEY

        Expected JSON body (subset):
            {
              "order_id": "...",
              "txn_id": "...",
              "status": "CHARGED" | "AUTHENTICATION_FAILED" | ...,
              "amount": 99900,
              ...
            }
        """
        try:
            # 1. Verify signature via gateway (uses response/public key) ----
            gateway = get_payment_gateway()
            received_sig = request.META.get("HTTP_X_SIGNATURE", "")
            raw_body = request.body

            if not gateway.verify_webhook_signature(raw_body, received_sig):
                logger.warning("HDFC webhook signature verification failed")
                return Response({"error": "Invalid signature"}, status=403)

            # 2. Parse payload -----------------------------------------------
            payload = request.data
            order_id = payload.get("order_id") or payload.get("orderId")
            status = (payload.get("status") or "").upper()

            if not order_id:
                logger.error(f"HDFC webhook missing order_id: {payload}")
                return Response({"error": "Missing order_id"}, status=400)

            logger.info(f"HDFC webhook received: order_id={order_id}, status={status}")

            # 3. Find the payment record by order_id in metadata -------------
            with transaction.atomic():
                payment, payment_type = self._find_payment(order_id)

                if payment is None:
                    logger.warning(f"Payment not found for webhook order_id={order_id}")
                    # Return 200 so HDFC doesn't retry endlessly
                    return Response({"status": "ignored", "reason": "payment not found"})

                # Already terminal — nothing to do
                if payment.status in (
                    UserPayment.Status.COMPLETED,
                    UserPayment.Status.FAILED,
                    UserPayment.Status.REFUNDED,
                ):
                    logger.info(f"Payment {payment.id} already {payment.status}, ignoring webhook")
                    return Response({"status": "already_processed"})

                # 4. Update based on HDFC status ----------------------------
                if status in ("CHARGED", "AUTO_REFUNDED"):
                    self._mark_completed(payment, payment_type, payload)
                elif status in HDFC_TERMINAL_FAILURE_STATUSES:
                    self._mark_failed(payment, payload)
                else:
                    # Intermediate status — store but leave as pending
                    payment.metadata["last_webhook"] = _slim_webhook_payload(payload)
                    payment.save(update_fields=["metadata", "updated_at"])
                    logger.info(f"Payment {payment.id} intermediate status: {status}")

            return Response({"status": "processed"})

        except Exception as e:
            logger.error(f"Error processing HDFC webhook: {e}", exc_info=True)
            return Response({"error": "Internal error"}, status=500)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _find_payment(order_id: str):
        """Look up a payment by the order_id column."""
        # Try UserPayment first
        payment = UserPayment.objects.filter(order_id=order_id, status=UserPayment.Status.PENDING).first()
        if payment:
            return payment, "student"

        # Then SchoolPayment
        payment = SchoolPayment.objects.filter(order_id=order_id, status=SchoolPayment.Status.PENDING).first()
        if payment:
            return payment, "school"

        return None, None

    @staticmethod
    def _mark_completed(payment, payment_type: str, payload: dict):
        payment.set_status(payment.Status.COMPLETED)
        payment.metadata["webhook_received"] = True
        payment.metadata["webhook_payload"] = _slim_webhook_payload(payload)
        payment.save()

        if payment_type == "student":
            _provision_user_subscriptions(payment)
            _send_payment_status_email(payment, "completed")
            logger.info(f"Student payment {payment.id} completed via webhook")
        else:
            _provision_school_subscriptions_with_students(payment)
            _send_payment_status_email(payment, "completed")
            logger.info(f"School payment {payment.id} completed via webhook")

    @staticmethod
    def _mark_failed(payment, payload: dict):
        payment.set_status(payment.Status.FAILED)
        payment.metadata["webhook_received"] = True
        payment.metadata["webhook_payload"] = _slim_webhook_payload(payload)
        payment.save()
        _send_payment_status_email(payment, "failed")
        logger.warning(f"Payment {payment.id} failed via webhook")
