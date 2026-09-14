from django import forms

AUDIO_TYPES = {"audio/mpeg", "audio/wav", "audio/x-wav", "audio/ogg", "audio/webm", "audio/mp4", "audio/x-m4a"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_IMAGENS_POST = 4


def validar_imagem(imagem):
    if imagem and imagem.size > MAX_UPLOAD_BYTES:
        raise forms.ValidationError("Cada imagem deve ter no máximo 10 MB.")
    return imagem


def validar_audio(audio):
    if not audio:
        return
    if audio.size > MAX_UPLOAD_BYTES:
        raise forms.ValidationError("O áudio deve ter no máximo 10 MB.")
    if audio.content_type not in AUDIO_TYPES:
        raise forms.ValidationError("Use áudio MP3, WAV, OGG, WebM ou M4A.")
    # A assinatura elimina arquivos claramente falsos; decodificação completa requer outro parser.
    posicao = audio.tell()
    audio.seek(0)
    cabecalho = audio.read(32)
    audio.seek(posicao)
    mp3 = cabecalho.startswith(b"ID3") or (len(cabecalho) > 1 and cabecalho[0] == 0xFF and cabecalho[1] & 0xE0 == 0xE0)
    assinaturas = {
        "audio/mpeg": mp3,
        "audio/wav": cabecalho.startswith(b"RIFF") and cabecalho[8:12] == b"WAVE",
        "audio/x-wav": cabecalho.startswith(b"RIFF") and cabecalho[8:12] == b"WAVE",
        "audio/ogg": cabecalho.startswith(b"OggS"),
        "audio/webm": cabecalho.startswith(b"\x1a\x45\xdf\xa3"),
        "audio/mp4": cabecalho[4:8] == b"ftyp",
        "audio/x-m4a": cabecalho[4:8] == b"ftyp",
    }
    if not assinaturas[audio.content_type]:
        raise forms.ValidationError("O conteúdo do áudio não corresponde ao formato informado.")


class SeletorDeImagens(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultiplasImagens(forms.ImageField):
    widget = SeletorDeImagens

    def clean(self, data, initial=None):
        arquivos = data if isinstance(data, (list, tuple)) else ([data] if data else [])
        if len(arquivos) > MAX_IMAGENS_POST:
            raise forms.ValidationError("Adicione no máximo 4 imagens por post.")
        imagens = []
        for arquivo in arquivos:
            validar_imagem(arquivo)
            imagem = super().clean(arquivo, initial)
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
    imagem = forms.ImageField(required=False, validators=[validar_imagem])
    audio = forms.FileField(required=False)

    def clean(self):
        dados = super().clean()
        conteudo = (dados.get("conteudo") or "").strip()
        imagem = dados.get("imagem")
        audio = dados.get("audio")
        if not conteudo and not imagem and not audio:
            raise forms.ValidationError("Escreva uma resposta ou adicione imagem ou áudio.")
        if imagem:
            if imagem.image.format not in {"JPEG", "PNG", "WEBP", "GIF"}:
                raise forms.ValidationError("Use imagens JPG, PNG, WebP ou GIF.")
        validar_audio(audio)
        dados["conteudo"] = conteudo
        return dados
