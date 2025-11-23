from .tokens import TokenCipher
from config.settings import settings

token_cipher = TokenCipher(key=settings.TOKEN_ENCRYPTION_KEY)