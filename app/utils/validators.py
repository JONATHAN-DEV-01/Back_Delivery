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
