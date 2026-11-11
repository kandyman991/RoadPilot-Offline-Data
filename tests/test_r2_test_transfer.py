"""Offline authenticated-envelope regression tests."""
import base64
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import upload_test_original_graphs_from_envelope as m

class EncryptedTransferTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.dir=Path(self.tmp.name)
        self.key=x25519.X25519PrivateKey.generate()
        self.now=int(time.time())
        peer=x25519.X25519PrivateKey.generate()
        sym=HKDF(algorithm=hashes.SHA256(),length=32,salt=None,info=m.CONTEXT).derive(peer.exchange(self.key.public_key()))
        plain={'schema':'roadpilot.r2.test-only-credential-handoff.v1','accountId':m.ACCOUNT,'bucket':m.BUCKET,'accessKeyId':'fake','secretAccessKey':'fake','issuedAt':self.now,'expiresAt':self.now+1800}
        nonce=os.urandom(12)
        enc=AESGCM(sym).encrypt(nonce,json.dumps(plain).encode(),m.CONTEXT)
        self.env=self.dir/'env.json'
        self.env.write_text(json.dumps({'schema':'roadpilot.r2.encrypted-handoff.v1','ephemeralPublicKey':base64.b64encode(peer.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)).decode(),'nonce':base64.b64encode(nonce).decode(),'ciphertext':base64.b64encode(enc).decode()}))
        self.priv=self.dir/'secret.key'
        self.priv.write_bytes(self.key.private_bytes(serialization.Encoding.Raw,serialization.PrivateFormat.Raw,serialization.NoEncryption()))
        self.priv.chmod(0o600)
    def tearDown(self): self.tmp.cleanup()
    def test_valid_recipient(self):
        self.assertEqual(m.decrypt_credentials(self.env,self.priv,now=self.now)['bucket'],m.BUCKET)
    def test_expired_rejected(self):
        with self.assertRaises(ValueError):m.decrypt_credentials(self.env,self.priv,now=self.now+1801)
    def test_tampered_rejected(self):
        e=json.loads(self.env.read_text());e['ciphertext']=base64.b64encode(os.urandom(100)).decode();self.env.write_text(json.dumps(e))
        with self.assertRaises(Exception):m.decrypt_credentials(self.env,self.priv,now=self.now)
    def test_key_permissions_rejected(self):
        self.priv.chmod(0o644)
        with self.assertRaises(ValueError):m.decrypt_credentials(self.env,self.priv,now=self.now)
    def test_missing_archives_fail_closed(self):
        old=m.ROOT;m.ROOT=self.dir
        try:
            with self.assertRaises(FileNotFoundError):m.expected_sources()
        finally:m.ROOT=old
if __name__=='__main__':unittest.main()
