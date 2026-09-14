from django import forms

AUDIO_TYPES = {"audio/mpeg", "audio/wav", "audio/x-wav", "audio/ogg", "audio/webm", "audio/mp4", "audio/x-m4a"}


def validar_audio(audio):
    if not audio:
        return
    if audio.size > 10 * 1024 * 1024:
        raise forms.ValidationError("O áudio deve ter no máximo 10 MB.")
    if audio.content_type not in AUDIO_TYPES:
        raise forms.ValidationError("Use áudio MP3, WAV, OGG, WebM ou M4A.")


class SeletorDeImagens(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultiplasImagens(forms.ImageField):
    widget = SeletorDeImagens

    def clean(self, data, initial=None):
        arquivos = data if isinstance(data, (list, tuple)) else ([data] if data else [])
        imagens = []
        for arquivo in arquivos:
            imagem = super().clean(arquivo, initial)
            if imagem.size > 10 * 1024 * 1024:
                raise forms.ValidationError("Cada imagem deve ter no máximo 10 MB.")
            if imagem.image.format not in {"JPEG", "PNG", "WEBP", "GIF"}:
                raise forms.ValidationError("Use imagens JPG, PNG, WebP ou GIF.")
            imagens.append(imagem)
        return imagens


class CriarPostForm(forms.Form):
    conteudo = forms.CharField(max_length=10000, required=False)
    imagem = MultiplasImagens(required=False)
    audio = forms.FileField(required=False)

    def clean(self):
        dados = super().clean()
        conteudo = dados.get("conteudo", "").strip()
        audio = dados.get("audio")
        validar_audio(audio)
        if not conteudo and not dados.get("imagem") and not audio:
            raise forms.ValidationError("Escreva algo ou adicione uma imagem ou áudio.")
        return dados


class EditarPostForm(forms.Form):
    conteudo = forms.CharField(
        max_length=10000,
        required=False,
        widget=forms.Textarea(attrs={"rows": 5, "placeholder": "Edite seu post..."}),
    )


class ComentarioForm(forms.Form):
    conteudo = forms.CharField(max_length=280, required=False)
    imagem = forms.ImageField(required=False)
    audio = forms.FileField(required=False)

    def clean(self):
        dados = super().clean()
        conteudo = (dados.get("conteudo") or "").strip()
        imagem = dados.get("imagem")
        audio = dados.get("audio")
        if not conteudo and not imagem and not audio:
            raise forms.ValidationError("Escreva uma resposta ou adicione imagem ou áudio.")
        if imagem:
            if imagem.size > 10 * 1024 * 1024:
                raise forms.ValidationError("A imagem deve ter no máximo 10 MB.")
            if imagem.image.format not in {"JPEG", "PNG", "WEBP", "GIF"}:
                raise forms.ValidationError("Use imagens JPG, PNG, WebP ou GIF.")
        validar_audio(audio)
        dados["conteudo"] = conteudo
        return dados
