from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema
from django.http import HttpResponse, HttpResponseRedirect
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
import logging
import uuid
import urllib.parse
from decimal import Decimal

from collections import Counter

from utils.user_dto_view import UserDTOView
from .dtos import UserDTO
from .roles import UserRole
from .models import User, School, UserPayment, SchoolPayment, UserModuleSubscription, SchoolModuleSubscription, ModuleName, GradeModuleAutoAssignment, ModulePricing, Coupon, ActivityLog
from .serializers import UserPaymentSerializer, SchoolPaymentSerializer, SchoolModuleSubscriptionSerializer, UserModuleSubscriptionSerializer, ModulePricingSerializer, CouponSerializer
from .services import get_module_usage_count_for_school, get_assigned_count_for_school
from .payment_gateway import get_payment_gateway, PaymentGatewayException
from utils.email import send_payment_success_email, send_payment_failed_email, send_payment_pending_email

logger = logging.getLogger(__name__)


def _get_frontend_base_url() -> str:
    """Get the frontend base URL for building return URLs."""
    return getattr(settings, "FRONTEND_BASE_URL", "https://app.helloivy.ai")


def _slim_gateway_verification(raw: dict) -> dict:
    """Extract only the essential fields from an HDFC gateway response.

    Drops bulky noise: udf1-10, emi_details, nested payment_links,
    merchant payloads, SDK tokens, and other redundant / expired data.
    """
    if not raw:
        return {}

    txn = raw.get("txn_detail") or {}
    return {
        "status": raw.get("status"),
        "order_id": raw.get("order_id"),
        "txn_id": raw.get("txn_id") or txn.get("txn_id"),
        "amount": raw.get("amount"),
        "currency": raw.get("currency"),
        "payment_method": raw.get("payment_method"),
        "payment_method_type": raw.get("payment_method_type"),
        "gateway": txn.get("gateway"),
        "date_created": raw.get("date_created"),
        "last_updated": raw.get("last_updated"),
        "refunded": raw.get("refunded"),
        "amount_refunded": raw.get("amount_refunded"),
    }


def _slim_webhook_payload(payload: dict) -> dict:
    """Keep only the fields needed for audit from a webhook payload."""
    if not payload:
        return {}
    return {
        "order_id": payload.get("order_id") or payload.get("orderId"),
        "status": payload.get("status"),
        "txn_id": payload.get("txn_id"),
        "amount": payload.get("amount"),
    }


# ---------------------------------------------------------------------------
# Module pricing — resolved from the ModulePricing table.
# Fallback used only when no DB row exists (e.g. fresh install).
# ---------------------------------------------------------------------------
DEFAULT_MODULE_PRICE = 999
PAYMENT_CURRENCY = "INR"

# Fallback prices matching STATIC_MODULES in the frontend
FALLBACK_PRICES = {
    "college_selector": 4500,
    "career_discovery": 999,
    "domain_discovery": 999,
}

from .currency_utils import get_usd_to_inr_rate


def get_module_price(
    module_name: str,
    user_id: int | None = None,
    school_id: int | None = None,
    currency: str | None = None,
) -> float:
    """Resolve price for a single module.

    Resolution order: user-specific → school-specific → global → fallback.
    If *currency* is not INR, look up the currency_variants JSON; fall back
    to the INR base price when the variant is missing.
    """
    pricing = None

    # 1. User-specific pricing
    if user_id:
        pricing = ModulePricing.objects.filter(
            module_name=module_name, user_id=user_id, is_active=True
        ).first()

    # 2. School-specific pricing
    if not pricing and school_id:
        pricing = ModulePricing.objects.filter(
            module_name=module_name, school_id=school_id, is_active=True
        ).first()

    # 3. Global pricing
    if not pricing:
        pricing = ModulePricing.objects.filter(
            module_name=module_name, school__isnull=True, user__isnull=True, is_active=True
        ).first()

    if not pricing:
        price = FALLBACK_PRICES.get(module_name, DEFAULT_MODULE_PRICE)
        if currency == "USD":
            rate = get_usd_to_inr_rate()
            return round(float(price) / rate, 2)
        return round(float(price), 2)

    base_price = float(pricing.price)
    if currency and currency != "INR":
        variants = pricing.currency_variants or {}
        if currency in variants and variants[currency] is not None:
            return round(float(variants[currency]), 2)
        
        # Automatic conversion if no variant is set
        if currency == "USD":
            rate = get_usd_to_inr_rate()
            return round(base_price / rate, 2)
        # Add other currencies if needed...

    return round(base_price, 2)


def get_all_module_prices(
    user_id: int | None = None,
    school_id: int | None = None,
    currency: str | None = None,
) -> dict[str, float]:
    """Return a {module_name: price} dict for every active ModuleName."""
    return {
        m.value: get_module_price(m.value, school_id=school_id, user_id=user_id, currency=currency)
        for m in ModuleName
    }

# ---------------------------------------------------------------------------
# Tax & discount configuration — must stay in sync with the frontend
# (components/payment/ModuleSelectionForm.tsx)
# ---------------------------------------------------------------------------
GST_RATE = 18  # percent (9% CGST + 9% SGST or 18% IGST)

# VALID_COUPONS dict is removed, we use the Coupon model from DB now.


def _compute_order_totals(
    modules: list[str],
    quantities: dict[str, int],
    coupon_code: str | None = None,
    prices: dict[str, float] | None = None,
) -> dict:
    """
    Compute subtotal, discount, tax, and grand total for an order.

    Returns a dict with: subtotal, discount, tax, total, coupon_code, coupon_pct.
    """
    price_map = prices or {}
    subtotal = sum(
        float(price_map.get(m, DEFAULT_MODULE_PRICE)) * quantities.get(m, 1)
        for m in modules
    )
    subtotal = round(subtotal, 2)
    
    discount = 0.0
    applied_coupon_code = None
    if coupon_code:
        try:
            coupon = Coupon.objects.get(code__iexact=coupon_code.strip())
            is_valid, _ = coupon.is_valid(amount=subtotal)
            if is_valid:
                applied_coupon_code = coupon.code
                if coupon.voucher_type == Coupon.VoucherType.PERCENTAGE:
                    discount = round(subtotal * (float(coupon.voucher_value) / 100), 2)
                else:
                    discount = float(coupon.voucher_value)
        except Coupon.DoesNotExist:
            pass

    taxable = max(0, subtotal - discount)
    tax = round(taxable * GST_RATE / 100, 2)
    total = taxable + tax
    return {
        "subtotal": subtotal,
        "discount": discount,
        "tax": tax,
        "total": total,
        "coupon_code": applied_coupon_code,
    }

def _provision_user_subscriptions(payment: UserPayment) -> None:
    """Create UserModuleSubscription records for each module in a completed payment."""
    if payment.status != UserPayment.Status.COMPLETED:
        return
    # Skip if subscriptions already exist for this payment (idempotency)
    if payment.subscriptions.exists():
        return
    expiry_date = payment.expiry_date or (timezone.now() + timedelta(days=365)).date()
    for entry in payment.modules_purchased:
        module_name = entry["module"]
        UserModuleSubscription.objects.create(
            user=payment.user,
            module_name=module_name,
            expiry_date=expiry_date,
            is_active=True,
            source="payment",
            payment=payment,
        )

    # Increment coupon usage count if applied
    pricing_data = payment.metadata.get("pricing", {})
    applied_code = pricing_data.get("coupon_code")
    if applied_code:
        try:
            from django.db.models import F
            Coupon.objects.filter(code__iexact=applied_code).update(used_count=F("used_count") + 1)
            logger.info(f"[Coupon] Incremented usage for code {applied_code} via user payment {payment.id}")
        except Exception:
            logger.exception(f"[Coupon] Failed to increment used_count for coupon {applied_code}")


def _provision_school_subscriptions(payment: SchoolPayment) -> None:
    """Create SchoolModuleSubscription records for each module in a completed payment."""
    if payment.status != SchoolPayment.Status.COMPLETED:
        return
    if payment.subscriptions.exists():
        return
    expiry_date = payment.expiry_date or (timezone.now() + timedelta(days=365)).date()
    for entry in payment.modules_purchased:
        module_name = entry["module"]
        SchoolModuleSubscription.objects.create(
            school=payment.school,
            module_name=module_name,
            expiry_date=expiry_date,
            is_active=True,
            source="payment",
            payment=payment,
        )

    # Increment coupon usage count if applied
    pricing_data = payment.metadata.get("pricing", {})
    applied_code = pricing_data.get("coupon_code")
    if applied_code:
        try:
            from django.db.models import F
            Coupon.objects.filter(code__iexact=applied_code).update(used_count=F("used_count") + 1)
            logger.info(f"[Coupon] Incremented usage for code {applied_code} via school payment {payment.id}")
        except Exception:
            logger.exception(f"[Coupon] Failed to increment used_count for coupon {applied_code}")


# ---------------------------------------------------------------------------
# Payment email helpers
# ---------------------------------------------------------------------------

GATEWAY_FAILURE_REASONS: dict[str, str] = {
    "AUTHENTICATION_FAILED": "Authentication failed – payment was not authorised",
    "AUTHORIZATION_FAILED": "Authorisation declined by your bank",
    "JUSPAY_DECLINED": "Payment declined by the payment gateway",
}

# All HDFC/Juspay statuses that represent a terminal failure (payment will
# never succeed).  Used across views and the webhook handler to mark the
# payment as failed instead of leaving it stuck in "pending".
HDFC_TERMINAL_FAILURE_STATUSES: set[str] = {
    "AUTHENTICATION_FAILED",
    "AUTHORIZATION_FAILED",
    "JUSPAY_DECLINED",
    "NOT_FOUND",
    # User-initiated cancellations / abandoned flows
    "BACKPRESSED",
    "CANCELLED",
    "USER_ABORTED",
    # Order created but never charged (user closed / navigated away)
    "NEW",
    # Expired sessions
    "EXPIRED",
    "SESSION_EXPIRED",
    "PAYMENT_LINK_EXPIRED",
}


def _format_currency(amount: int | float, currency: str = "INR") -> str:
    """Format amount with currency symbol."""
    symbol = "\u20b9" if currency == "INR" else currency + " "
    return f"{symbol}{amount:,.2f}"


def _build_module_list(payment) -> list[dict]:
    """Build a [{name, price, quantity}] list from modules_purchased."""
    items = []
    for entry in payment.modules_purchased:
        module_name = entry["module"]
        label = module_name.replace("_", " ").title()
        price = entry.get("price")
        quantity = entry.get("quantity", 1)
        items.append({
            "name": label, 
            "price": _format_currency(price, payment.currency) if price else "",
            "quantity": quantity
        })
    return items


def _generate_payment_invoice(payment) -> bytes | None:
    """Prepare InvoiceData and generate PDF bytes for a payment."""
    logger.info(f"[Invoice] Generating PDF for payment_id={payment.id}")
    
    try:
        from utils.invoice_pdf import InvoiceData, InvoiceLineItem, generate_invoice_pdf
        
        # Resolve data (common for both B2C and B2B where possible)
        if isinstance(payment, UserPayment):
            user = payment.user
            email = user.email
            user_name = user.first_name or user.email
            first_name = user.first_name or ""
            last_name = user.last_name or ""
        else:
            school = payment.school
            email = school.contact_email
            user_name = school.name
            first_name = ""
            last_name = ""

        transaction_id = payment.gateway_transaction_id or str(payment.id)
        payment_date = payment.updated_at.strftime("%d %b %Y") if hasattr(payment, "updated_at") else timezone.now().strftime("%d %b %Y")
        currency = payment.currency or "INR"
        
        pricing = (payment.metadata or {}).get("pricing", {})
        billing_state = (payment.metadata or {}).get("billing_state", "")
        tax_label = "CGST (9%) + SGST (9%)" if billing_state == "maharashtra" else "IGST (18%)"
        address = (payment.metadata or {}).get("address", "")
        gst_number = (payment.metadata or {}).get("gst_number", "")

        line_items = []
        for entry in payment.modules_purchased:
            line_items.append(InvoiceLineItem(
                module=entry["module"],
                quantity=entry.get("quantity", 1),
                price=entry.get("price", DEFAULT_MODULE_PRICE),
            ))

        invoice_data = InvoiceData(
            order_id=payment.id,
            order_date=payment_date,
            billing_name=user_name,
            first_name=first_name,
            last_name=last_name,
            email=email,
            address=address,
            gst_number=gst_number,
            line_items=line_items,
            subtotal=pricing.get("subtotal", payment.amount),
            discount=pricing.get("discount", 0),
            discount_code=pricing.get("coupon_code"),
            tax=pricing.get("tax", 0),
            tax_label=tax_label,
            total=payment.amount,
            currency=currency,
            transaction_id=transaction_id,
            status=payment.status.capitalize(),
            payment_mode="HDFC Gateway",
        )
        return generate_invoice_pdf(invoice_data)
    except Exception:
        logger.exception(f"[Invoice] Failed to generate invoice PDF for payment {payment.id}")
        return None


def _send_payment_status_email(payment, status: str, gateway_status: str | None = None) -> None:
    """Send payment success or failure email.

    Works for both UserPayment (B2C) and SchoolPayment (B2B).
    Runs in a best-effort fashion – failures are logged, never raised.
    """
    logger.info(f"[PaymentEmail] _send_payment_status_email called: payment_id={payment.id}, status={status}, gateway_status={gateway_status}")

    try:
        # Resolve recipient
        if isinstance(payment, UserPayment):
            user = payment.user
            email = user.email
            user_name = user.first_name or user.email
            logger.info(f"[PaymentEmail] B2C payment: user_id={user.id}, email={email}, user_name={user_name}")
        else:
            school = payment.school
            email = school.contact_email
            user_name = school.name
            logger.info(f"[PaymentEmail] B2B payment: school_id={school.id}, email={email}, school_name={user_name}")
            if not email:
                logger.warning(f"[PaymentEmail] No contact email for school {school.id}; skipping")
                return

        transaction_id = payment.gateway_transaction_id or str(payment.id)
        payment_date = payment.updated_at.strftime("%d %b %Y") if hasattr(payment, "updated_at") else timezone.now().strftime("%d %b %Y")
        currency = payment.currency or "INR"
        modules = _build_module_list(payment)

        logger.info(f"[PaymentEmail] Prepared data: transaction_id={transaction_id}, date={payment_date}, currency={currency}, amount={payment.amount}, modules={modules}")

        if status == "completed":
            pricing = (payment.metadata or {}).get("pricing", {})
            billing_state = (payment.metadata or {}).get("billing_state", "")
            if billing_state == "maharashtra":
                tax_label = "CGST (9%) + SGST (9%)"
            else:
                tax_label = "IGST (18%)"
            logger.info(f"[PaymentEmail] Sending SUCCESS email to {email}, pricing={pricing}, billing_state={billing_state}")

            # Generate invoice PDF attachment
            invoice_pdf = _generate_payment_invoice(payment) if status == "completed" else None

            send_payment_success_email(
                email=email,
                user_name=user_name,
                transaction_id=transaction_id,
                payment_date=payment_date,
                modules=modules,
                subtotal=_format_currency(pricing.get("subtotal", payment.amount), currency),
                tax=_format_currency(pricing.get("tax", 0), currency),
                total_amount=_format_currency(payment.amount, currency),
                currency=currency,
                discount=_format_currency(pricing["discount"], currency) if pricing.get("discount") else None,
                payment_method="HDFC Gateway",
                tax_label=tax_label,
                invoice_pdf=invoice_pdf,
            )
            logger.info(f"[PaymentEmail] SUCCESS email sent to {email} for payment {payment.id}")
        elif status == "failed":
            failure_reason = GATEWAY_FAILURE_REASONS.get(gateway_status) if gateway_status else None
            logger.info(f"[PaymentEmail] Sending FAILED email to {email}, failure_reason={failure_reason}")
            send_payment_failed_email(
                email=email,
                user_name=user_name,
                transaction_id=transaction_id,
                payment_date=payment_date,
                modules=modules,
                total_amount=_format_currency(payment.amount, currency),
                currency=currency,
                failure_reason=failure_reason,
            )
            logger.info(f"[PaymentEmail] FAILED email sent to {email} for payment {payment.id}")
        elif status == "pending":
            logger.info(f"[PaymentEmail] Sending PENDING email to {email}")
            
            # Generate invoice PDF attachment for pending payments as well
            invoice_pdf = _generate_payment_invoice(payment)
            
            send_payment_pending_email(
                email=email,
                user_name=user_name,
                transaction_id=transaction_id,
                payment_date=payment_date,
                modules=modules,
                total_amount=_format_currency(payment.amount, currency),
                currency=currency,
                invoice_pdf=invoice_pdf,
            )
            logger.info(f"[PaymentEmail] PENDING email sent to {email} for payment {payment.id}")
            logger.info(f"[PaymentEmail] PENDING email sent to {email} for payment {payment.id}")
        else:
            logger.warning(f"[PaymentEmail] Unknown status={status} for payment {payment.id}; no email sent")
    except Exception:
        logger.exception(f"[PaymentEmail] EXCEPTION while sending {status} email for payment {payment.id}")


class StudentCheckoutView(APIView):
    """Create a pending payment for selected modules (B2C students only)."""
    allow_public = True

    def post(self, request: Request) -> Response:
        # Resolve user: authenticated or guest checkout via contact details
        if isinstance(request.user, UserDTO):
            user = User.objects.get(id=request.user.id)
            if user.school_id is not None:
                raise PermissionDenied(detail="Only B2C users can use this endpoint")
        else:
            email = (request.data.get("email") or "").strip().lower()
            if not email:
                return Response({"error": "Email is required for guest checkout"}, status=400)
            first_name = (request.data.get("first_name") or "").strip()
            last_name = (request.data.get("last_name") or "").strip()
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "is_active": False,
                    "role": UserRole.STUDENT,
                },
            )
            if not created and user.school_id is not None:
                raise PermissionDenied(detail="Only B2C users can use this endpoint")
            if not created:
                updated = False
                if first_name and not user.first_name:
                    user.first_name = first_name
                    updated = True
                if last_name and not user.last_name:
                    user.last_name = last_name
                    updated = True
                if updated:
                    user.save(update_fields=["first_name", "last_name"])

        modules = request.data.get("modules", [])
        if not modules or not isinstance(modules, list):
            return Response({"error": "modules must be a non-empty list"}, status=400)

        valid_modules = {m.value for m in ModuleName}
        invalid = [m for m in modules if m not in valid_modules]
        if invalid:
            return Response({"error": f"Invalid module names: {invalid}"}, status=400)

        modules_purchased = [{"module": m, "quantity": q} for m, q in Counter(modules).items()]
        coupon_code = request.data.get("coupon_code")
        billing_state = request.data.get("billing_state", "")
        currency = request.data.get("currency", PAYMENT_CURRENCY)
        quantities = dict(Counter(modules))
        price_map = get_all_module_prices(user_id=user.id, currency=currency)
        order = _compute_order_totals(list(quantities.keys()), quantities, coupon_code, prices=price_map)
        total = order["total"]

        first_name = request.data.get("first_name", "")
        last_name = request.data.get("last_name", "")
        email = request.data.get("email", "")
        phone = request.data.get("phone", "")
        address = request.data.get("address", "")
        gst_number = request.data.get("gst_number", "")

        # Always create a new payment record for each checkout attempt.
        payment = UserPayment(
            user=user,
            modules_purchased=modules_purchased,
            amount=total,
            currency=currency,
            payment_gateway="hdfc",
        )
        payment.metadata = {
            "pricing": order,
            "billing_state": billing_state,
            "first_name": first_name or user.first_name,
            "last_name": last_name or user.last_name,
            "email": email or user.email,
            "phone": phone,
            "address": address,
            "gst_number": gst_number,
        }
        payment.set_status(UserPayment.Status.PENDING)
        payment.save()
        _send_payment_status_email(payment, "pending")

        # If total is 0 (e.g. 100% discount), bypass gateway and provision immediately
        if total == 0:
            payment.set_status(UserPayment.Status.COMPLETED)
            payment.metadata = {
                "pricing": order,
                "billing_state": billing_state,
                "first_name": first_name or user.first_name,
                "last_name": last_name or user.last_name,
                "email": email or user.email,
                "phone": phone,
                "address": address,
                "gst_number": gst_number,
                "is_zero_cost": True,
            }
            payment.save()
            _provision_user_subscriptions(payment)
            _send_payment_status_email(payment, "completed")
            
            ActivityLog.log(
                user=user,
                event_type="payment",
                description=f"Zero-cost checkout completed for: {', '.join(modules)}",
                metadata={"payment_id": payment.id, "modules": modules},
                request=request
            )
            
            return Response({
                "payment_id": payment.id,
                "is_zero_cost": True,
                "status": "completed",
                "message": "Checkout successful (100% discount applied)"
            }, status=201)

        # Initialize HDFC payment order
        frontend_base = _get_frontend_base_url()

        # HDFC rejects a new session with a previously-used order_id.
        # Generate a unique order_id per attempt so retries work.
        hdfc_order_id = f"{payment.id}_{uuid.uuid4().hex[:8]}"

        # HDFC may strip query params from the return URL, so embed
        # all context in the URL path.  The Next.js Route Handler at
        # /api/payment/return/ calls back to Django to verify, then
        # redirects the browser to the frontend status page.
        return_url = f"{frontend_base}/api/payment/return/{hdfc_order_id}/student"

        try:
            gateway = get_payment_gateway()
            gateway_metadata = {
                "payment_id": payment.id,
                "order_id": hdfc_order_id,
                "email": email or user.email,
                "phone": phone or getattr(user, "phone", ""),
                "first_name": first_name or user.first_name,
                "last_name": last_name or user.last_name,
                "address": address,
                "gst_number": gst_number,
                "modules": modules,
                "user_type": "student",
                "description": f"Module subscription: {', '.join(modules)}",
                "return_url": return_url,
            }
            
            gateway_response = gateway.create_payment_order(
                amount=total,
                currency=currency,
                metadata=gateway_metadata
            )
            
            # Store gateway transaction ID and payment URL
            payment.gateway_transaction_id = gateway_response.get("transaction_id", "")
            payment.order_id = gateway_response.get("order_id", "")
            payment_links = gateway_response.get("payment_links", {})
            payment.metadata = {
                "pricing": order,
                "billing_state": billing_state,
                "first_name": first_name or user.first_name,
                "last_name": last_name or user.last_name,
                "email": email or user.email,
                "phone": phone,
                "address": address,
                "gst_number": gst_number,
            }
            payment.save()
            
            ActivityLog.log(
                user=user,
                event_type="payment",
                description=f"Checkout initialized for: {', '.join(modules)}",
                metadata={"payment_id": payment.id, "order_id": hdfc_order_id, "amount": total},
                request=request
            )
            
        except PaymentGatewayException as e:
            logger.error(f"Failed to initialize HDFC payment for user {user.id}: {str(e)}")
            return Response({"error": "Failed to initialize payment. Please try again."}, status=500)

        line_items = [
            {"module": m, "label": m.replace("_", " ").title(), "price": price_map.get(m, DEFAULT_MODULE_PRICE)}
            for m in modules
        ]

        # Return the HDFC payment page URL for frontend redirect
        payment_url = ""
        if isinstance(payment_links, dict):
            payment_url = payment_links.get("web", payment_links.get("mobile", ""))
        elif isinstance(payment_links, str):
            payment_url = payment_links

        return Response({
            "payment_id": payment.id,
            "order_id": payment.order_id,
            "line_items": line_items,
            "subtotal": order["subtotal"],
            "discount": order["discount"],
            "tax": order["tax"],
            "total": total,
            "currency": currency,
            "gateway": "hdfc",
            "transaction_id": payment.gateway_transaction_id,
            "payment_url": payment_url,
        }, status=201)


class StudentCheckoutConfirmView(UserDTOView):
    """Confirm a pending payment — marks it completed and provisions subscriptions."""

    def post(self, request: Request, payment_id: int) -> Response:
        if self.user_dto.school_id is not None:
            raise PermissionDenied(detail="Only B2C users can use this endpoint")

        try:
            payment = UserPayment.objects.get(id=payment_id, user_id=self.user_dto.id)
        except UserPayment.DoesNotExist:
            return Response({"error": "Payment not found"}, status=404)

        if payment.status != UserPayment.Status.PENDING:
            return Response({"error": "Payment is not in pending state"}, status=400)

        payment.set_status(UserPayment.Status.COMPLETED)
        payment.save()
        _provision_user_subscriptions(payment)
        _send_payment_status_email(payment, "completed")
        return Response(UserPaymentSerializer(payment).data, status=200)


class StudentPaymentsView(UserDTOView):
    """List all payments for the current authenticated user."""

    def get(self, request: Request) -> Response:
        payments = UserPayment.objects.filter(user_id=self.user_dto.id).order_by("-created_at")
        return Response({"payments": UserPaymentSerializer(payments, many=True).data}, status=200)


class UserPaymentListCreateView(UserDTOView):
    """List all B2C user payments or create a new one (admin only)."""

    def _require_admin(self) -> None:
        if self.user_dto.role not in (UserRole.SUPERADMIN, UserRole.OPERATIONADMIN):
            raise PermissionDenied(detail="Admin access required")

    @extend_schema(responses={200: UserPaymentSerializer(many=True)})
    def get(self, request: Request) -> Response:
        self._require_admin()
        qs = UserPayment.objects.select_related("user").order_by("-created_at")

        # Optional filters
        user_id = request.query_params.get("user_id")
        status = request.query_params.get("status")
        currency = request.query_params.get("currency")
        if user_id:
            qs = qs.filter(user_id=user_id)
        if status:
            qs = qs.filter(status=status)
        if currency:
            qs = qs.filter(currency=currency)

        serializer = UserPaymentSerializer(qs, many=True)
        return Response({"payments": serializer.data, "total": qs.count()}, status=200)

    @extend_schema(request=UserPaymentSerializer, responses={201: UserPaymentSerializer})
    def post(self, request: Request) -> Response:
        self._require_admin()
        serializer = UserPaymentSerializer(data=request.data)
        if serializer.is_valid():
            payment = serializer.save()
            payment.set_status(payment.status)
            payment.save()
            _provision_user_subscriptions(payment)
            return Response(UserPaymentSerializer(payment).data, status=201)
        return Response(serializer.errors, status=400)


class UserPaymentDetailView(UserDTOView):
    """Retrieve or update a single B2C user payment (admin only)."""

    def _require_admin(self) -> None:
        if self.user_dto.role not in (UserRole.SUPERADMIN, UserRole.OPERATIONADMIN):
            raise PermissionDenied(detail="Admin access required")

    def get(self, request: Request, payment_id: int) -> Response:
        self._require_admin()
        try:
            payment = UserPayment.objects.select_related("user").get(id=payment_id)
        except UserPayment.DoesNotExist:
            return Response({"error": "Payment not found"}, status=404)
        return Response(UserPaymentSerializer(payment).data, status=200)

    def patch(self, request: Request, payment_id: int) -> Response:
        self._require_admin()
        try:
            payment = UserPayment.objects.get(id=payment_id)
        except UserPayment.DoesNotExist:
            return Response({"error": "Payment not found"}, status=404)
        prev_status = payment.status
        serializer = UserPaymentSerializer(payment, data=request.data, partial=True)
        if serializer.is_valid():
            updated = serializer.save()
            new_status = updated.status
            if new_status != prev_status:
                updated.set_status(new_status)
                updated.save()
            if prev_status != UserPayment.Status.COMPLETED:
                _provision_user_subscriptions(updated)
            return Response(UserPaymentSerializer(updated).data, status=200)
        return Response(serializer.errors, status=400)

    def delete(self, request: Request, payment_id: int) -> Response:
        self._require_admin()
        try:
            payment = UserPayment.objects.get(id=payment_id)
        except UserPayment.DoesNotExist:
            return Response({"error": "Payment not found"}, status=404)
        payment.delete()
        return Response(status=204)


class SchoolPaymentListCreateView(UserDTOView):
    """List all school payments or create a new one (admin only)."""

    def _require_admin(self) -> None:
        if self.user_dto.role not in (UserRole.SUPERADMIN, UserRole.OPERATIONADMIN):
            raise PermissionDenied(detail="Admin access required")

    @extend_schema(responses={200: SchoolPaymentSerializer(many=True)})
    def get(self, request: Request) -> Response:
        self._require_admin()
        qs = SchoolPayment.objects.select_related("school").order_by("-created_at")

        school_id = request.query_params.get("school_id")
        status = request.query_params.get("status")
        currency = request.query_params.get("currency")
        if school_id:
            qs = qs.filter(school_id=school_id)
        if status:
            qs = qs.filter(status=status)
        if currency:
            qs = qs.filter(currency=currency)

        serializer = SchoolPaymentSerializer(qs, many=True)
        return Response({"payments": serializer.data, "total": qs.count()}, status=200)

    @extend_schema(request=SchoolPaymentSerializer, responses={201: SchoolPaymentSerializer})
    def post(self, request: Request) -> Response:
        self._require_admin()
        serializer = SchoolPaymentSerializer(data=request.data)
        if serializer.is_valid():
            payment = serializer.save()
            payment.set_status(payment.status)
            payment.save()
            _provision_school_subscriptions(payment)
            return Response(SchoolPaymentSerializer(payment).data, status=201)
        return Response(serializer.errors, status=400)


class SchoolPaymentDetailView(UserDTOView):
    """Retrieve or update a single school payment (admin only)."""

    def _require_admin(self) -> None:
        if self.user_dto.role not in (UserRole.SUPERADMIN, UserRole.OPERATIONADMIN):
            raise PermissionDenied(detail="Admin access required")

    def get(self, request: Request, payment_id: int) -> Response:
        self._require_admin()
        try:
            payment = SchoolPayment.objects.select_related("school").get(id=payment_id)
        except SchoolPayment.DoesNotExist:
            return Response({"error": "Payment not found"}, status=404)
        return Response(SchoolPaymentSerializer(payment).data, status=200)

    def patch(self, request: Request, payment_id: int) -> Response:
        self._require_admin()
        try:
            payment = SchoolPayment.objects.get(id=payment_id)
        except SchoolPayment.DoesNotExist:
            return Response({"error": "Payment not found"}, status=404)
        prev_status = payment.status
        serializer = SchoolPaymentSerializer(payment, data=request.data, partial=True)
        if serializer.is_valid():
            updated = serializer.save()
            new_status = updated.status
            if new_status != prev_status:
                updated.set_status(new_status)
                updated.save()
            if prev_status != SchoolPayment.Status.COMPLETED:
                _provision_school_subscriptions(updated)
            return Response(SchoolPaymentSerializer(updated).data, status=200)
        return Response(serializer.errors, status=400)

    def delete(self, request: Request, payment_id: int) -> Response:
        self._require_admin()
        try:
            payment = SchoolPayment.objects.get(id=payment_id)
        except SchoolPayment.DoesNotExist:
            return Response({"error": "Payment not found"}, status=404)
        payment.delete()
        return Response(status=204)


class AdminPaymentRefreshView(UserDTOView):
    """Refresh payment status from the payment gateway (admin only).

    Works for both B2C (UserPayment) and school (SchoolPayment) payments.
    """

    def _require_admin(self) -> None:
        if self.user_dto.role not in (UserRole.SUPERADMIN, UserRole.OPERATIONADMIN):
            raise PermissionDenied(detail="Admin access required")

    def post(self, request: Request, payment_type: str, payment_id: int) -> Response:
        self._require_admin()

        if payment_type == "b2c":
            try:
                payment = UserPayment.objects.select_related("user").get(id=payment_id)
            except UserPayment.DoesNotExist:
                return Response({"error": "Payment not found"}, status=404)
            serializer_class = UserPaymentSerializer
        elif payment_type == "schools":
            try:
                payment = SchoolPayment.objects.select_related("school").get(id=payment_id)
            except SchoolPayment.DoesNotExist:
                return Response({"error": "Payment not found"}, status=404)
            serializer_class = SchoolPaymentSerializer
        else:
            return Response({"error": "Invalid payment type"}, status=400)

        order_id = payment.order_id or str(payment.id)
        txn_id = payment.gateway_transaction_id

        if not txn_id and not order_id:
            return Response(
                {"error": "No gateway transaction ID or order ID available to verify", "payment": serializer_class(payment).data},
                status=400,
            )

        try:
            gateway = get_payment_gateway()
            result = gateway.verify_payment(order_id=order_id, transaction_id=txn_id)
        except PaymentGatewayException as e:
            return Response(
                {"error": f"Gateway error: {str(e)}", "payment": serializer_class(payment).data},
                status=502,
            )

        # Store a slim snapshot of the gateway response in metadata
        payment.metadata["last_gateway_refresh"] = {
            "timestamp": timezone.now().isoformat(),
            "result": _slim_gateway_verification(result.get("gateway_response", result)),
        }

        # Update status if gateway reports a definitive result and payment is still pending
        gateway_status = result.get("status", "UNKNOWN")
        if result.get("verified") and payment.status == "pending":
            payment.set_status("completed")
            payment.metadata["verification"] = _slim_gateway_verification(result.get("gateway_response", {}))
            payment.save()
            if payment_type == "b2c":
                _provision_user_subscriptions(payment)
            else:
                _provision_school_subscriptions(payment)
            _send_payment_status_email(payment, "completed")
        elif gateway_status in HDFC_TERMINAL_FAILURE_STATUSES and payment.status == "pending":
            payment.set_status("failed")
            payment.metadata["verification"] = _slim_gateway_verification(result.get("gateway_response", {}))
            payment.save()
            _send_payment_status_email(payment, "failed", gateway_status=gateway_status)
        else:
            payment.save()

        return Response({
            "payment": serializer_class(payment).data,
            "gateway_result": result,
        })


# ---------------------------------------------------------------------------
# School-admin self-service checkout (similar to StudentCheckout but for schools)
# ---------------------------------------------------------------------------

def _provision_school_subscriptions_with_students(payment: SchoolPayment) -> None:
    """Create SchoolModuleSubscription with max_students per module."""
    if payment.status != SchoolPayment.Status.COMPLETED:
        return
    if payment.subscriptions.exists():
        return
    expiry_date = payment.expiry_date or (timezone.now() + timedelta(days=365)).date()
    for entry in payment.modules_purchased:
        module_name = entry["module"]
        num_students = entry.get("quantity", payment.quantity or 0)
        SchoolModuleSubscription.objects.create(
            school=payment.school,
            module_name=module_name,
            expiry_date=expiry_date,
            is_active=True,
            source="payment",
            max_students=num_students,
            payment=payment,
        )


class SchoolCheckoutView(UserDTOView):
    """Create a pending payment for selected modules (school admin only)."""

    def _require_school_admin(self) -> None:
        if self.user_dto.role != UserRole.SCHOOLADMIN or self.user_dto.school_id is None:
            raise PermissionDenied(detail="Only school admins can use this endpoint")

    def get(self, request: Request) -> Response:
        """Return total students and school contact details (for pre-filling checkout)."""
        self._require_school_admin()
        total_students = User.objects.filter(
            school_id=self.user_dto.school_id, role=UserRole.STUDENT, is_active=True
        ).count()
        school = School.objects.get(id=self.user_dto.school_id)
        return Response({
            "total_students": total_students,
            "address": school.address or "",
            "email": school.contact_email or "",
            "phone": school.contact_phone or "",
        }, status=200)

    def post(self, request: Request) -> Response:
        self._require_school_admin()

        module_quantities = request.data.get("module_quantities", {})
        if not module_quantities or not isinstance(module_quantities, dict):
            return Response({"error": "module_quantities must be a non-empty dict of {module: num_students}"}, status=400)

        valid_modules = {m.value for m in ModuleName}
        invalid = [m for m in module_quantities if m not in valid_modules]
        if invalid:
            return Response({"error": f"Invalid module names: {invalid}"}, status=400)

        invalid_qty = [m for m, qty in module_quantities.items() if not isinstance(qty, int) or qty < 1]
        if invalid_qty:
            return Response({"error": f"Each module must have a positive integer student count: {invalid_qty}"}, status=400)

        modules = list(module_quantities.keys())
        modules_purchased = [{"module": m, "quantity": qty} for m, qty in module_quantities.items()]
        coupon_code = request.data.get("coupon_code")
        billing_state = request.data.get("billing_state", "")

        first_name = request.data.get("first_name", "")
        last_name = request.data.get("last_name", "")
        email = request.data.get("email", "")
        phone = request.data.get("phone", "")
        address = request.data.get("address", "")
        gst_number = request.data.get("gst_number", "")

        school = School.objects.get(id=self.user_dto.school_id)
        currency = request.data.get("currency", school.currency or "INR")
        price_map = get_all_module_prices(school_id=school.id, currency=currency)
        order = _compute_order_totals(modules, module_quantities, coupon_code, prices=price_map)
        total = order["total"]

        metadata = {
            "module_quantities": module_quantities,
            "pricing": order,
            "billing_state": billing_state,
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "phone": phone,
            "address": address,
            "gst_number": gst_number,
        }

        # Always create a new payment record for each checkout attempt.
        payment = SchoolPayment(
            school=school,
            modules_purchased=modules_purchased,
            amount=total,
            currency=PAYMENT_CURRENCY,
            payment_gateway="hdfc",
            metadata=metadata,
        )
        payment.set_status(SchoolPayment.Status.PENDING)
        payment.save()

        # Initialize HDFC payment order
        frontend_base = _get_frontend_base_url()

        # HDFC rejects a new session with a previously-used order_id.
        # Generate a unique order_id per attempt so retries work.
        hdfc_order_id = f"{payment.id}_{uuid.uuid4().hex[:8]}"

        # If total is 0, bypass gateway and provision immediately
        if total == 0:
            payment.set_status(SchoolPayment.Status.COMPLETED)
            payment.metadata = {
                **payment.metadata,
                "pricing": order,
                "is_zero_cost": True,
            }
            payment.save()
            _provision_school_subscriptions_with_students(payment)
            _send_payment_status_email(payment, "completed")

            return Response({
                "payment_id": payment.id,
                "is_zero_cost": True,
                "status": "completed",
                "message": "Checkout successful (100% discount applied)"
            }, status=201)

        try:
            gateway = get_payment_gateway()
            gateway_metadata = {
                "payment_id": payment.id,
                "order_id": hdfc_order_id,
                "email": email or school.contact_email,
                "phone": phone or school.contact_phone,
                "first_name": first_name,
                "last_name": last_name,
                "address": address,
                "gst_number": gst_number,
                "modules": modules,
                "module_quantities": module_quantities,
                "user_type": "school",
                "description": f"School subscription: {', '.join(modules)} for {len(module_quantities)} modules",
                "return_url": return_url,
            }
            
            gateway_response = gateway.create_payment_order(
                amount=total,
                currency=currency,
                metadata=gateway_metadata
            )
            
            # Store gateway transaction ID and order information
            payment.gateway_transaction_id = gateway_response.get("transaction_id", "")
            payment.order_id = gateway_response.get("order_id", "")
            payment_links = gateway_response.get("payment_links", {})
            payment.metadata = {
                **payment.metadata,
                "pricing": order,
            }
            payment.save()
            
        except PaymentGatewayException as e:
            logger.error(f"Failed to initialize HDFC payment for school {school.id}: {str(e)}")
            return Response({"error": "Failed to initialize payment. Please try again."}, status=500)

        line_items = [
            {"module": m, "label": m.replace("_", " ").title(), "price": price_map.get(m, DEFAULT_MODULE_PRICE)}
            for m in modules
        ]

        # Return the HDFC payment page URL for frontend redirect
        payment_url = ""
        if isinstance(payment_links, dict):
            payment_url = payment_links.get("web", payment_links.get("mobile", ""))
        elif isinstance(payment_links, str):
            payment_url = payment_links

        return Response({
            "payment_id": payment.id,
            "line_items": line_items,
            "module_quantities": module_quantities,
            "subtotal": order["subtotal"],
            "discount": order["discount"],
            "tax": order["tax"],
            "total": total,
            "currency": currency,
            "gateway": "hdfc",
            "transaction_id": payment.gateway_transaction_id,
            "payment_url": payment_url,
        }, status=201)


class SchoolCheckoutConfirmView(UserDTOView):
    """Confirm a pending school payment — marks it completed and provisions subscriptions."""

    def _require_school_admin(self) -> None:
        if self.user_dto.role != UserRole.SCHOOLADMIN or self.user_dto.school_id is None:
            raise PermissionDenied(detail="Only school admins can use this endpoint")

    def post(self, request: Request, payment_id: int) -> Response:
        self._require_school_admin()

        try:
            payment = SchoolPayment.objects.get(id=payment_id, school_id=self.user_dto.school_id)
        except SchoolPayment.DoesNotExist:
            return Response({"error": "Payment not found"}, status=404)

        if payment.status != SchoolPayment.Status.PENDING:
            return Response({"error": "Payment is not in pending state"}, status=400)

        payment.set_status(SchoolPayment.Status.COMPLETED)
        payment.save()
        _provision_school_subscriptions_with_students(payment)
        _send_payment_status_email(payment, "completed")
        return Response(SchoolPaymentSerializer(payment).data, status=200)


class SchoolPaymentsHistoryView(UserDTOView):
    """List all payments for the current school admin's school."""

    def _require_school_admin(self) -> None:
        if self.user_dto.role not in (UserRole.SCHOOLADMIN, UserRole.SCHOOLOPSADMIN) or self.user_dto.school_id is None:
            raise PermissionDenied(detail="Only school admins can use this endpoint")

    def get(self, request: Request) -> Response:
        self._require_school_admin()
        payments = SchoolPayment.objects.filter(school_id=self.user_dto.school_id).order_by("-created_at")
        return Response({"payments": SchoolPaymentSerializer(payments, many=True).data}, status=200)


class SchoolSubscriptionsView(UserDTOView):
    """List active module subscriptions for the current school admin's school (aggregated by module)."""

    def _require_school_admin(self) -> None:
        if self.user_dto.role not in (UserRole.SCHOOLADMIN, UserRole.SCHOOLOPSADMIN) or self.user_dto.school_id is None:
            raise PermissionDenied(detail="Only school admins can use this endpoint")

    def get(self, request: Request) -> Response:
        self._require_school_admin()
        from django.db.models import Sum, Max

        today = timezone.now().date()
        agg = (
            SchoolModuleSubscription.objects.filter(
                school_id=self.user_dto.school_id, is_active=True, expiry_date__gte=today
            )
            .values("module_name")
            .annotate(
                total_max_students=Sum("max_students"),
                latest_expiry=Max("expiry_date"),
            )
        )

        module_display_map = dict(ModuleName.choices)
        result = []
        for row in agg:
            assigned = get_assigned_count_for_school(row["module_name"], self.user_dto.school_id)
            total_max = row["total_max_students"]
            result.append({
                "module_name": row["module_name"],
                "module_display": module_display_map.get(row["module_name"], row["module_name"]),
                "max_students": total_max,
                "expiry_date": row["latest_expiry"].isoformat() if row["latest_expiry"] else None,
                "is_active": True,
                "used_students": assigned,
                "remaining_students": (total_max - assigned) if total_max is not None else None,
            })
        return Response({"subscriptions": result}, status=200)


class StudentSubscriptionsView(UserDTOView):
    """List module subscriptions for the current student/B2C user (aggregated by module)."""

    def get(self, request: Request) -> Response:
        from django.db.models import Max

        today = timezone.now().date()

        # Get all active subscriptions for this user
        active_subs = (
            UserModuleSubscription.objects
            .filter(user_id=self.user_dto.id, is_active=True, expiry_date__gte=today)
            .select_related("payment")
        )

        # Aggregate by module
        module_data: dict[str, dict] = {}
        for sub in active_subs:
            mod = sub.module_name
            if mod not in module_data:
                module_data[mod] = {"latest_expiry": sub.expiry_date, "total_purchased": 0}
            if sub.expiry_date > module_data[mod]["latest_expiry"]:
                module_data[mod]["latest_expiry"] = sub.expiry_date
            # Get quantity from associated payment
            qty = 1
            if sub.payment_id and sub.payment.modules_purchased:
                for entry in sub.payment.modules_purchased:
                    if isinstance(entry, dict) and entry.get("module") == mod:
                        qty = entry.get("quantity", 1)
                        break
            module_data[mod]["total_purchased"] += qty

        module_display_map = dict(ModuleName.choices)
        result = []
        for mod, data in module_data.items():
            used = self._get_user_session_count(mod)
            purchased = data["total_purchased"]
            result.append({
                "module_name": mod,
                "module_display": module_display_map.get(mod, mod),
                "expiry_date": data["latest_expiry"].isoformat(),
                "is_active": True,
                "purchased": purchased,
                "used_sessions": used,
                "remaining_sessions": max(0, purchased - used),
            })
        return Response({"subscriptions": result}, status=200)

    def _get_user_session_count(self, module_name: str) -> int:
        if module_name == "domain_discovery":
            from domain_discovery.models import DomainSession
            return DomainSession.objects.filter(user_id=self.user_dto.id).count()
        if module_name == "career_discovery":
            from career_discovery.models import CareerSession
            return CareerSession.objects.filter(user_id=self.user_dto.id).count()
        return 0


# ---------------------------------------------------------------------------
# Ledger views — unified subscription + payment history per entity
# ---------------------------------------------------------------------------

class SchoolLedgerView(UserDTOView):
    """Full ledger for a school: all subscriptions and payments, ordered by date."""

    def _require_access(self) -> int:
        if self.user_dto.role in (UserRole.SUPERADMIN, UserRole.OPERATIONADMIN):
            school_id = self.request.query_params.get("school_id")
            if not school_id:
                raise PermissionDenied(detail="school_id query param required for admin")
            return int(school_id)
        if self.user_dto.role in (UserRole.SCHOOLADMIN, UserRole.SCHOOLOPSADMIN) and self.user_dto.school_id:
            return self.user_dto.school_id
        raise PermissionDenied(detail="Access denied")

    def get(self, request: Request) -> Response:
        school_id = self._require_access()

        subscriptions = SchoolModuleSubscription.objects.filter(
            school_id=school_id
        ).order_by("-created_at")
        payments = SchoolPayment.objects.filter(
            school_id=school_id
        ).order_by("-created_at")

        # Active modules: distinct modules with active, non-expired subscriptions
        today = timezone.now().date()
        active_modules = list(
            SchoolModuleSubscription.objects.filter(
                school_id=school_id, is_active=True, expiry_date__gte=today
            ).values_list("module_name", flat=True).distinct()
        )

        # Student assignment counts per module
        assignment_counts = {}
        for mod in active_modules:
            count = UserModuleSubscription.objects.filter(
                school_subscription__school_id=school_id,
                school_subscription__module_name=mod,
                is_active=True,
                expiry_date__gte=today,
            ).values("user_id").distinct().count()
            assignment_counts[mod] = count

        return Response({
            "school_id": school_id,
            "active_modules": active_modules,
            "assignment_counts": assignment_counts,
            "subscriptions": SchoolModuleSubscriptionSerializer(subscriptions, many=True).data,
            "payments": SchoolPaymentSerializer(payments, many=True).data,
        }, status=200)


class StudentLedgerView(UserDTOView):
    """Full ledger for a student: all subscriptions (B2C purchases + B2B assignments) and payments."""

    def get(self, request: Request) -> Response:
        # Students see their own ledger; admins can pass user_id
        if self.user_dto.role in (UserRole.SUPERADMIN, UserRole.OPERATIONADMIN):
            user_id = request.query_params.get("user_id")
            if not user_id:
                raise PermissionDenied(detail="user_id query param required for admin")
            user_id = int(user_id)
        elif self.user_dto.role in (UserRole.SCHOOLADMIN, UserRole.SCHOOLOPSADMIN):
            user_id = request.query_params.get("user_id")
            if not user_id:
                raise PermissionDenied(detail="user_id query param required")
            user_id = int(user_id)
            # Verify the student belongs to the admin's school
            try:
                student = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return Response({"error": "User not found"}, status=404)
            if student.school_id != self.user_dto.school_id:
                raise PermissionDenied(detail="User does not belong to your school")
        else:
            user_id = self.user_dto.id

        subscriptions = UserModuleSubscription.objects.filter(
            user_id=user_id
        ).select_related("payment", "school_subscription", "assigned_by").order_by("-created_at")
        payments = UserPayment.objects.filter(
            user_id=user_id
        ).order_by("-created_at")

        today = timezone.now().date()
        active_modules = list(
            UserModuleSubscription.objects.filter(
                user_id=user_id, is_active=True, expiry_date__gte=today
            ).values_list("module_name", flat=True).distinct()
        )

        # Also include school-level modules if user belongs to a school
        user = User.objects.get(id=user_id)
        school_modules = []
        if user.school_id:
            school_modules = list(
                SchoolModuleSubscription.objects.filter(
                    school_id=user.school_id, is_active=True, expiry_date__gte=today
                ).values_list("module_name", flat=True).distinct()
            )

        return Response({
            "user_id": user_id,
            "active_modules": list(set(active_modules + school_modules)),
            "b2c_modules": [m for m in active_modules if UserModuleSubscription.objects.filter(
                user_id=user_id, module_name=m, source="payment", is_active=True, expiry_date__gte=today
            ).exists()],
            "b2b_modules": [m for m in active_modules if UserModuleSubscription.objects.filter(
                user_id=user_id, module_name=m, source="school_assignment", is_active=True, expiry_date__gte=today
            ).exists()],
            "school_modules": school_modules,
            "subscriptions": UserModuleSubscriptionSerializer(subscriptions, many=True).data,
            "payments": UserPaymentSerializer(payments, many=True).data,
        }, status=200)


# ---------------------------------------------------------------------------
# Module assignment for B2B students (school admin / school ops admin)
# ---------------------------------------------------------------------------

class SchoolStudentModuleAssignView(UserDTOView):
    """
    Assign or revoke module access for B2B students.
    Only schooladmin and schoolopsadmin of the same school can use this.
    Supports assigning by user_ids, grade_level, or both.
    """

    def _require_school_admin(self) -> None:
        if self.user_dto.role not in (UserRole.SCHOOLADMIN, UserRole.SCHOOLOPSADMIN):
            raise PermissionDenied(detail="School admin access required")
        if not self.user_dto.school_id:
            raise PermissionDenied(detail="You must belong to a school")

    def get(self, request: Request) -> Response:
        """List all module assignments for students in this school."""
        self._require_school_admin()
        today = timezone.now().date()

        # Get all active school subscriptions
        school_subs = SchoolModuleSubscription.objects.filter(
            school_id=self.user_dto.school_id, is_active=True, expiry_date__gte=today
        )

        # Optional grade filter
        grade_level = request.query_params.get("grade_level")

        # Get all student assignments for this school
        assignments_qs = UserModuleSubscription.objects.filter(
            school_subscription__school_id=self.user_dto.school_id,
            source="school_assignment",
        ).select_related("user", "school_subscription", "assigned_by").order_by("-created_at")

        if grade_level:
            assignments_qs = assignments_qs.filter(user__grade_level=grade_level)

        assignment_data = []
        for a in assignments_qs:
            assignment_data.append({
                "id": a.id,
                "user_id": a.user_id,
                "user_email": a.user.email,
                "user_name": f"{a.user.first_name} {a.user.last_name}".strip(),
                "grade_level": a.user.grade_level or "",
                "module_name": a.module_name,
                "module_display": a.get_module_name_display(),
                "expiry_date": a.expiry_date,
                "is_active": a.is_active,
                "assigned_by": a.assigned_by.email if a.assigned_by else None,
                "created_at": a.created_at,
            })

        # Include auto-assign rules
        auto_rules = GradeModuleAutoAssignment.objects.filter(
            school_id=self.user_dto.school_id, is_active=True
        ).select_related("created_by")
        auto_rules_data = [
            {
                "id": r.id,
                "grade_level": r.grade_level,
                "module_name": r.module_name,
                "module_display": r.get_module_name_display(),
                "is_active": r.is_active,
                "created_by": r.created_by.email if r.created_by else None,
                "created_at": r.created_at,
            }
            for r in auto_rules
        ]

        return Response({
            "school_subscriptions": SchoolModuleSubscriptionSerializer(school_subs, many=True).data,
            "assignments": assignment_data,
            "auto_assign_rules": auto_rules_data,
        }, status=200)

    def post(self, request: Request) -> Response:
        """
        Assign modules to students.
        Body: {
            "user_ids": [1, 2, 3],         # optional if grade_level provided
            "grade_level": "Grade 10",       # optional if user_ids provided
            "module_names": ["career_discovery"],
            "expiry_date": "2027-01-01"      # optional, defaults to subscription expiry
        }
        """
        self._require_school_admin()
        today = timezone.now().date()

        user_ids = request.data.get("user_ids", [])
        grade_level = request.data.get("grade_level")
        module_names = request.data.get("module_names", [])
        expiry_date_str = request.data.get("expiry_date")

        if not user_ids and not grade_level:
            return Response({"error": "Provide user_ids, grade_level, or both"}, status=400)
        if not module_names or not isinstance(module_names, list):
            return Response({"error": "module_names must be a non-empty list"}, status=400)

        valid_modules = {m.value for m in ModuleName}
        invalid = [m for m in module_names if m not in valid_modules]
        if invalid:
            return Response({"error": f"Invalid module names: {invalid}"}, status=400)

        # Resolve students: merge user_ids and grade_level
        student_filter = {"school_id": self.user_dto.school_id, "role": UserRole.STUDENT}
        if user_ids and grade_level:
            # Both: union of explicit IDs + grade
            from django.db.models import Q
            students = User.objects.filter(
                Q(id__in=user_ids) | Q(grade_level=grade_level),
                **student_filter,
            )
        elif grade_level:
            students = User.objects.filter(grade_level=grade_level, **student_filter)
        else:
            students = User.objects.filter(id__in=user_ids, **student_filter)
            if students.count() != len(user_ids):
                return Response({"error": "Some user_ids are invalid or don't belong to your school"}, status=400)

        if not students.exists():
            return Response({"error": "No matching students found"}, status=400)

        # Find the matching active school subscriptions
        school_subs = {
            sub.module_name: sub
            for sub in SchoolModuleSubscription.objects.filter(
                school_id=self.user_dto.school_id,
                module_name__in=module_names,
                is_active=True,
                expiry_date__gte=today,
            ).order_by("-expiry_date")
        }

        missing_modules = [m for m in module_names if m not in school_subs]
        if missing_modules:
            return Response(
                {"error": f"School does not have active subscriptions for: {missing_modules}"},
                status=400,
            )

        # Soft capacity check
        warnings = []
        from django.db.models import Sum
        for mod in module_names:
            school_sub = school_subs[mod]
            if school_sub.max_students is not None:
                current_assigned = get_assigned_count_for_school(mod, self.user_dto.school_id)
                new_count = students.count()
                if current_assigned + new_count > school_sub.max_students:
                    warnings.append(
                        f"{mod}: assigning {new_count} seats would exceed purchased capacity "
                        f"({current_assigned} assigned + {new_count} new = {current_assigned + new_count}, "
                        f"max = {school_sub.max_students})"
                    )

        admin_user = User.objects.get(id=self.user_dto.id)
        created = []
        skipped = 0
        for student in students:
            for mod in module_names:
                school_sub = school_subs[mod]
                # Duplicate prevention: skip if active assignment already exists
                existing = UserModuleSubscription.objects.filter(
                    user=student,
                    module_name=mod,
                    school_subscription=school_sub,
                    source="school_assignment",
                    is_active=True,
                ).exists()
                if existing:
                    skipped += 1
                    continue

                exp_date = expiry_date_str or str(school_sub.expiry_date)
                assignment = UserModuleSubscription.objects.create(
                    user=student,
                    module_name=mod,
                    expiry_date=exp_date,
                    is_active=True,
                    source="school_assignment",
                    school_subscription=school_sub,
                    assigned_by=admin_user,
                )
                created.append({
                    "id": assignment.id,
                    "user_id": student.id,
                    "user_email": student.email,
                    "module_name": mod,
                    "expiry_date": str(assignment.expiry_date),
                })

        response_data: dict = {"assigned": created, "count": len(created), "skipped": skipped}
        if warnings:
            response_data["warnings"] = warnings
        return Response(response_data, status=201)


class SchoolStudentModuleRevokeView(UserDTOView):
    """Revoke (deactivate) a specific module assignment for a B2B student."""

    def _require_school_admin(self) -> None:
        if self.user_dto.role not in (UserRole.SCHOOLADMIN, UserRole.SCHOOLOPSADMIN):
            raise PermissionDenied(detail="School admin access required")
        if not self.user_dto.school_id:
            raise PermissionDenied(detail="You must belong to a school")

    def post(self, request: Request, assignment_id: int) -> Response:
        self._require_school_admin()
        try:
            assignment = UserModuleSubscription.objects.get(
                id=assignment_id,
                source="school_assignment",
                school_subscription__school_id=self.user_dto.school_id,
            )
        except UserModuleSubscription.DoesNotExist:
            return Response({"error": "Assignment not found"}, status=404)

        assignment.is_active = False
        assignment.save()
        return Response({"message": "Module access revoked", "id": assignment_id}, status=200)


class SchoolModuleReminderView(UserDTOView):
    """Send module completion reminder emails to selected students."""

    def _require_school_admin(self) -> None:
        if self.user_dto.role not in (UserRole.SCHOOLADMIN, UserRole.SCHOOLOPSADMIN):
            raise PermissionDenied(detail="School admin access required")
        if not self.user_dto.school_id:
            raise PermissionDenied(detail="You must belong to a school")

    def post(self, request: Request) -> Response:
        """
        Send reminder emails to students about their assigned modules.
        Body: {
            "user_ids": [1, 2, 3],
        }
        """
        self._require_school_admin()

        user_ids = request.data.get("user_ids", [])
        if not user_ids or not isinstance(user_ids, list):
            return Response({"error": "user_ids must be a non-empty list"}, status=400)

        students = User.objects.filter(
            id__in=user_ids,
            school_id=self.user_dto.school_id,
            role=UserRole.STUDENT,
        )
        if not students.exists():
            return Response({"error": "No matching students found"}, status=400)

        from utils.email import send_email

        school_name = School.objects.filter(id=self.user_dto.school_id).values_list('name', flat=True).first() or ''
        platform_url = _get_frontend_base_url()

        sent = []
        failed = []
        for student in students:
            try:
                send_email(
                    to=student.email,
                    subject="Reminder: Complete Your Module",
                    html=(
                        "<p>Hello,</p>"
                        "<p>Time's running out! Hurry! Complete your module now "
                        "before your service expires! Please ignore if already completed.</p>"
                        f'<p><a href="{platform_url}">{platform_url}</a></p>'
                        f"{'<p>— ' + school_name + '</p>' if school_name else ''}"
                    ),
                )
                sent.append(student.email)
            except Exception as e:
                logger.warning("Failed to send reminder to %s: %s", student.email, e)
                failed.append(student.email)

        return Response({"sent": sent, "failed": failed, "count": len(sent)}, status=200)


class GradeAutoAssignView(UserDTOView):
    """Manage auto-assignment rules: when a student is added to a grade, auto-assign modules."""

    def _require_school_admin(self) -> None:
        if self.user_dto.role not in (UserRole.SCHOOLADMIN, UserRole.SCHOOLOPSADMIN):
            raise PermissionDenied(detail="School admin access required")
        if not self.user_dto.school_id:
            raise PermissionDenied(detail="You must belong to a school")

    def get(self, request: Request) -> Response:
        """List all active auto-assign rules for this school."""
        self._require_school_admin()
        rules = GradeModuleAutoAssignment.objects.filter(
            school_id=self.user_dto.school_id, is_active=True
        ).select_related("school_subscription", "created_by").order_by("grade_level", "module_name")

        data = [
            {
                "id": r.id,
                "grade_level": r.grade_level,
                "module_name": r.module_name,
                "module_display": r.get_module_name_display(),
                "school_subscription_id": r.school_subscription_id,
                "is_active": r.is_active,
                "created_by": r.created_by.email if r.created_by else None,
                "created_at": r.created_at,
            }
            for r in rules
        ]
        return Response({"auto_assign_rules": data}, status=200)

    def post(self, request: Request) -> Response:
        """
        Create auto-assign rules.
        Body: { "grade_level": "Grade 10", "module_names": ["career_discovery", "domain_discovery"] }
        """
        self._require_school_admin()
        today = timezone.now().date()

        grade_level = request.data.get("grade_level")
        module_names = request.data.get("module_names", [])

        if not grade_level:
            return Response({"error": "grade_level is required"}, status=400)
        if not module_names or not isinstance(module_names, list):
            return Response({"error": "module_names must be a non-empty list"}, status=400)

        valid_modules = {m.value for m in ModuleName}
        invalid = [m for m in module_names if m not in valid_modules]
        if invalid:
            return Response({"error": f"Invalid module names: {invalid}"}, status=400)

        # Find active school subscriptions for these modules
        school_subs = {
            sub.module_name: sub
            for sub in SchoolModuleSubscription.objects.filter(
                school_id=self.user_dto.school_id,
                module_name__in=module_names,
                is_active=True,
                expiry_date__gte=today,
            ).order_by("-expiry_date")
        }

        missing = [m for m in module_names if m not in school_subs]
        if missing:
            return Response(
                {"error": f"No active subscriptions for: {missing}"},
                status=400,
            )

        admin_user = User.objects.get(id=self.user_dto.id)
        created = []
        for mod in module_names:
            rule, was_created = GradeModuleAutoAssignment.objects.update_or_create(
                school_id=self.user_dto.school_id,
                grade_level=grade_level,
                module_name=mod,
                defaults={
                    "school_subscription": school_subs[mod],
                    "created_by": admin_user,
                    "is_active": True,
                },
            )
            created.append({
                "id": rule.id,
                "grade_level": rule.grade_level,
                "module_name": rule.module_name,
                "created": was_created,
            })

        return Response({"rules": created, "count": len(created)}, status=201)


class StudentInvoiceDownloadView(UserDTOView):
    """Serve invoice PDF for a student payment."""

    def get(self, request: Request, payment_id: int) -> HttpResponse | Response:
        try:
            payment = UserPayment.objects.get(id=payment_id, user_id=self.user_dto.id)
        except UserPayment.DoesNotExist:
            return Response({"error": "Payment not found"}, status=404)


        pdf_bytes = _generate_payment_invoice(payment)
        if not pdf_bytes:
            return Response({"error": "Failed to generate invoice PDF"}, status=500)

        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="HelloIvy_Invoice_{payment_id}.pdf"'
        return response


class SchoolInvoiceDownloadView(UserDTOView):
    """Serve invoice PDF for a school payment."""

    def _require_school_admin(self) -> None:
        if self.user_dto.role not in (UserRole.SCHOOLADMIN, UserRole.SCHOOLOPSADMIN) or self.user_dto.school_id is None:
            raise PermissionDenied(detail="Only school admins can use this endpoint")

    def get(self, request: Request, payment_id: int) -> HttpResponse | Response:
        self._require_school_admin()
        try:
            payment = SchoolPayment.objects.get(id=payment_id, school_id=self.user_dto.school_id)
        except SchoolPayment.DoesNotExist:
            return Response({"error": "Payment not found"}, status=404)


        pdf_bytes = _generate_payment_invoice(payment)
        if not pdf_bytes:
            return Response({"error": "Failed to generate invoice PDF"}, status=500)

        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="HelloIvy_School_Invoice_{payment_id}.pdf"'
        return response


class GradeAutoAssignDeleteView(UserDTOView):
    """Deactivate an auto-assign rule."""

    def _require_school_admin(self) -> None:
        if self.user_dto.role not in (UserRole.SCHOOLADMIN, UserRole.SCHOOLOPSADMIN):
            raise PermissionDenied(detail="School admin access required")
        if not self.user_dto.school_id:
            raise PermissionDenied(detail="You must belong to a school")

    def delete(self, request: Request, rule_id: int) -> Response:
        self._require_school_admin()
        try:
            rule = GradeModuleAutoAssignment.objects.get(
                id=rule_id, school_id=self.user_dto.school_id
            )
        except GradeModuleAutoAssignment.DoesNotExist:
            return Response({"error": "Auto-assign rule not found"}, status=404)

        rule.is_active = False
        rule.save()
        return Response({"message": "Auto-assign rule deactivated", "id": rule_id}, status=200)


# ---------------------------------------------------------------------------
# Payment retry — allow resuming a pending payment session
# ---------------------------------------------------------------------------

class PaymentRetryView(UserDTOView):
    """
    Re-initialize a pending payment session with HDFC.
    
    Used when a user returns to their dashboard and wants to complete
     a payment that was previously started but not finished.
    """

    def post(self, request: Request, payment_id: int, **kwargs) -> Response:
        payment_type = kwargs.get("type", "student")
        
        logger.info(f"[PaymentRetry] Received request for payment_id={payment_id}, type={payment_type}, user={self.user_dto.id}")

        if payment_type == "school":
            if self.user_dto.role not in (UserRole.SCHOOLADMIN, UserRole.SCHOOLOPSADMIN) or self.user_dto.school_id is None:
                raise PermissionDenied(detail="Only school admins can retry school payments")
            try:
                payment = SchoolPayment.objects.get(id=payment_id, school_id=self.user_dto.school_id)
            except SchoolPayment.DoesNotExist:
                return Response({"error": "Payment not found"}, status=404)
        else:
            try:
                payment = UserPayment.objects.get(id=payment_id, user_id=self.user_dto.id)
            except UserPayment.DoesNotExist:
                logger.error(f"[PaymentRetry] UserPayment {payment_id} not found for user {self.user_dto.id}")
                return Response({"error": "Payment not found"}, status=404)

        if payment.status != payment.Status.PENDING:
            logger.warning(f"[PaymentRetry] Attempted to retry non-pending payment {payment.id} (status: {payment.status})")
            return Response({
                "error": f"Only pending payments can be retried. Current status: {payment.status}",
                "status": payment.status
            }, status=400)

        # Re-initialize HDFC payment order
        frontend_base = _get_frontend_base_url()
        
        # Determine gateway type and details
        type_str = "student" if payment_type == "student" else "school"
        
        # HDFC rejects a new session with a previously-used order_id.
        # Generate a unique order_id per attempt so retries work.
        hdfc_order_id = f"{payment.id}_{uuid.uuid4().hex[:8]}"
        return_url = f"{frontend_base}/api/payment/return/{hdfc_order_id}/{type_str}"

        try:
            gateway = get_payment_gateway()
            logger.info(f"[PaymentRetry] Resolved gateway: {gateway}")
            
            # Extract metadata for the gateway
            # If metadata was lost or empty, the gateway order might fail,
            # but we try to preserve what was there.
            m = payment.metadata or {}
            cust = m.get("customer") or {} # Some versions might store customer nested
            
            first_name = cust.get("first_name") or m.get("first_name", "")
            last_name = cust.get("last_name") or m.get("last_name", "")
            email = cust.get("email") or m.get("email", "")
            phone = cust.get("phone") or m.get("phone", "")
            address = cust.get("address") or m.get("address", "")
            state = cust.get("state") or m.get("billing_state", "")

            gateway_metadata = {
                "payment_id": payment.id,
                "order_id": hdfc_order_id,
                "type": type_str,
                "first_name": first_name or self.user_dto.first_name,
                "last_name": last_name or self.user_dto.last_name,
                "email": email or self.user_dto.email,
                "phone": phone,
                "address": address,
                "state": state,
                "return_url": return_url,
            }
            
            logger.info(f"[PaymentRetry] Re-initializing HDFC session for payment {payment.id} with new order_id {hdfc_order_id}")
            
            gateway_response = gateway.create_payment_order(
                amount=Decimal(str(payment.amount)),
                currency=payment.currency or PAYMENT_CURRENCY,
                metadata=gateway_metadata
            )
            
            # Update payment record with new gateway details
            payment.order_id = hdfc_order_id
            # Gateway returns 'transaction_id', not 'gateway_transaction_id'
            payment.gateway_transaction_id = gateway_response.get("transaction_id", "") or gateway_response.get("gateway_transaction_id", "")
            payment.save()

            payment_links = gateway_response.get("payment_links", {})
            logger.info(f"[PaymentRetry] Raw gateway_response keys: {list(gateway_response.keys())}")
            logger.info(f"[PaymentRetry] Payment links: {payment_links}")
            
            # Try web link first, then iframe, then top-level web key
            payment_url = (
                payment_links.get("web")
                or payment_links.get("iframe")
                or gateway_response.get("web")
            )
            
            if not payment_url:
                 logger.error(f"[PaymentRetry] Gateway did not return a payment URL for payment {payment.id}")
                 return Response({"error": "Gateway did not return a payment URL"}, status=500)

            logger.info(f"[PaymentRetry] Successfully re-initialized payment {payment.id}. New txn ID: {payment.gateway_transaction_id}")

            return Response({
                "payment_id": payment.id,
                "payment_url": payment_url,
                "gateway_transaction_id": payment.gateway_transaction_id,
                "order_id": hdfc_order_id
            })

        except Exception as e:
            logger.exception(f"[PaymentRetry] Failed to re-initialize HDFC session for payment {payment.id}: {e}")
            return Response({"error": "Failed to re-initialize payment session. Please try again later."}, status=500)


# ---------------------------------------------------------------------------
# Payment status check — called by frontend after HDFC redirect
# ---------------------------------------------------------------------------

class PaymentStatusView(UserDTOView):
    """
    Check payment status and auto-confirm if HDFC reports success.
    
    Called by the frontend payment status page after HDFC redirects back.
    Verifies with HDFC, updates status, and provisions subscriptions.
    """

    def get(self, request: Request, payment_id: int) -> Response:
        payment_type = request.query_params.get("type", "student")

        logger.info(
            f"[PaymentStatus] Received request: payment_id={payment_id}, "
            f"type={payment_type}, user_id={self.user_dto.id}, "
            f"query_params={dict(request.query_params)}"
        )

        if payment_type == "school":
            return self._handle_school_payment(payment_id)
        else:
            return self._handle_student_payment(payment_id)

    def _handle_student_payment(self, payment_id: int) -> Response:
        try:
            payment = UserPayment.objects.get(id=payment_id, user_id=self.user_dto.id)
        except UserPayment.DoesNotExist:
            logger.warning(
                f"[PaymentStatus] Student payment not found: payment_id={payment_id}, "
                f"user_id={self.user_dto.id}"
            )
            return Response({"error": "Payment not found"}, status=404)

        logger.info(
            f"[PaymentStatus] Student payment found: payment_id={payment.id}, "
            f"status={payment.status}, gateway_txn_id={payment.gateway_transaction_id}, "
            f"amount={payment.amount}, modules={payment.modules_purchased}, "
            f"metadata={payment.metadata}"
        )

        # Already completed — just return status
        if payment.status == UserPayment.Status.COMPLETED:
            logger.info(f"[PaymentStatus] Payment {payment.id} already completed")
            return Response({
                "payment_id": payment.id,
                "status": "completed",
                "message": "Payment already completed",
                "amount": payment.amount,
                "currency": payment.currency or "INR",
            })

        if payment.status == UserPayment.Status.FAILED:
            logger.info(f"[PaymentStatus] Payment {payment.id} already failed")
            return Response({
                "payment_id": payment.id,
                "status": "failed",
                "message": "Payment failed",
                "amount": payment.amount,
                "currency": payment.currency or "INR",
            })

        # Still pending — verify with HDFC
        if payment.status == UserPayment.Status.PENDING:
            order_id = payment.order_id or str(payment.id)
            txn_id = payment.gateway_transaction_id
            logger.info(
                f"[PaymentStatus] Verifying pending payment {payment.id} with HDFC: "
                f"order_id={order_id}, txn_id={txn_id}"
            )

            try:
                gateway = get_payment_gateway()
                result = gateway.verify_payment(order_id=order_id, transaction_id=txn_id)
            except Exception as e:
                logger.error(
                    f"[PaymentStatus] Gateway verify_payment exception for payment {payment.id}: {e}",
                    exc_info=True,
                )
                return Response({
                    "payment_id": payment.id,
                    "status": "pending",
                    "message": "Payment verification temporarily unavailable. Please wait.",
                    "amount": payment.amount,
                    "currency": payment.currency or "INR",
                })

            logger.info(
                f"[PaymentStatus] HDFC verify result for payment {payment.id}: "
                f"hdfc_status={result.get('status')}, verified={result.get('verified')}"
            )

            if result.get("verified"):
                payment.set_status(UserPayment.Status.COMPLETED)
                payment.metadata["verification"] = _slim_gateway_verification(result.get("gateway_response", {}))
                payment.save()
                _provision_user_subscriptions(payment)
                _send_payment_status_email(payment, "completed")
                logger.info(f"[PaymentStatus] Payment {payment.id} completed and subscriptions provisioned")

                return Response({
                    "payment_id": payment.id,
                    "status": "completed",
                    "message": "Payment successful! Your modules are now active.",
                    "amount": payment.amount,
                    "currency": payment.currency or "INR",
                })
            else:
                hdfc_status = result.get("status", "UNKNOWN")
                logger.warning(
                    f"[PaymentStatus] Payment {payment.id} not verified: hdfc_status={hdfc_status}"
                )
                if hdfc_status in HDFC_TERMINAL_FAILURE_STATUSES:
                    payment.set_status(UserPayment.Status.FAILED)
                    payment.metadata["verification"] = _slim_gateway_verification(result.get("gateway_response", {}))
                    payment.save()
                    _send_payment_status_email(payment, "failed", gateway_status=hdfc_status)
                    return Response({
                        "payment_id": payment.id,
                        "status": "failed",
                        "message": "Payment was not successful. Please try again.",
                        "amount": payment.amount,
                        "currency": payment.currency or "INR",
                    })

                # Still pending at HDFC
                return Response({
                    "payment_id": payment.id,
                    "status": "pending",
                    "message": "Payment is being processed. Please wait.",
                    "amount": payment.amount,
                    "currency": payment.currency or "INR",
                })

        return Response({
            "payment_id": payment.id,
            "status": payment.status,
            "message": f"Payment status: {payment.status}",
            "amount": payment.amount,
            "currency": payment.currency or "INR",
        })

    def _handle_school_payment(self, payment_id: int) -> Response:
        if self.user_dto.role != UserRole.SCHOOLADMIN or self.user_dto.school_id is None:
            logger.warning(
                f"[PaymentStatus] School payment permission denied: "
                f"role={self.user_dto.role}, school_id={self.user_dto.school_id}"
            )
            raise PermissionDenied(detail="Only school admins can use this endpoint")

        try:
            payment = SchoolPayment.objects.get(id=payment_id, school_id=self.user_dto.school_id)
        except SchoolPayment.DoesNotExist:
            logger.warning(
                f"[PaymentStatus] School payment not found: payment_id={payment_id}, "
                f"school_id={self.user_dto.school_id}"
            )
            return Response({"error": "Payment not found"}, status=404)

        logger.info(
            f"[PaymentStatus] School payment found: payment_id={payment.id}, "
            f"status={payment.status}, gateway_txn_id={payment.gateway_transaction_id}, "
            f"amount={payment.amount}, modules={payment.modules_purchased}, "
            f"metadata={payment.metadata}"
        )

        if payment.status == SchoolPayment.Status.COMPLETED:
            logger.info(f"[PaymentStatus] School payment {payment.id} already completed")
            return Response({
                "payment_id": payment.id,
                "status": "completed",
                "message": "Payment already completed",
                "amount": payment.amount,
                "currency": payment.currency or "INR",
            })

        if payment.status == SchoolPayment.Status.FAILED:
            logger.info(f"[PaymentStatus] School payment {payment.id} already failed")
            return Response({
                "payment_id": payment.id,
                "status": "failed",
                "message": "Payment failed",
                "amount": payment.amount,
                "currency": payment.currency or "INR",
            })

        if payment.status == SchoolPayment.Status.PENDING:
            order_id = payment.order_id or str(payment.id)
            txn_id = payment.gateway_transaction_id
            logger.info(
                f"[PaymentStatus] Verifying pending school payment {payment.id} with HDFC: "
                f"order_id={order_id}, txn_id={txn_id}"
            )

            try:
                gateway = get_payment_gateway()
                result = gateway.verify_payment(order_id=order_id, transaction_id=txn_id)
            except Exception as e:
                logger.error(
                    f"[PaymentStatus] Gateway verify_payment exception for school payment {payment.id}: {e}",
                    exc_info=True,
                )
                return Response({
                    "payment_id": payment.id,
                    "status": "pending",
                    "message": "Payment verification temporarily unavailable. Please wait.",
                    "amount": payment.amount,
                    "currency": payment.currency or "INR",
                })

            logger.info(
                f"[PaymentStatus] HDFC verify result for school payment {payment.id}: "
                f"hdfc_status={result.get('status')}, verified={result.get('verified')}"
            )

            if result.get("verified"):
                payment.set_status(SchoolPayment.Status.COMPLETED)
                payment.metadata["verification"] = _slim_gateway_verification(result.get("gateway_response", {}))
                payment.save()
                _provision_school_subscriptions_with_students(payment)
                _send_payment_status_email(payment, "completed")
                logger.info(f"[PaymentStatus] School payment {payment.id} completed and subscriptions provisioned")

                return Response({
                    "payment_id": payment.id,
                    "status": "completed",
                    "message": "Payment successful! School modules are now active.",
                    "amount": payment.amount,
                    "currency": payment.currency or "INR",
                })
            else:
                hdfc_status = result.get("status", "UNKNOWN")
                logger.warning(
                    f"[PaymentStatus] School payment {payment.id} not verified: hdfc_status={hdfc_status}"
                )
                if hdfc_status in HDFC_TERMINAL_FAILURE_STATUSES:
                    payment.set_status(SchoolPayment.Status.FAILED)
                    payment.metadata["verification"] = _slim_gateway_verification(result.get("gateway_response", {}))
                    payment.save()
                    _send_payment_status_email(payment, "failed", gateway_status=hdfc_status)
                    return Response({
                        "payment_id": payment.id,
                        "status": "failed",
                        "message": "Payment was not successful. Please try again.",
                        "amount": payment.amount,
                        "currency": payment.currency or "INR",
                    })

                return Response({
                    "payment_id": payment.id,
                    "status": "pending",
                    "message": "Payment is being processed. Please wait.",
                    "amount": payment.amount,
                    "currency": payment.currency or "INR",
                })

        return Response({
            "payment_id": payment.id,
            "status": payment.status,
            "message": f"Payment status: {payment.status}",
            "amount": payment.amount,
            "currency": payment.currency or "INR",
        })


class GuestPaymentStatusView(APIView):
    """
    Check payment status for guest (unauthenticated) checkouts.

    Security: payment lookup requires both payment_id (integer) and the
    order_id (contains an unguessable random hex component).
    """
    allow_public = True

    def get(self, request: Request, payment_id: int) -> Response:
        order_id = request.query_params.get("order_id", "")
        if not order_id:
            return Response({"error": "order_id query parameter is required"}, status=400)

        try:
            payment = UserPayment.objects.get(id=payment_id)
        except UserPayment.DoesNotExist:
            return Response({"error": "Payment not found"}, status=404)

        # Verify the order_id matches what's stored
        stored_order_id = payment.order_id
        if not stored_order_id or stored_order_id != order_id:
            return Response({"error": "Payment not found"}, status=404)

        # Already terminal
        if payment.status == UserPayment.Status.COMPLETED:
            return Response({
                "payment_id": payment.id,
                "status": "completed",
                "message": "Payment successful! Your modules are now active.",
                "amount": payment.amount,
                "currency": payment.currency or "INR",
            })

        if payment.status == UserPayment.Status.FAILED:
            return Response({
                "payment_id": payment.id,
                "status": "failed",
                "message": "Payment was not successful. Please try again.",
                "amount": payment.amount,
                "currency": payment.currency or "INR",
            })

        # Pending — verify with HDFC
        if payment.status == UserPayment.Status.PENDING:
            txn_id = payment.gateway_transaction_id
            try:
                gateway = get_payment_gateway()
                result = gateway.verify_payment(order_id=stored_order_id, transaction_id=txn_id)
            except Exception as e:
                logger.error(
                    f"[GuestPaymentStatus] verify_payment exception for payment {payment.id}: {e}",
                    exc_info=True,
                )
                return Response({
                    "payment_id": payment.id,
                    "status": "pending",
                    "message": "Payment verification temporarily unavailable. Please wait.",
                    "amount": payment.amount,
                    "currency": payment.currency or "INR",
                })

            if result.get("verified"):
                payment.set_status(UserPayment.Status.COMPLETED)
                payment.metadata["verification"] = _slim_gateway_verification(result.get("gateway_response", {}))
                payment.save()
                _provision_user_subscriptions(payment)
                _send_payment_status_email(payment, "completed")
                return Response({
                    "payment_id": payment.id,
                    "status": "completed",
                    "message": "Payment successful! Your modules are now active.",
                    "amount": payment.amount,
                    "currency": payment.currency or "INR",
                })

            hdfc_status = result.get("status", "UNKNOWN")
            logger.info(
                f"[GuestPaymentStatus] HDFC verify result for payment {payment.id}: "
                f"hdfc_status={hdfc_status}, verified={result.get('verified')}"
            )
            if hdfc_status in HDFC_TERMINAL_FAILURE_STATUSES:
                payment.set_status(UserPayment.Status.FAILED)
                payment.metadata["verification"] = _slim_gateway_verification(result.get("gateway_response", {}))
                payment.save()
                _send_payment_status_email(payment, "failed", gateway_status=hdfc_status)
                return Response({
                    "payment_id": payment.id,
                    "status": "failed",
                    "message": "Payment was not successful. Please try again.",
                    "amount": payment.amount,
                    "currency": payment.currency or "INR",
                })

            return Response({
                "payment_id": payment.id,
                "status": "pending",
                "message": "Payment is being processed. Please wait.",
                "amount": payment.amount,
                "currency": payment.currency or "INR",
            })

        return Response({
            "payment_id": payment.id,
            "status": payment.status,
            "message": f"Payment status: {payment.status}",
            "amount": payment.amount,
            "currency": payment.currency or "INR",
        })


# ---------------------------------------------------------------------------
# Payment return — unauthenticated endpoint called by the frontend Route
# Handler after HDFC redirects back.  Verifies the payment with HDFC,
# updates the record, provisions subscriptions, and returns the result
# so the Route Handler can redirect the browser to the status page.
# ---------------------------------------------------------------------------

class PaymentReturnVerifyView(APIView):
    """
    Verify a payment after HDFC redirects back.

    This endpoint is unauthenticated.  Security is provided by the
    order_id which is unguessable (``{payment_id}_{random_hex}``).
    The frontend Next.js Route Handler calls this server-to-server,
    then redirects the browser to the status page with the result.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request: Request, order_id: str, payment_type: str) -> Response:
        if payment_type not in ("student", "school"):
            return Response({"payment_id": None, "status": "error", "type": payment_type}, status=400)

        payment = self._find_payment(order_id, payment_type)
        if payment is None:
            logger.warning(f"[PaymentReturn] Payment not found for order_id={order_id}")
            return Response({"payment_id": None, "status": "not_found", "type": payment_type}, status=404)

        status_cls = payment.Status

        # Already terminal — return immediately
        if payment.status in (status_cls.COMPLETED, status_cls.FAILED):
            res_data = {
                "payment_id": payment.id,
                "status": "completed" if payment.status == status_cls.COMPLETED else "failed",
                "type": payment_type,
                "amount": payment.amount,
                "currency": payment.currency or "INR",
            }
            # Include cart details for failure flow to allow immediate retry
            if payment.status == status_cls.FAILED:
                res_data["modules"] = ",".join(m["module"] for m in payment.modules_purchased)
                res_data["billing_state"] = (payment.metadata or {}).get("billing_state", "")

            return Response(res_data)

        # Verify with HDFC
        stored_order_id = payment.order_id or str(payment.id)
        try:
            gateway = get_payment_gateway()
            result = gateway.verify_payment(
                order_id=stored_order_id,
                transaction_id=payment.gateway_transaction_id,
            )
        except Exception as e:
            logger.error(f"[PaymentReturn] verify_payment exception for order_id={order_id}: {e}", exc_info=True)
            return Response({"payment_id": payment.id, "status": "pending", "type": payment_type, "amount": payment.amount, "currency": payment.currency or "INR"})

        hdfc_status = result.get("status", "UNKNOWN")
        logger.info(
            f"[PaymentReturn] HDFC verify result for payment {payment.id}: "
            f"hdfc_status={hdfc_status}, verified={result.get('verified')}, "
            f"gateway_response={result.get('gateway_response', {})}"
        )

        if result.get("verified"):
            payment.set_status(status_cls.COMPLETED)
            payment.metadata["verification"] = _slim_gateway_verification(result.get("gateway_response", {}))
            payment.save()
            if payment_type == "student":
                _provision_user_subscriptions(payment)
            else:
                _provision_school_subscriptions_with_students(payment)
            _send_payment_status_email(payment, "completed")
            logger.info(f"[PaymentReturn] Payment {payment.id} completed via return flow")
            return Response({
                "payment_id": payment.id,
                "status": "completed",
                "type": payment_type,
                "amount": payment.amount,
                "currency": payment.currency or "INR"
            })

        # User is already back from the gateway — any non-success status
        # means the payment will not complete.  Mark it failed so the
        # frontend shows the failure screen immediately.
        logger.warning(
            f"[PaymentReturn] Payment {payment.id} not successful on return: "
            f"hdfc_status={hdfc_status}, marking as failed"
        )
        payment.set_status(status_cls.FAILED)
        payment.metadata["verification"] = _slim_gateway_verification(result.get("gateway_response", {}))
        payment.save()
        _send_payment_status_email(payment, "failed", gateway_status=hdfc_status)
        return Response({
            "payment_id": payment.id,
            "status": "failed",
            "type": payment_type,
            "amount": payment.amount,
            "currency": payment.currency or "INR",
            "modules": ",".join(m["module"] for m in payment.modules_purchased),
            "billing_state": (payment.metadata or {}).get("billing_state", ""),
        })

    @staticmethod
    def _find_payment(order_id: str, payment_type: str):
        """Look up a payment by parsing the payment_id from order_id and verifying the full value."""
        parts = order_id.split("_", 1)
        if not parts or not parts[0].isdigit():
            return None
        payment_id = int(parts[0])

        Model = UserPayment if payment_type == "student" else SchoolPayment
        try:
            payment = Model.objects.get(id=payment_id)
        except Model.DoesNotExist:
            return None

        # Verify the full order_id matches (prevents guessing payment IDs)
        if payment.order_id != order_id:
            return None
        return payment


# ---------------------------------------------------------------------------
# Module Pricing CRUD (admin only)
# ---------------------------------------------------------------------------

class ModulePricingListCreateView(UserDTOView):
    """List all module pricing rows or create a new one (admin only)."""

    def _require_admin(self) -> None:
        if self.user_dto.role not in (UserRole.SUPERADMIN, UserRole.OPERATIONADMIN):
            raise PermissionDenied(detail="Admin access required")

    def get(self, request: Request) -> Response:
        self._require_admin()
        qs = ModulePricing.objects.select_related("school", "user").order_by("module_name", "school", "user")

        module_name = request.query_params.get("module_name")
        school_id = request.query_params.get("school_id")
        user_id = request.query_params.get("user_id")
        scope = request.query_params.get("scope")  # "global", "school", "user"

        if module_name:
            qs = qs.filter(module_name=module_name)
        if school_id:
            qs = qs.filter(school_id=school_id)
        if user_id:
            qs = qs.filter(user_id=user_id)
        if scope == "global":
            qs = qs.filter(school__isnull=True, user__isnull=True)
        elif scope == "school":
            qs = qs.filter(school__isnull=False)
        elif scope == "user":
            qs = qs.filter(user__isnull=False)

        serializer = ModulePricingSerializer(qs, many=True)
        return Response({"pricing": serializer.data, "total": qs.count()}, status=200)

    def post(self, request: Request) -> Response:
        self._require_admin()
        serializer = ModulePricingSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class ModulePricingDetailView(UserDTOView):
    """Retrieve, update, or delete a single module pricing row (admin only)."""

    def _require_admin(self) -> None:
        if self.user_dto.role not in (UserRole.SUPERADMIN, UserRole.OPERATIONADMIN):
            raise PermissionDenied(detail="Admin access required")

    def get(self, request: Request, pricing_id: int) -> Response:
        self._require_admin()
        try:
            pricing = ModulePricing.objects.select_related("school", "user").get(id=pricing_id)
        except ModulePricing.DoesNotExist:
            return Response({"error": "Pricing not found"}, status=404)
        return Response(ModulePricingSerializer(pricing).data, status=200)

    def patch(self, request: Request, pricing_id: int) -> Response:
        self._require_admin()
        try:
            pricing = ModulePricing.objects.get(id=pricing_id)
        except ModulePricing.DoesNotExist:
            return Response({"error": "Pricing not found"}, status=404)
        serializer = ModulePricingSerializer(pricing, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=200)
        return Response(serializer.errors, status=400)

    def delete(self, request: Request, pricing_id: int) -> Response:
        self._require_admin()
        try:
            pricing = ModulePricing.objects.get(id=pricing_id)
        except ModulePricing.DoesNotExist:
            return Response({"error": "Pricing not found"}, status=404)
        pricing.delete()
        return Response(status=204)


class ModulePricingPublicView(UserDTOView):
    """Return resolved prices for the current user context (for frontend checkout)."""

    def get(self, request: Request) -> Response:
        school_id = self.user_dto.school_id
        user_id = self.user_dto.id
        currency = "INR"

        if school_id:
            school = School.objects.filter(id=school_id).first()
            if school and school.currency:
                currency = school.currency

        price_map = get_all_module_prices(school_id=school_id, user_id=user_id, currency=currency)
        return Response({
            "prices": price_map,
            "currency": currency,
            "default_price": DEFAULT_MODULE_PRICE,
        }, status=200)




# ---------------------------------------------------------------------------
# Coupon Management APIs (Admin Only)
# ---------------------------------------------------------------------------

class AdminCouponListCreateView(UserDTOView):
    """List all coupons or create a new one (admin only)."""
    def get(self, request: Request) -> Response:
        user_role = self.user_dto.role
        if user_role not in [User.Role.SUPERADMIN, User.Role.OPERATIONADMIN]:
            return Response({"error": "Unauthorized"}, status=403)
            
        # Optional: filter by code availability (used by frontend while typing)
        code_to_check = request.query_params.get("code")
        if code_to_check:
            exists = Coupon.objects.filter(code__iexact=code_to_check).exists()
            return Response({"total": 1 if exists else 0}, status=200)

        qs = Coupon.objects.all().order_by("-created_at")
        serializer = CouponSerializer(qs, many=True)
        return Response({"coupons": serializer.data, "total": qs.count()}, status=200)

    def post(self, request: Request) -> Response:
        user_role = self.user_dto.role
        if user_role not in [User.Role.SUPERADMIN, User.Role.OPERATIONADMIN]:
            return Response({"error": "Unauthorized"}, status=403)
        
        serializer = CouponSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class AdminCouponDetailView(UserDTOView):
    """Retrieve, update or delete a coupon (admin only)."""
    def get(self, request: Request, coupon_id: int) -> Response:
        user_role = self.user_dto.role
        if user_role not in [User.Role.SUPERADMIN, User.Role.OPERATIONADMIN]:
            return Response({"error": "Unauthorized"}, status=403)
        try:
            coupon = Coupon.objects.get(id=coupon_id)
        except Coupon.DoesNotExist:
            return Response({"error": "Coupon not found"}, status=404)
        return Response(CouponSerializer(coupon).data, status=200)

    def patch(self, request: Request, coupon_id: int) -> Response:
        user_role = self.user_dto.role
        if user_role not in [User.Role.SUPERADMIN, User.Role.OPERATIONADMIN]:
            return Response({"error": "Unauthorized"}, status=403)
        try:
            coupon = Coupon.objects.get(id=coupon_id)
        except Coupon.DoesNotExist:
            return Response({"error": "Coupon not found"}, status=404)
        
        serializer = CouponSerializer(coupon, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=200)
        return Response(serializer.errors, status=400)

    def delete(self, request: Request, coupon_id: int) -> Response:
        user_role = self.user_dto.role
        if user_role not in [User.Role.SUPERADMIN, User.Role.OPERATIONADMIN]:
            return Response({"error": "Unauthorized"}, status=403)
        try:
            coupon = Coupon.objects.get(id=coupon_id)
            coupon.delete()
            return Response(status=204)
        except Coupon.DoesNotExist:
            return Response({"error": "Coupon not found"}, status=404)


class CouponValidatePublicView(APIView):
    """Publicly validate a coupon code for students during checkout."""
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        code = request.data.get("code")
        amount = request.data.get("amount", 0)
        if not code:
            return Response({"error": "Code is required"}, status=400)
        
        try:
            coupon = Coupon.objects.get(code__iexact=code.strip())
            amount_val = float(amount)
            logger.info(f"[Coupon] Validating code '{code}' for amount {amount_val}")
            is_valid, message = coupon.is_valid(amount=amount_val)
            if not is_valid:
                return Response({"error": message}, status=400)
            
            return Response({
                "valid": True,
                "code": coupon.code,
                "voucher_type": coupon.voucher_type,
                "voucher_value": float(coupon.voucher_value),
                "min_booking_amount": float(coupon.min_booking_amount) if coupon.min_booking_amount else None,
            }, status=200)
        except Coupon.DoesNotExist:
            return Response({"error": "Invalid coupon code"}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=500)
