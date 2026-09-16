from contextlib import contextmanager

from django.db import connection
from django.test.utils import CaptureQueriesContext


class QueryBudgetMixin:
    """Ajuda testes a detectar regressões N+1 sem prender o código a um número exato."""

    @contextmanager
    def assertMaxQueries(self, limite):
        with CaptureQueriesContext(connection) as consultas:
            yield

        total = len(consultas)
        if total > limite:
            sql = "\n\n".join(
                consulta["sql"]
                for consulta in consultas.captured_queries
            )
            self.fail(
                f"Orçamento de queries excedido: {total} > {limite}.\n\n{sql}"
            )
