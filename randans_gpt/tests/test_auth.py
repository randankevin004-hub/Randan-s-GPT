import unittest

from backend.auth import RATE_LIMIT_MESSAGE, SupabaseAuth


class SupabaseAuthErrorTests(unittest.TestCase):
    def test_rate_limit_is_not_reported_as_an_expired_session(self):
        error = SupabaseAuth._error(429, {"message": "Email rate limit exceeded"})

        self.assertEqual(error.code, "rate_limit")
        self.assertEqual(str(error), RATE_LIMIT_MESSAGE)


if __name__ == "__main__":
    unittest.main()
