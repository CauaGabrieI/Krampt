import unicodedata

from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.password_validation import validate_password

User = get_user_model()


def normalizar_usuario(valor):
    """Canonical form for usernames: NFKC, no whitespace, lowercase."""
    return ''.join(unicodedata.normalize('NFKC', valor).split()).lower()


class CadastroForm(forms.Form):
    name = forms.CharField(label='Nome', max_length=150)
    username = forms.CharField(label='Usuário', max_length=150)
    email = forms.EmailField(label='E-mail', max_length=254)
    password = forms.CharField(label='Senha', strip=False, widget=forms.PasswordInput)
    password_confirm = forms.CharField(label='Confirmar senha', strip=False, widget=forms.PasswordInput)

    def clean_name(self):
        nome = ' '.join(unicodedata.normalize('NFKC', self.cleaned_data['name']).split())
        if not nome:
            raise forms.ValidationError('Informe seu nome.')
        return nome

    def clean_username(self):
        username = normalizar_usuario(self.cleaned_data['username'])
        User._meta.get_field('username').clean(username, None)
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('Este usuário já está em uso.')
        return username

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Este e-mail já está em uso.')
        return email

    def clean(self):
        dados = super().clean()
        senha = dados.get('password')
        confirmacao = dados.get('password_confirm')
        if senha and confirmacao and senha != confirmacao:
            self.add_error('password_confirm', 'As senhas não coincidem.')
        if senha:
            usuario = User(username=dados.get('username', ''), first_name=dados.get('name', ''), email=dados.get('email', ''))
            try:
                validate_password(senha, usuario)
            except forms.ValidationError as erro:
                self.add_error('password', erro)
        return dados

    def save(self):
        return User.objects.create_user(
            username=self.cleaned_data['username'],
            first_name=self.cleaned_data['name'],
            email=self.cleaned_data['email'],
            password=self.cleaned_data['password'],
            is_active=False,
        )


class LoginForm(forms.Form):
    username = forms.CharField(label='Usuário', max_length=150)
    password = forms.CharField(label='Senha', strip=False, widget=forms.PasswordInput)

    def __init__(self, request, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request
        self.usuario = None

    def clean(self):
        dados = super().clean()
        username = normalizar_usuario(dados.get('username', ''))
        senha = dados.get('password')
        if username and senha:
            self.usuario = authenticate(self.request, username=username, password=senha)
            if self.usuario is None:
                raise forms.ValidationError('Usuário ou senha inválidos.')
        elif not username and 'username' in dados:
            self.add_error('username', 'Informe seu usuário.')
        return dados


class VerificacaoForm(forms.Form):
    codigo = forms.RegexField(
        regex=r"^[0-9]{6}$",
        label="Código",
        error_messages={
            "required": "Informe o código de 6 dígitos.",
            "invalid": "O código deve ter exatamente 6 números.",
        },
    )


class RedefinirSenhaForm(PasswordResetForm):
    email = forms.EmailField(
        label="E-mail",
        max_length=254,
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )


class TesteEmailForm(forms.Form):
    email = forms.EmailField(label="E-mail de destino", max_length=254)
