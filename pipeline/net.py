"""HTTP helper shared by the pipeline scripts.

Some Python installs on macOS ship without CA certificates, so every https call fails with
CERTIFICATE_VERIFY_FAILED. Fall back to certifi or the system bundle when that happens.
"""
import os
import ssl
import urllib.request


def _context():
    ctx = ssl.create_default_context()
    if ctx.cert_store_stats().get("x509_ca"):
        return ctx
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass
    for f in ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt", "/opt/homebrew/etc/openssl@3/cert.pem"):
        if os.path.exists(f):
            return ssl.create_default_context(cafile=f)
    return ctx


CTX = _context()


def urlopen(req, timeout=40):
    return urllib.request.urlopen(req, timeout=timeout, context=CTX)
