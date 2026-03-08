from typing import Final
import bcrypt


def verify_password(
    plain_password: str,
    hashed_password: str
) -> bool:
    try:
        plain_pwd = plain_password.encode("utf-8")
        hashed_pwd = hashed_password.encode("utf-8")
        return bcrypt.checkpw(plain_pwd, hashed_pwd)
    except Exception:
        return False

def get_password_hash(
    password: str
) -> str:
    pwd = password.encode("utf-8")
    salt: Final[bytes] = bcrypt.gensalt()

    hashed = bcrypt.hashpw(pwd, salt)
    return hashed.decode("utf-8")