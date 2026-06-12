"""
Payment Gateway Service for HDFC HyperCheckout Integration

This module handles all payment gateway operations, abstracting the specific
gateway implementation to make it easy to switch or add multiple gateways.
"""

import logging
import hashlib
import hmac
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from decimal import Decimal

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class PaymentGatewayException(Exception):
    """Base exception for payment gateway errors."""
    pass


class PaymentGateway(ABC):
    """Abstract base class for payment gateway implementations."""

    @abstractmethod
    def create_payment_order(self, amount: Decimal, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a payment order in the gateway.
        
        Args:
            amount: Payment amount
            currency: Currency code (e.g., "INR")
            metadata: Additional metadata for the payment
            
        Returns:
            Dictionary containing order_id, transaction_id, and other gateway-specific info
        """
        pass

    @abstractmethod
    def verify_payment(self, order_id: str, transaction_id: str, signature: Optional[str] = None) -> Dict[str, Any]:
        """
        Verify a completed payment.
        
        Args:
            order_id: Order ID from the payment gateway
            transaction_id: Transaction ID from the payment gateway
            signature: Payment signature for verification
            
        Returns:
            Dictionary with verification status and details
        """
        pass

    @abstractmethod
    def cancel_payment(self, transaction_id: str) -> Dict[str, Any]:
        """Cancel or refund a payment."""
        pass

    @abstractmethod
    def verify_webhook_signature(self, raw_body: bytes, received_signature: str) -> bool:
        """
        Verify the HMAC signature on an inbound webhook payload.

        Args:
            raw_body: The raw HTTP request body (bytes).
            received_signature: The signature sent by the gateway (e.g. x-signature header).

        Returns:
            True if the signature is valid, False otherwise.
        """
        pass


class HDFCPaymentGateway(PaymentGateway):
    """
    HDFC SmartGateway payment gateway implementation.
    
    Documentation: https://smartgateway.hdfcbank.com/docs/smartgateway-kits-integration/web/
    
    Key model (from SmartGateway Dashboard → Settings → Security):
    - HDFC_API_KEY        (private key) — authenticates outbound API calls via HTTP Basic Auth.
    - HDFC_RESPONSE_KEY   (response key) — verifies inbound webhook signatures via HMAC-SHA256.
    
    Other required settings:
    - HDFC_MERCHANT_ID: Your merchant ID
    - HDFC_PAYMENT_PAGE_CLIENT_ID: Client ID (sandbox: 'hdfcmaster')
    - HDFC_SANDBOX_MODE: Boolean for sandbox/production mode
    """

    BASE_URL_PROD = "https://smartgateway.hdfc.bank.in"
    BASE_URL_SANDBOX = "https://smartgateway.hdfcuat.bank.in"

    API_VERSION = "2024-02-01"

    def __init__(self):
        """Initialize HDFC gateway with configuration from settings."""
        self.merchant_id = getattr(settings, "HDFC_MERCHANT_ID", "")
        self.client_id = getattr(settings, "HDFC_PAYMENT_PAGE_CLIENT_ID", "hdfcmaster")
        # Private key — used to authenticate outbound API requests (HTTP Basic Auth username)
        self.api_key = getattr(settings, "HDFC_API_KEY", "")
        # Response key — used to verify HMAC-SHA256 signatures on inbound webhooks
        self.response_key = getattr(settings, "HDFC_RESPONSE_KEY", "")
        self.sandbox_mode = getattr(settings, "HDFC_SANDBOX_MODE", True)
        self.base_url = self.BASE_URL_SANDBOX if self.sandbox_mode else self.BASE_URL_PROD

        if not all([self.merchant_id, self.client_id, self.api_key]):
            logger.warning("HDFC payment gateway not fully configured. Check settings.")

    def verify_webhook_signature(self, raw_body: bytes, received_signature: str) -> bool:
        """
        Verify an inbound HDFC webhook using the response key (HMAC-SHA256).

        HDFC signs the raw request body and sends the hex-encoded signature
        in the ``x-signature`` HTTP header.
        """
        if not self.response_key:
            logger.error("HDFC_RESPONSE_KEY not configured — cannot verify webhook signature")
            return False
        expected = hmac.new(
            self.response_key.encode(),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, received_signature)

    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None, content_type: str = "application/json") -> Dict[str, Any]:
        """
        Make a request to HDFC API using HTTP Basic Auth.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            data: Request data (for POST/PUT)
            content_type: Content type for the request
            
        Returns:
            Response JSON as dictionary
            
        Raises:
            PaymentGatewayException: If request fails
        """
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Content-Type": content_type,
            "version": self.API_VERSION,
            "x-merchantid": self.merchant_id,
        }
        # HDFC uses HTTP Basic Auth with the API key
        auth = (self.api_key, "")

        try:
            if method.upper() == "POST":
                if content_type == "application/json":
                    response = requests.post(url, json=data, headers=headers, auth=auth, timeout=30)
                else:
                    response = requests.post(url, data=data, headers=headers, auth=auth, timeout=30)
            elif method.upper() == "GET":
                response = requests.get(url, params=data, headers=headers, auth=auth, timeout=30)
            else:
                raise PaymentGatewayException(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"HDFC API request failed: {str(e)}")
            raise PaymentGatewayException(f"Payment gateway error: {str(e)}")

    def create_payment_order(self, amount: Decimal, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a payment order with HDFC SmartGateway.
        
        This initiates a payment session that can be completed by the frontend SDK.
        
        Args:
            amount: Payment amount in major currency units (e.g. rupees for INR)
            currency: Currency code (e.g., "INR")
            metadata: Additional data including payment_id, user email, etc.
            
        Returns:
            Dictionary with:
            - order_id: HDFC order ID
            - transaction_id: Gateway transaction ID
            - amount: Amount as sent to HDFC
            - status: "pending"
            - metadata: Original metadata
        """
        try:
            # HDFC SmartGateway expects the amount in major currency units
            # (rupees for INR), e.g. "999.00" for ₹999.
            amount_str = f"{amount:.2f}"

            # Prepare session data for HDFC
            # See: https://smartgateway.hdfcbank.com/docs/smartgateway-kits-integration/web/
            # Use the caller-supplied order_id (unique per attempt) if present,
            # otherwise fall back to payment_id for backwards compatibility.
            hdfc_order_id = str(metadata.get("order_id", metadata.get("payment_id", "")))
            session_data = {
                "order_id": hdfc_order_id,
                "amount": amount_str,
                "customer_id": str(metadata.get("payment_id", "")),
                "customer_email": metadata.get("email", ""),
                "customer_phone": metadata.get("phone", ""),
                "payment_page_client_id": self.client_id,
                "action": "paymentPage",
                "return_url": metadata.get("return_url", ""),
            }

            # Create session via HDFC API
            response = self._make_request("POST", "/session", session_data)

            if response.get("status") in ("NEW", "CREATED", "new", "created") or response.get("payment_links"):
                order_id = response.get("order_id", response.get("id", str(metadata.get("payment_id", ""))))
                transaction_id = response.get("txn_id", response.get("id", str(metadata.get("payment_id", ""))))
                payment_links = response.get("payment_links", {})

                logger.info(f"HDFC session created: order_id={order_id}, txn_id={transaction_id}")

                return {
                    "order_id": order_id,
                    "transaction_id": transaction_id,
                    "amount": amount,
                    "currency": currency,
                    "status": "pending",
                    "metadata": metadata,
                    "gateway_response": response,
                    "payment_links": payment_links,
                }

            else:
                error_msg = response.get("error_message", response.get("status", "Session creation failed"))
                logger.error(f"HDFC session creation failed: {error_msg}")
                raise PaymentGatewayException(f"Failed to create payment session: {error_msg}")

        except Exception as e:
            logger.error(f"Error creating HDFC payment session: {str(e)}")
            raise PaymentGatewayException(f"Failed to create payment session: {str(e)}")

    def verify_payment(self, order_id: str, transaction_id: str, signature: Optional[str] = None) -> Dict[str, Any]:
        """
        Verify a completed payment with HDFC using order status API.
        """
        try:
            # Query HDFC for order status using GET /orders/{orderId}
            response = self._make_request("GET", f"/orders/{order_id}")

            if response:
                status = response.get("status", "UNKNOWN")
                is_success = status in ("CHARGED", "AUTO_REFUNDED")

                logger.info(f"Payment verified: order_id={order_id}, status={status}, verified={is_success}")

                return {
                    "verified": is_success,
                    "status": status,
                    "amount": response.get("amount"),
                    "order_id": response.get("order_id", order_id),
                    "message": "Payment verified successfully" if is_success else f"Payment status: {status}",
                    "gateway_response": response,
                }

            else:
                error_msg = response.get("message", "Verification failed")
                logger.warning(f"HDFC payment verification failed: {error_msg}")
                return {
                    "verified": False,
                    "status": "UNKNOWN",
                    "message": f"Verification error: {error_msg}",
                }

        except Exception as e:
            logger.error(f"Error verifying HDFC payment: {str(e)}")
            return {
                "verified": False,
                "status": "ERROR",
                "message": f"Verification error: {str(e)}",
            }

    def cancel_payment(self, transaction_id: str) -> Dict[str, Any]:
        """Cancel or refund a payment."""
        try:
            import uuid
            refund_data = {
                "order_id": transaction_id,
                "unique_request_id": str(uuid.uuid4()),
            }

            # Use /refunds endpoint with form-urlencoded content type
            response = self._make_request("POST", "/refunds", refund_data, content_type="application/x-www-form-urlencoded")

            if response.get("status") in ("SUCCESS", "PENDING"):
                logger.info(f"Payment refund initiated: {transaction_id}")
                return {
                    "success": True,
                    "refund_id": response.get("id", response.get("refund_id")),
                    "message": "Refund initiated successfully",
                }
            else:
                error_msg = response.get("error_message", response.get("status", "Refund failed"))
                logger.error(f"HDFC refund failed: {error_msg}")
                return {
                    "success": False,
                    "message": f"Refund error: {error_msg}",
                }

        except Exception as e:
            logger.error(f"Error canceling HDFC payment: {str(e)}")
            return {
                "success": False,
                "message": f"Cancellation error: {str(e)}",
            }


class DummyPaymentGateway(PaymentGateway):
    """
    Dummy/mock payment gateway for testing and development.
    Use only in development environments.
    """

    def create_payment_order(self, amount: Decimal, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a fake payment order."""
        logger.info(f"DUMMY: Creating payment order for {currency} {amount}")
        return {
            "order_id": f"DUMMY_ORDER_{metadata.get('payment_id', 'unknown')}",
            "transaction_id": f"DUMMY_TXN_{metadata.get('payment_id', 'unknown')}",
            "amount": amount,
            "currency": currency,
            "status": "pending",
            "metadata": metadata,
        }

    def verify_payment(self, order_id: str, transaction_id: str, signature: Optional[str] = None) -> Dict[str, Any]:
        """Verify a fake payment (always succeeds)."""
        logger.info(f"DUMMY: Verifying payment {transaction_id}")
        return {
            "verified": True,
            "status": "SUCCESS",
            "message": "Dummy payment verified",
        }

    def cancel_payment(self, transaction_id: str) -> Dict[str, Any]:
        """Cancel a fake payment."""
        logger.info(f"DUMMY: Canceling payment {transaction_id}")
        return {
            "success": True,
            "message": "Dummy payment canceled",
        }

    def verify_webhook_signature(self, raw_body: bytes, received_signature: str) -> bool:
        """Dummy gateway always accepts webhooks."""
        return True


def get_payment_gateway() -> PaymentGateway:
    """
    Factory function to get the appropriate payment gateway instance.
    
    Returns:
        PaymentGateway instance based on Django settings
    """
    gateway_type = getattr(settings, "PAYMENT_GATEWAY", "hdfc").lower()

    if gateway_type == "hdfc":
        return HDFCPaymentGateway()
    elif gateway_type == "dummy":
        return DummyPaymentGateway()
    else:
        logger.warning(f"Unknown payment gateway type: {gateway_type}, using HDFC")
        return HDFCPaymentGateway()
