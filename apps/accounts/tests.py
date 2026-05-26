from django.test import TestCase, Client
from .models import User, EmailOTP
from .services import AccountsService


class AccountsServiceTest(TestCase):
    def test_create_user_success(self) -> None:
        success, msg = AccountsService.create_user("test@example.com")
        self.assertTrue(success)
        self.assertEqual(msg, "User created successfully")
        self.assertTrue(User.objects.filter(email="test@example.com").exists())
        self.assertTrue(
            EmailOTP.objects.filter(email="test@example.com", is_active=True).exists()
        )

    def test_create_user_duplicate(self) -> None:
        AccountsService.create_user("dup@example.com")
        success, msg = AccountsService.create_user("dup@example.com")
        self.assertFalse(success)
        self.assertIn("Error creating user", msg)

    def test_verify_otp_success(self) -> None:
        AccountsService.create_user("otp@example.com")
        otp = EmailOTP.objects.get(email="otp@example.com", is_active=True)
        valid, msg = AccountsService.verify_otp("otp@example.com", otp.code)
        self.assertTrue(valid)
        self.assertEqual(msg, "OTP verified successfully")
        user = User.objects.get(email="otp@example.com")
        self.assertTrue(user.is_active)

    def test_verify_otp_invalid(self) -> None:
        AccountsService.create_user("otp2@example.com")
        valid, msg = AccountsService.verify_otp("otp2@example.com", "wrongcode")
        self.assertFalse(valid)
        self.assertIn("Invalid OTP", msg)

    def test_request_password_reset(self) -> None:
        AccountsService.create_user("reset@example.com")
        success, msg = AccountsService.request_password_reset("reset@example.com")
        self.assertTrue(success)
        self.assertIn("OTP sent", msg)

    def test_reset_password_success(self) -> None:
        AccountsService.create_user("pwreset@example.com")
        otp = EmailOTP.objects.get(email="pwreset@example.com", is_active=True)
        AccountsService.verify_otp("pwreset@example.com", otp.code)  # Activate user
        # Request password reset
        AccountsService.request_password_reset("pwreset@example.com")
        otp2 = EmailOTP.objects.filter(
            email="pwreset@example.com", is_active=True
        ).last()
        if not otp2:
            self.fail("No OTP found for password reset")
        valid, msg = AccountsService.reset_password("pwreset@example.com", "newpass123")
        self.assertTrue(valid)
        self.assertIn("Password reset successfully", msg)
        user = User.objects.get(email="pwreset@example.com")
        self.assertTrue(user.check_password("newpass123"))


class AccountsViewTest(TestCase):
    def setUp(self) -> None:
        self.client = Client()

    def test_signup_view(self) -> None:
        url = "/api/accounts/signup/"
        resp = self.client.post(
            url, {"email": "signup@example.com"}, content_type="application/json"
        )
        self.assertEqual(resp.status_code, 201)
        self.assertIn("Signup successful", resp.json().get("message", ""))

    def test_otp_verify_view(self) -> None:
        AccountsService.create_user("otpview@example.com")
        otp = EmailOTP.objects.get(email="otpview@example.com", is_active=True)
        url = "/api/accounts/verify/"
        resp = self.client.post(
            url,
            {"email": "otpview@example.com", "code": otp.code},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("OTP verified", resp.json().get("message", ""))

    def test_login_view(self) -> None:
        AccountsService.create_user("login@example.com")
        otp = EmailOTP.objects.get(email="login@example.com", is_active=True)
        AccountsService.verify_otp("login@example.com", otp.code)
        user = User.objects.get(email="login@example.com")
        user.set_password("testpass")
        user.save()
        url = "/api/accounts/login/"
        resp = self.client.post(
            url,
            {"email": "login@example.com", "password": "testpass"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("token", resp.json())

    def test_password_reset_request_view(self) -> None:
        AccountsService.create_user("pwreq@example.com")
        url = "/api/accounts/password-reset/request/"
        resp = self.client.post(
            url, {"email": "pwreq@example.com"}, content_type="application/json"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("OTP sent", resp.json().get("message", ""))

    def test_password_reset_confirm_view(self) -> None:
        AccountsService.create_user("pwconf@example.com")
        otp = EmailOTP.objects.get(email="pwconf@example.com", is_active=True)
        AccountsService.verify_otp("pwconf@example.com", otp.code)
        AccountsService.request_password_reset("pwconf@example.com")
        otp2 = EmailOTP.objects.filter(
            email="pwconf@example.com", is_active=True
        ).last()
        if not otp2:
            self.fail("No OTP found for password reset")
        url = "/api/accounts/password-reset/confirm/"
        resp = self.client.post(
            url,
            {
                "email": "pwconf@example.com",
                "new_password": "pw12345",
                "code": otp2.code,
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Password reset successfully", resp.json().get("message", ""))
