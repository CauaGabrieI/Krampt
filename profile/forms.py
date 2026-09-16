from django import forms

from posts.services import validar_limites_da_imagem

from .models import DenunciaUsuario

def validar_foto(foto):
    if foto.size > 5 * 1024 * 1024:
        raise forms.ValidationError("A foto deve ter no máximo 5 MB.")
    if foto.image.format not in {"JPEG", "PNG", "WEBP"}:
        raise forms.ValidationError("Use uma imagem JPG, PNG ou WebP.")
    dentro_do_limite, mensagem = validar_limites_da_imagem(foto)
    if not dentro_do_limite:
        raise forms.ValidationError(mensagem)
    return foto


class EditarPerfilForm(forms.Form):
    nome = forms.CharField(max_length=150, label="Nome", widget=forms.TextInput(attrs={"autocomplete": "given-name", "placeholder": " "}))
    biografia = forms.CharField(
        max_length=160,
        required=False,
        label="Bio",
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": " "}),
    )
    foto = forms.ImageField(
        required=False,
        label="Foto de perfil",
        widget=forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
    )
    remover_foto = forms.BooleanField(required=False, label="Remover foto atual")
    banner = forms.ImageField(
        required=False,
        label="Banner do perfil",
        widget=forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
    )
    remover_banner = forms.BooleanField(required=False, label="Remover banner atual")

    def clean_foto(self):
        foto = self.cleaned_data.get("foto")
        return validar_foto(foto) if foto else None

    def clean_banner(self):
        banner = self.cleaned_data.get("banner")
        return validar_foto(banner) if banner else None

    def clean(self):
        dados = super().clean()
        if dados.get("foto") and dados.get("remover_foto"):
            self.add_error("remover_foto", "Escolha uma nova foto ou remova a atual.")
        if dados.get("banner") and dados.get("remover_banner"):
            self.add_error("remover_banner", "Escolha um novo banner ou remova o atual.")
        return dados

class DenunciaUsuarioForm(forms.Form):
    motivo = forms.ChoiceField(choices=DenunciaUsuario.Motivo.choices)
    detalhes = forms.CharField(max_length=1000, required=False)
