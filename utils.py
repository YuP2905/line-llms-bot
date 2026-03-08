from core.security import get_password_hash

if __name__ == "__main__":
    password = "yupeng@!"
    hashed_password = get_password_hash(password)
    print(f"Hashed password: {hashed_password}")