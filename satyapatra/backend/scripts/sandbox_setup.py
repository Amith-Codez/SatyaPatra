"""Create the sandbox issuers' PKI (root CA + signing certificates) and seal specimens."""
import datetime
import sys
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID

sys.path.insert(0, str(Path(__file__).resolve().parent))
import docgen  # noqa: E402

PKI = docgen.PKI
NOW = datetime.datetime.now(datetime.timezone.utc)


def _name(cn, org="Sandbox Issuer Network (synthetic)"):
    return x509.Name([x509.NameAttribute(NameOID.COUNTRY_NAME, "IN"),
                      x509.NameAttribute(NameOID.ORGANIZATION_NAME, org),
                      x509.NameAttribute(NameOID.COMMON_NAME, cn)])


def _write_key(key, path):
    path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                       serialization.NoEncryption()))


def make_ca():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    cert = (x509.CertificateBuilder().subject_name(_name("Sandbox Issuer Root CA")).issuer_name(_name("Sandbox Issuer Root CA"))
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(NOW - datetime.timedelta(days=1)).not_valid_after(NOW + datetime.timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=1), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False, key_encipherment=False,
                                         data_encipherment=False, key_agreement=False, key_cert_sign=True,
                                         crl_sign=True, encipher_only=False, decipher_only=False), critical=True)
            .sign(key, hashes.SHA256()))
    _write_key(key, PKI / "issuer-ca.key")
    (PKI / "issuer-ca.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return key, cert


def make_signer(ca_key, ca_cert, slug, cn):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    cert = (x509.CertificateBuilder().subject_name(_name(cn)).issuer_name(ca_cert.subject)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(NOW - datetime.timedelta(days=1)).not_valid_after(NOW + datetime.timedelta(days=1825))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=True, key_encipherment=False,
                                         data_encipherment=False, key_agreement=False, key_cert_sign=False,
                                         crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.EMAIL_PROTECTION]), critical=False)
            .sign(ca_key, hashes.SHA256()))
    _write_key(key, PKI / f"{slug}.key")
    (PKI / f"{slug}.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))


SEALS = {
    "ISS-FIRE": ("STATE FIRE & EMERGENCY SERVICES", (139, 30, 30), True),
    "ISS-MUNI": ("MUNICIPAL CORPORATION BUILDINGS", (30, 77, 139), False),
    "ISS-REG": ("SUB-REGISTRAR OFFICE", (60, 60, 60), True),
    "ISS-BANK": ("SAMPLE NATIONAL BANK", (15, 90, 58), False),
    "NOTARY": ("NOTARY PUBLIC", (60, 60, 60), True),
    "FAKE-FIRE": ("FIRE SERVICES DEPARTMENT", (150, 40, 40), False),
}

if __name__ == "__main__":
    ca_key, ca_cert = make_ca()
    make_signer(ca_key, ca_cert, "ISS-FIRE", "Sample State Fire & Emergency Services - Signing")
    make_signer(ca_key, ca_cert, "ISS-MUNI", "Sample Municipal Corporation - Signing")
    for k, (txt, col, star) in SEALS.items():
        m = docgen.make_seal_master(txt, col, star)
        m.save(PKI / f"{k}-seal.png")
        (PKI / f"{k}-seal.phash").write_text(docgen.specimen_hash(m))
    print("PKI and seals ready in", PKI)
