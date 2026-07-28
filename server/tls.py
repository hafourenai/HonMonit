import os
import logging
from pathlib import Path
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from datetime import datetime, timedelta

logger = logging.getLogger("honmonit.tls")


class TLSManager:
    """Manage self-signed TLS certificates for HonMonit."""

    def __init__(self, cert_dir: str = "./certs"):
        self.cert_dir = Path(cert_dir)
        self.cert_path = self.cert_dir / "honmonit.crt"
        self.key_path = self.cert_dir / "honmonit.key"

    def ensure_certificates(self):
        """Ensure TLS certificates exist, generate if missing."""
        if self.cert_path.exists() and self.key_path.exists():
            logger.info("TLS certificates found at %s", self.cert_dir)
            return

        logger.info("Generating self-signed TLS certificate...")
        self.generate_self_signed_cert()
        logger.info("TLS certificate saved to %s", self.cert_dir)

    def generate_self_signed_cert(
        self,
        hostname: str = "localhost",
        valid_days: int = 365,
    ):
        """Generate a self-signed certificate."""
        # Create cert directory if it doesn't exist
        self.cert_dir.mkdir(parents=True, exist_ok=True)

        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend(),
        )

        # Generate certificate
        subject = issuer = x509.Name(
            [
                x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "State"),
                x509.NameAttribute(NameOID.LOCALITY_NAME, "City"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "HonMonit"),
                x509.NameAttribute(NameOID.COMMON_NAME, hostname),
            ]
        )

        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.utcnow())
            .not_valid_after(datetime.utcnow() + timedelta(days=valid_days))
            .add_extension(
                x509.SubjectAlternativeName(
                    [
                        x509.DNSName(hostname),
                        x509.DNSName("*.localhost"),
                        x509.DNSName("127.0.0.1"),
                    ]
                ),
                critical=False,
            )
            .sign(private_key, hashes.SHA256(), default_backend())
        )

        # Save private key
        with open(self.key_path, "wb") as f:
            f.write(
                private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )

        # Save certificate
        with open(self.cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

        # Set restrictive permissions on private key
        os.chmod(self.key_path, 0o600)

    def get_cert_paths(self) -> tuple:
        """Get certificate and key paths."""
        return str(self.cert_path), str(self.key_path)
