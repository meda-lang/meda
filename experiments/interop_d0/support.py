"""Local test infrastructure; secret files exist only in temporary directories."""
from __future__ import annotations
import contextlib
import json
from pathlib import Path
import secrets
import socket
import ssl
import subprocess
import time

HERE = Path(__file__).resolve().parent
PYTHON = HERE / '.venv/bin/python'


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def write_private(path, data):
    path = Path(path)
    path.write_text(json.dumps(data))
    path.chmod(0o600)
    return path


def certificates(directory):
    directory = Path(directory)
    ca, ca_key = directory/'ca.pem', directory/'ca.key'
    cert, key, csr = directory/'server.pem', directory/'server.key', directory/'server.csr'
    ext = directory/'extensions.cnf'
    ext.write_text('subjectAltName=DNS:localhost,IP:127.0.0.1\nbasicConstraints=CA:FALSE\nextendedKeyUsage=serverAuth\n')
    commands = [
        ['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1', '-subj', '/CN=Meda local test CA', '-keyout', str(ca_key), '-out', str(ca)],
        ['openssl', 'req', '-newkey', 'rsa:2048', '-nodes', '-subj', '/CN=localhost', '-keyout', str(key), '-out', str(csr)],
        ['openssl', 'x509', '-req', '-in', str(csr), '-CA', str(ca), '-CAkey', str(ca_key), '-CAcreateserial', '-days', '1', '-extfile', str(ext), '-out', str(cert)],
    ]
    for command in commands:
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
    ca_key.chmod(0o600)
    key.chmod(0o600)
    return {'ca_file': str(ca), 'cert_file': str(cert), 'key_file': str(key)}


def credentials(audience):
    ops = ['discover', 'readEvidence'] if audience == 'mcp' else ['discover', 'submit', 'observe', 'provideInput', 'cancel']
    rows = []
    for label, principal, expiry, target in [('valid', 'alice', 3600, audience), ('foreign', 'bob', 3600, audience), ('expired', 'alice', -60, audience), ('wrong_audience', 'alice', 3600, 'unrelated')]:
        rows.append({'label': label, 'token': secrets.token_urlsafe(32), 'principal': principal,
                     'tenant': 'tenant-a', 'audience': target, 'operations': ops, 'expires_at': time.time()+expiry})
    return rows


@contextlib.contextmanager
def peer(config, directory):
    directory = Path(directory)
    name = config['protocol']
    config_path = write_private(directory/(name+'-config.json'), config)
    with (directory/(name+'-process.log')).open('wb') as log:
        child = subprocess.Popen([str(PYTHON), str(HERE/'sdk_peers.py'), '--config', str(config_path)],
                                 stdout=log, stderr=log, cwd=HERE, start_new_session=True)
        try:
            context = ssl.create_default_context(cafile=config['ca_file'])
            deadline = time.monotonic()+10
            while True:
                if child.poll() is not None:
                    raise RuntimeError(f'{name} SDK peer exited {child.returncode}; inspect private process log')
                try:
                    with socket.create_connection(('127.0.0.1', config['port']), timeout=.2) as sock:
                        with context.wrap_socket(sock, server_hostname='localhost'):
                            break
                except (OSError, ssl.SSLError):
                    if time.monotonic() >= deadline:
                        raise RuntimeError(f'{name} SDK peer startup timed out')
                    time.sleep(.03)
            yield child
        finally:
            child.terminate()
            try:
                child.wait(timeout=2)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=2)


def read_witness(path):
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
