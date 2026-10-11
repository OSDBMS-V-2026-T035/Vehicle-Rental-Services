from django.db import InterfaceError, OperationalError
from django.http import JsonResponse


class ApiDatabaseErrorMiddleware:
    """Keep API failures machine-readable when MySQL is unavailable."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except (InterfaceError, OperationalError) as exception:
            response = self._database_error_response(request, exception)
            if response is not None:
                return response
            raise

    def process_exception(self, request, exception):
        return self._database_error_response(request, exception)

    @staticmethod
    def _database_error_response(request, exception=None):
        if request.path.startswith("/api/") and isinstance(exception, (InterfaceError, OperationalError)):
            return JsonResponse(
                {
                    "ok": False,
                    "message": (
                        "RideHub database is unavailable. Start MySQL 8.4 and "
                        "verify MYSQL_DATABASE, MYSQL_USER, and MYSQL_PASSWORD in .env."
                    ),
                },
                status=503,
            )
        return None
