from .models import PreferenciasUsuario


def preferencias_interface(request):
    if not request.user.is_authenticated:
        return {}
    preferencias, _ = PreferenciasUsuario.objects.get_or_create(usuario=request.user)
    return {"preferencias_interface": preferencias}
