from django import forms
from django.contrib.auth import get_user_model

from login.forms import normalizar_usuario

from .models import PreferenciasUsuario

User = get_user_model()


class ContaForm(forms.Form):
    nome = forms.CharField(label="Nome de exibição", max_length=150)
    username = forms.CharField(label="Usuário", max_length=150)
    email = forms.EmailField(label="E-mail", max_length=254)

    def __init__(self, usuario, *args, **kwargs):
        self.usuario = usuario
        super().__init__(*args, **kwargs)

    def clean_nome(self):
        nome = " ".join(self.cleaned_data["nome"].split())
        if not nome:
            raise forms.ValidationError("Informe seu nome.")
        return nome

    def clean_username(self):
        username = normalizar_usuario(self.cleaned_data["username"])
        User._meta.get_field("username").clean(username, self.usuario)
        if User.objects.exclude(pk=self.usuario.pk).filter(username__iexact=username).exists():
            raise forms.ValidationError("Este usuário já está em uso.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.exclude(pk=self.usuario.pk).filter(email__iexact=email).exists():
            raise forms.ValidationError("Este e-mail já está em uso.")
        return email

    def save(self):
        email_alterado = self.usuario.email.lower() != self.cleaned_data["email"]
        self.usuario.first_name = self.cleaned_data["nome"]
        self.usuario.username = self.cleaned_data["username"]
        self.usuario.email = self.cleaned_data["email"]
        self.usuario.save(update_fields=["first_name", "username", "email"])
        return email_alterado


class PrivacidadeForm(forms.ModelForm):
    class Meta:
        model = PreferenciasUsuario
        fields = ("permitir_novas_conversas", "mensagens_de")
        labels = {
            "permitir_novas_conversas": "Permitir novas conversas",
            "mensagens_de": "Quem pode enviar mensagens",
        }


class MensagensForm(forms.ModelForm):
    class Meta:
        model = PreferenciasUsuario
        fields = ("permitir_novas_conversas", "mensagens_de")
        labels = {
            "permitir_novas_conversas": "Permitir novas conversas",
            "mensagens_de": "Aceitar mensagens de",
        }


class NotificacoesForm(forms.ModelForm):
    class Meta:
        model = PreferenciasUsuario
        fields = (
            "notificacoes_site",
            "notificar_seguidores",
            "notificar_curtidas",
            "notificar_comentarios",
            "notificar_respostas",
            "notificar_reposts",
            "notificar_mensagens",
        )
        labels = {
            "notificacoes_site": "Notificações dentro do site",
            "notificar_seguidores": "Novos seguidores",
            "notificar_curtidas": "Curtidas",
            "notificar_comentarios": "Comentários",
            "notificar_respostas": "Respostas",
            "notificar_reposts": "Republicações",
            "notificar_mensagens": "Aviso de mensagens privadas no cabeçalho",
        }


class AparenciaForm(forms.ModelForm):
    class Meta:
        model = PreferenciasUsuario
        fields = ("tema", "tamanho_fonte", "reduzir_animacoes", "densidade")
        labels = {
            "tema": "Tema",
            "tamanho_fonte": "Tamanho da fonte",
            "reduzir_animacoes": "Reduzir animações",
            "densidade": "Densidade do feed",
        }


class ConfirmacaoForm(forms.Form):
    confirmacao = forms.CharField(label="Confirmação", max_length=150)


class ExcluirContaForm(ConfirmacaoForm):
    senha = forms.CharField(label="Senha atual", strip=False, widget=forms.PasswordInput)
