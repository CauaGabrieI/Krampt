import re


CHAVE_IDEMPOTENCIA_RE = re.compile(r"^[A-Za-z0-9:_-]{8,64}$")
VALORES_TRUE = {"1", "true", "on", "yes"}
VALORES_FALSE = {"0", "false", "off", "no"}


def obter_chave_idempotencia(request):
    chave = (request.POST.get("idempotency_key") or "").strip()
    if not chave or not CHAVE_IDEMPOTENCIA_RE.fullmatch(chave):
        return None
    return chave


def obter_estado_desejado(request):
    valor = (request.POST.get("desired_state") or "").strip().lower()
    if valor in VALORES_TRUE:
        return True
    if valor in VALORES_FALSE:
        return False
    return None
