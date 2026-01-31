"""
Secure Password Manager for PDF Passwords
Encrypts passwords using Fernet symmetric encryption
"""
import os
import yaml
from pathlib import Path
from typing import Dict, Optional
from cryptography.fernet import Fernet


class PasswordManager:
    """
    Manages encrypted PDF passwords stored in YAML.
    Uses Fernet encryption (AES 128-bit).
    """
    
    def __init__(self, secrets_file: str = "secrets.yaml.enc", key_file: str = ".encryption_key"):
        """
        Initialize password manager.
        
        Args:
            secrets_file: Path to encrypted secrets file
            key_file: Path to encryption key (keep this private!)
        """
        self.secrets_path = Path(__file__).parent.parent / secrets_file
        self.key_path = Path(__file__).parent.parent / key_file
        self.cipher = None
        self._load_or_create_key()
    
    def _load_or_create_key(self):
        """Load existing encryption key or create new one"""
        if self.key_path.exists():
            with open(self.key_path, 'rb') as f:
                key = f.read()
        else:
            # Generate new key
            key = Fernet.generate_key()
            with open(self.key_path, 'wb') as f:
                f.write(key)
            print(f"[OK] Created new encryption key: {self.key_path}")
            print(f"[WARN] IMPORTANT: Keep {self.key_path} secure and DO NOT commit to git!")
        
        self.cipher = Fernet(key)
    
    def save_passwords(self, passwords: Dict[str, str]):
        """
        Save passwords in encrypted YAML file.
        
        Args:
            passwords: Dict mapping PDF filename patterns to passwords
        """
        # Convert to YAML
        yaml_data = yaml.dump(passwords)
        
        # Encrypt
        encrypted_data = self.cipher.encrypt(yaml_data.encode())
        
        # Save
        with open(self.secrets_path, 'wb') as f:
            f.write(encrypted_data)
        
        print(f"[OK] Saved {len(passwords)} encrypted password(s) to {self.secrets_path}")
    
    def load_passwords(self) -> Dict[str, str]:
        """
        Load and decrypt passwords from YAML file.
        
        Returns:
            Dict of passwords
        """
        if not self.secrets_path.exists():
            return {}
        
        try:
            # Read encrypted file
            with open(self.secrets_path, 'rb') as f:
                encrypted_data = f.read()
            
            # Decrypt
            decrypted_data = self.cipher.decrypt(encrypted_data)
            
            # Parse YAML
            passwords = yaml.safe_load(decrypted_data.decode())
            
            return passwords or {}
        
        except Exception as e:
            print(f"[WARN] Could not load passwords: {e}")
            return {}
    
    def get_password(self, pdf_filename: str) -> Optional[str]:
        """
        Get password for a specific PDF.
        Supports pattern matching (e.g., "amazon_*" matches "amazon_jan.pdf")
        
        Args:
            pdf_filename: Name of PDF file
        
        Returns:
            Password if found, None otherwise
        """
        passwords = self.load_passwords()
        
        # Try exact match first
        if pdf_filename in passwords:
            return passwords[pdf_filename]
        
        # Try pattern matching
        for pattern, password in passwords.items():
            if self._matches_pattern(pdf_filename, pattern):
                return password
        
        return None
    
    def _matches_pattern(self, filename: str, pattern: str) -> bool:
        """Simple wildcard pattern matching"""
        if '*' in pattern:
            parts = pattern.split('*')
            if parts[0] and not filename.startswith(parts[0]):
                return False
            if parts[-1] and not filename.endswith(parts[-1]):
                return False
            return True
        return filename == pattern
    
    def add_password(self, pattern: str, password: str):
        """
        Add or update a password.
        
        Args:
            pattern: PDF filename or pattern (e.g., "*.pdf" or "amazon_*")
            password: Password to store
        """
        passwords = self.load_passwords()
        passwords[pattern] = password
        self.save_passwords(passwords)


# Convenience functions
def init_password_store(passwords: dict = None):
    """Initialize password store with passwords dict"""
    manager = PasswordManager()
    
    if passwords is None:
        print("[WARN] No passwords provided. Use add_password() to add passwords.")
        print("  Example: manager.add_password('*.pdf', 'your_password')")
        return
    
    manager.save_passwords(passwords)
    print("\n[OK] Password store initialized")
    print("  Patterns configured:")
    for pattern in passwords.keys():
        print(f"    - {pattern}")


def get_pdf_password(pdf_path: str) -> Optional[str]:
    """
    Get password for a PDF file.
    
    Args:
        pdf_path: Path to PDF file
    
    Returns:
        Password if found, None otherwise
    """
    manager = PasswordManager()
    filename = Path(pdf_path).name
    return manager.get_password(filename)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "add":
            # Add password interactively
            pattern = input("PDF pattern (e.g., *.pdf, *_Amazon_*.pdf): ")
            password = input("Password: ")
            manager = PasswordManager()
            manager.add_password(pattern, password)
            print(f"[OK] Password added for pattern: {pattern}")
        elif sys.argv[1] == "test":
            # Test password retrieval
            print("\n" + "="*60)
            print("Testing password retrieval:")
            print("="*60)
            
            test_files = [
                "4315XXXXXXXX2007_170033_Retail_Amazon_NORM.pdf",
                "4315XXXXXXXX2007_349072_Retail_Amazon_NORM.pdf",
                "some_other_statement.pdf"
            ]
            
            for test_file in test_files:
                password = get_pdf_password(test_file)
                if password:
                    print(f"[OK] {test_file[:40]}... -> Password found")
                else:
                    print(f"[X] {test_file[:40]}... -> No password")
    else:
        print("""Password Manager Usage:
        
Add password:   python password_manager.py add
Test retrieval: python password_manager.py test
        
Passwords are encrypted and stored in secrets.yaml.enc
        """)
