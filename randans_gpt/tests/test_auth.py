import unittest
from unittest.mock import patch

from backend.auth import EMAIL_CONFIRM_REDIRECT, RATE_LIMIT_MESSAGE, SupabaseAuth


class SupabaseAuthErrorTests(unittest.TestCase):
    def test_rate_limit_is_not_reported_as_an_expired_session(self):
        error = SupabaseAuth._error(429, {"message": "Email rate limit exceeded"})

        self.assertEqual(error.code, "rate_limit")
        self.assertEqual(str(error), RATE_LIMIT_MESSAGE)

    def test_signup_redirects_confirmation_email_to_hosted_page(self):
        auth = SupabaseAuth(config={"url": "", "anon_key": ""})
        with patch.object(auth, "_call", return_value={}) as call:
            result = auth.sign_up("friend@example.com", "password123")

        self.assertTrue(result["needs_confirmation"])
        self.assertEqual(call.call_args.args[3], {"redirect_to": EMAIL_CONFIRM_REDIRECT})

    def test_signup_uses_configured_confirmation_redirect(self):
        redirect = "https://example.com/confirmed"
        auth = SupabaseAuth(config={"email_redirect_url": redirect})
        with patch.object(auth, "_call", return_value={}) as call:
            auth.sign_up("friend@example.com", "password123")

        self.assertEqual(call.call_args.args[3], {"redirect_to": redirect})

    def test_resend_uses_confirmation_redirect(self):
        auth = SupabaseAuth(config={"url": "", "anon_key": ""})
        with patch.object(auth, "_call") as call:
            result = auth.resend("friend@example.com")

        self.assertTrue(result["ok"])
        self.assertEqual(call.call_args.args[3], {"redirect_to": EMAIL_CONFIRM_REDIRECT})


if __name__ == "__main__":
    unittest.main()
