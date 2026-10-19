from django.db import NotSupportedError
from django.test import RequestFactory, SimpleTestCase

from .middleware import ApiDatabaseErrorMiddleware


class ApiDatabaseErrorMiddlewareTests(SimpleTestCase):
    def test_returns_json_for_an_unsupported_database_server(self):
        middleware = ApiDatabaseErrorMiddleware(lambda request: (_ for _ in ()).throw(NotSupportedError("old MySQL")))

        response = middleware(RequestFactory().post("/api/auth/login/"))

        self.assertEqual(response.status_code, 503)
        self.assertJSONEqual(
            response.content,
            {
                "ok": False,
                "message": (
                    "RideHub database is unavailable or unsupported. Start MySQL 8.4 "
                    "and verify MYSQL_HOST, MYSQL_PORT, MYSQL_DATABASE, MYSQL_USER, "
                    "and MYSQL_PASSWORD in .env."
                ),
            },
        )
