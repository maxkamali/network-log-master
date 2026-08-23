#!/usr/bin/env python3
import argparse
import grp
import hashlib
import ipaddress
import json
import os
import pwd
import re
import stat
import subprocess
import sys
from pathlib import Path

EXPECTED_BINARY_SIZE = 35792104
EXPECTED_BINARY_SHA256 = '26f44ca89143f2326a3aad98b2cb5e8b5af9397aef7001cd8d022e90d6e0b55e'
EXPECTED_UNIT_SHA256 = 'd8774a8a664856242805d0e5a78297db31865e2b56727edd8d16764921858cd4'
EXPECTED_MANIFESTS = {
    'c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb': (
        'registry.ollama.ai/library/gemma4/latest',
        'sha256:f0988ff50a2458c598ff6b1b87b94d0f5c44d73061c2795391878b00b2285e11',
        9608350718,
    ),
    'e7a64ff15fb174c42b4f463e5c888c4f2c7b9cabf9e8d65a1c0874405426c1b2': (
        'registry.ollama.ai/library/nemotron-3.5-lightning/30b',
        'sha256:7101a4a1d9e30ce87a71265e93215173f5e4cc84883e5cf1ef88862547f31fcd',
        25430749387,
    ),
    'd8b269ad5c7c7144ce104b83ce93bc3efb85e0f74e01be6be5f5d6f7ca90b60f': (
        'registry.ollama.ai/library/north-mini-code-1.0/latest',
        'sha256:d7d22779fb87ed760b8b256143d423ccbbf760020d5277b9949759f67afbab12',
        18593967008,
    ),
    '500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41': (
        'registry.ollama.ai/library/qwen3/8b',
        'sha256:05a61d37b08453e59290add468e3bb2f688e23a01e967fecb0e2fa41218cea76',
        5225388164,
    ),
    'ca06e9e4087c714d44355bf954099187890e63084b4a632b8e9956c4b9492074': (
        'registry.ollama.ai/library/qwen3-coder-next/latest',
        'sha256:5d55cac51f303b790c7fafb707fbec596ad64c7af9282619aa7dc88a37646d4c',
        51741611823,
    ),
    '22130167c4c20e20c7b71454612966ca8e8171e9b3cc8ab6ce8aa6cbfec79643': (
        'registry.ollama.ai/library/qwen3.8/27b',
        'sha256:492b2922d38e553cabc2d319345644ed482874fbf5e5c9e4495cbf8e17b0cf5f',
        17741872154,
    ),
}
OLLAMA_BINARY = Path('/usr/local/bin/ollama')
OLLAMA_UNIT = Path('/etc/systemd/system/ollama.service')
MODEL_ROOT = Path('/usr/share/ollama/.ollama/models')
SHA256_DIGEST_RE = re.compile(r'^sha256:([0-9a-f]{64})$')


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def validate_file(path, uid, gid, mode, size=None, digest=None):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('required Ollama artifact is not a real regular file')
    details = path.stat()
    if details.st_nlink != 1:
        raise ValueError('required Ollama artifact must not be hard-linked')
    if details.st_uid != uid or details.st_gid != gid:
        raise ValueError('required Ollama artifact has unexpected ownership')
    if stat.S_IMODE(details.st_mode) != mode:
        raise ValueError('required Ollama artifact has unexpected mode')
    if size is not None and details.st_size != size:
        raise ValueError('required Ollama artifact has unexpected size')
    if digest is not None and file_sha256(path) != digest:
        raise ValueError('required Ollama artifact has unexpected hash')


def validate_model_blob(path, expected_size, expected_digest=None, hash_content=False):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('missing or invalid Ollama blob')
    if path.stat().st_size != expected_size:
        raise ValueError('missing or invalid Ollama blob')
    if hash_content:
        if expected_digest is None or file_sha256(path) != expected_digest:
            raise ValueError('Ollama blob hash differs')


def verify_model_store(model_root=MODEL_ROOT, hash_blobs=False):
    manifest_root = model_root / 'manifests'
    blob_root = model_root / 'blobs'
    if not manifest_root.is_dir() or not blob_root.is_dir():
        raise ValueError('Ollama model store is incomplete')

    manifests = [path for path in manifest_root.rglob('*') if path.is_file()]
    if len(manifests) != len(EXPECTED_MANIFESTS):
        raise ValueError('unexpected Ollama manifest count')

    observed = set()
    hashed_blobs = set()
    referenced_blobs = set()
    for path in manifests:
        if path.is_symlink():
            raise ValueError('unexpected symbolic-link Ollama manifest')
        manifest_hash = file_sha256(path)
        if manifest_hash not in EXPECTED_MANIFESTS:
            raise ValueError('unexpected Ollama manifest')
        observed.add(manifest_hash)
        expected_reference, expected_config, expected_bytes = EXPECTED_MANIFESTS[
            manifest_hash
        ]
        reference = path.relative_to(manifest_root).as_posix()
        if reference != expected_reference:
            raise ValueError('unexpected Ollama manifest reference')
        data = json.loads(path.read_text(encoding='utf-8'))
        config = data.get('config')
        layers = data.get('layers')
        if not isinstance(config, dict) or not isinstance(layers, list):
            raise ValueError('invalid Ollama manifest structure')
        if config.get('digest') != expected_config:
            raise ValueError('unexpected Ollama config digest')
        descriptors = [config, *layers]
        declared_bytes = 0
        for descriptor in descriptors:
            digest = descriptor.get('digest')
            size = descriptor.get('size')
            digest_match = (
                SHA256_DIGEST_RE.fullmatch(digest)
                if isinstance(digest, str)
                else None
            )
            if digest_match is None:
                raise ValueError('invalid Ollama blob digest')
            if not isinstance(size, int) or size < 0:
                raise ValueError('invalid Ollama blob size')
            blob = blob_root / digest.replace(':', '-')
            referenced_blobs.add(blob)
            verify_hash = hash_blobs and blob not in hashed_blobs
            validate_model_blob(
                blob,
                size,
                expected_digest=digest_match.group(1),
                hash_content=verify_hash,
            )
            if verify_hash:
                hashed_blobs.add(blob)
            declared_bytes += size
        if declared_bytes != expected_bytes:
            raise ValueError('unexpected Ollama declared bytes')

    if observed != set(EXPECTED_MANIFESTS):
        raise ValueError('incomplete Ollama manifest set')
    return tuple(sorted(manifests)), tuple(sorted(referenced_blobs))


def verify_listener():
    result = subprocess.run(
        ['ss', '-ltnH', 'sport = :11434'],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    if len(lines) != 1:
        raise ValueError('unexpected Ollama listener count')
    fields = lines[0].split()
    local = fields[3]
    host = local.rsplit(':', 1)[0].strip('[]')
    if not ipaddress.ip_address(host).is_loopback:
        raise ValueError('Ollama listener is not loopback-only')


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--offline', action='store_true')
    parser.add_argument(
        '--hash-blobs',
        action='store_true',
        help='read and hash each unique model blob against its digest name',
    )
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        ollama = pwd.getpwnam('ollama')
        group = grp.getgrnam('ollama')
        validate_file(
            OLLAMA_BINARY,
            0,
            0,
            0o755,
            EXPECTED_BINARY_SIZE,
            EXPECTED_BINARY_SHA256,
        )
        validate_file(
            OLLAMA_UNIT,
            0,
            0,
            0o644,
            digest=EXPECTED_UNIT_SHA256,
        )
        if MODEL_ROOT.is_symlink() or not MODEL_ROOT.is_dir():
            raise ValueError('Ollama model root is not a real directory')
        model_details = MODEL_ROOT.stat()
        if model_details.st_uid != ollama.pw_uid or model_details.st_gid != group.gr_gid:
            raise ValueError('Ollama model root has unexpected ownership')
        if stat.S_IMODE(model_details.st_mode) != 0o755:
            raise ValueError('Ollama model root has unexpected mode')
        verify_model_store(hash_blobs=args.hash_blobs)

        if not args.offline:
            subprocess.run(
                ['systemctl', 'is-active', '--quiet', 'ollama.service'],
                check=True,
            )
            subprocess.run(
                ['systemctl', 'is-enabled', '--quiet', 'ollama.service'],
                check=True,
            )
            verify_listener()

        print('GX10_OLLAMA_VERIFY=PASS')
        return 0
    except (
        KeyError,
        OSError,
        subprocess.CalledProcessError,
        ValueError,
    ) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
