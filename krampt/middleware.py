from django.contrib.auth.middleware import LoginRequiredMiddleware
from django.utils.cache import add_never_cache_headers


class AutenticacaoMiddleware(LoginRequiredMiddleware):
    """Exige sessão válida por requisição e evita cache das páginas HTML."""

    def process_response(self, request, response):
        if response.get("Content-Type", "").startswith("text/html"):
            add_never_cache_headers(response)
        return response
