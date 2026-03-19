import re

def sanitize_phone(phone: str) -> str:
    """Higieniza o telefone mantendo apenas números."""
    return re.sub(r'\D', '', phone)

def validate_phone(phone: str) -> bool:
    """
    Valida se o telefone tem 10 ou 11 dígitos após sanitização.
    Rejeita +55 pois assume escopo nacional simplificado, conforme regra.
    """
    if '+55' in phone:
        return False
        
    sanitized = sanitize_phone(phone)
    if len(sanitized) not in [10, 11]:
        return False
        
    return True

def validate_name(name: str, min_len: int, max_len: int) -> bool:
    """
    Valida nome/sobrenome: apenas letras, acentos, espaços, apostrofo e hifen.
    """
    if not name or len(name) < min_len or len(name) > max_len:
        return False
        
    pattern = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ\s\-\']+$")
    return bool(pattern.match(name))

def format_name(name: str) -> str:
    """Formata a primeira letra em maiúscula."""
    if not name:
        return name
    return name.title()

def validate_email(email: str) -> bool:
    """
    Validação RFC 5321 simplificada para e-mail.
    """
    if not email or len(email) > 254:
        return False
        
    pattern = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
    return bool(pattern.match(email))

def validate_cpf(cpf: str) -> bool:
    """
    Valida se o CPF é válido.
    """
    cpf = re.sub(r'\D', '', cpf)

    if len(cpf) != 11:
        return False

    if cpf == cpf[0] * 11:
        return False

    for i in range(9, 11):
        soma = sum(int(cpf[num]) * ((i + 1) - num) for num in range(i))
        digito = (soma * 10 % 11) % 10
        if digito != int(cpf[i]):
            return False

    return True
def validate_cnpj(cnpj: str) -> bool:
    """
    Valida se o CNPJ é válido.
    """
    cnpj = re.sub(r'\D', '', cnpj)

    if len(cnpj) != 14:
        return False

    if cnpj == cnpj[0] * 14:
        return False

    # Validação dos dígitos verificadores
    for i in [12, 13]:
        peso = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2] if i == 12 else [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        soma = sum(int(cnpj[num]) * peso[num] for num in range(i))
        digito = (soma % 11)
        digito = 0 if digito < 2 else 11 - digito
        if digito != int(cnpj[i]):
            return False

    return True
