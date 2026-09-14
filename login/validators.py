from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class ComposicaoSenhaValidator:
    """Complementa os validadores nativos com os requisitos do Krampt."""

    def validate(self, password, user=None):
        requisitos = (
            (any(caractere.isupper() for caractere in password), _("A senha precisa de pelo menos uma letra maiúscula.")),
            (any(caractere.islower() for caractere in password), _("A senha precisa de pelo menos uma letra minúscula.")),
            (any(caractere.isdecimal() for caractere in password), _("A senha precisa de pelo menos um número.")),
            (any(not caractere.isalnum() and not caractere.isspace() for caractere in password), _("A senha precisa de pelo menos um caractere especial.")),
        )
        erros = [mensagem for valido, mensagem in requisitos if not valido]
        if erros:
            raise ValidationError(erros)

    def get_help_text(self):
        return _("Use letras maiúsculas e minúsculas, números e caracteres especiais.")
