from __future__ import annotations
from typing import Optional
from cryptography.fernet import Fernet, InvalidToken


class TokenCipher:

    def __init__(self, key: str) -> None:
        self._fernet = Fernet(key)

    def encrypt(self, plaintext_token: str) -> str:
        if plaintext_token is None:
            raise ValueError("Cannot encrypt None.")
        if plaintext_token == "":
            raise ValueError("Cannot encrypt empty string")
        
        token_bytes = plaintext_token.encode("utf-8")
        encryped = self._fernet.encrypt(token_bytes)
        return encryped.decode("utf-8")
    
    def decrypt(self, ciphertext: str) -> Optional[str]:
        
        if not ciphertext: return None
        
        try: 
            decrypted_bytes = self._fernet.decrypt(ciphertext.encode("utf-8"))
        except InvalidToken:
            raise InvalidToken("Invalid token.")
        
        return decrypted_bytes.decode("utf-8")
    
    
def generate_key() -> str:
    return Fernet.generate_key().decode("utf-8")