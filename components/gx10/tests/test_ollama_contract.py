#!/usr/bin/env python3
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

GX10_DIR = Path(__file__).resolve().parents[1]


def load_script(name, filename):
    path = GX10_DIR / 'install' / filename
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


INSTALLER = load_script('install_ollama', 'install-ollama.py')
MODEL_INSTALLER = load_script('install_model_store', 'install-model-store.py')
VERIFIER = load_script('verify_ollama', 'verify-ollama.py')
PLATFORM_VERIFIER = load_script('verify_platform', 'verify-platform.py')


class OllamaContractTests(unittest.TestCase):
    def test_expected_manifest_inventory_is_complete(self):
        self.assertEqual(len(VERIFIER.EXPECTED_MANIFESTS), 6)
        self.assertEqual(
            {value[1] for value in VERIFIER.EXPECTED_MANIFESTS.values()},
            {
                'sha256:f0988ff50a2458c598ff6b1b87b94d0f5c44d73061c2795391878b00b2285e11',
                'sha256:7101a4a1d9e30ce87a71265e93215173f5e4cc84883e5cf1ef88862547f31fcd',
                'sha256:d7d22779fb87ed760b8b256143d423ccbbf760020d5277b9949759f67afbab12',
                'sha256:05a61d37b08453e59290add468e3bb2f688e23a01e967fecb0e2fa41218cea76',
                'sha256:5d55cac51f303b790c7fafb707fbec596ad64c7af9282619aa7dc88a37646d4c',
                'sha256:492b2922d38e553cabc2d319345644ed482874fbf5e5c9e4495cbf8e17b0cf5f',
            },
        )

    def test_invalid_binary_size_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'ollama'
            path.write_bytes(b'not the captured binary')
            with self.assertRaisesRegex(ValueError, 'unexpected size'):
                INSTALLER.validate_binary(path)

    def test_symbolic_link_model_blob_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'target'
            target.write_bytes(b'blob')
            link = root / 'link'
            os.symlink(target, link)
            with self.assertRaisesRegex(ValueError, 'invalid Ollama blob'):
                VERIFIER.validate_model_blob(link, 4)

    def test_model_blob_hash_is_verified_when_requested(self):
        with tempfile.TemporaryDirectory() as directory:
            blob = Path(directory) / 'blob'
            blob.write_bytes(b'blob')
            VERIFIER.validate_model_blob(
                blob,
                4,
                expected_digest=(
                    'fa2c8cc4f28176bbeed4b736df569a34c79cd3723e9ec42f9674b4d46ac6b8b8'
                ),
                hash_content=True,
            )
            with self.assertRaisesRegex(ValueError, 'hash differs'):
                VERIFIER.validate_model_blob(
                    blob,
                    4,
                    expected_digest='0' * 64,
                    hash_content=True,
                )

    def test_platform_verifier_uses_captured_cuda_path(self):
        self.assertEqual(
            PLATFORM_VERIFIER.CUDA_COMPILER,
            Path('/usr/local/cuda/bin/nvcc'),
        )

    def test_model_store_file_install_is_no_overwrite_and_reusable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            target = root / 'target'
            source.write_bytes(b'manifest')
            MODEL_INSTALLER.install_file(
                source,
                target,
                os.getuid(),
                os.getgid(),
            )
            self.assertEqual(target.read_bytes(), b'manifest')
            self.assertEqual(target.stat().st_nlink, 1)
            MODEL_INSTALLER.preflight_file(source, target)
            MODEL_INSTALLER.install_file(
                source,
                target,
                os.getuid(),
                os.getgid(),
            )

    def test_divergent_existing_model_store_file_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            target = root / 'target'
            source.write_bytes(b'expected')
            target.write_bytes(b'diverged')
            with self.assertRaisesRegex(ValueError, 'differs'):
                MODEL_INSTALLER.preflight_file(source, target)

    def test_model_store_source_and_target_must_be_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, 'equals installed target'):
                MODEL_INSTALLER.validate_distinct_roots(root, root)

    def test_ollama_unit_does_not_claim_pipeline_integration(self):
        text = (GX10_DIR / 'systemd' / 'ollama.service').read_text(encoding='utf-8')
        self.assertIn('ExecStart=/usr/local/bin/ollama serve', text)
        self.assertNotIn('fetch-spool', text)
        self.assertNotIn('ingest-spool', text)
        self.assertNotIn('enrich-events', text)
        self.assertNotIn('11434', text)


if __name__ == '__main__':
    unittest.main()
