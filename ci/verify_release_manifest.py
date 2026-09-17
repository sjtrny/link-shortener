"""Verify that a published tag resolves to the expected OCI image index."""

from argparse import ArgumentParser
import json
from pathlib import Path


def verify_manifest(manifest: dict, digest: str, expected_platforms: set[tuple[str, str]]):
    if manifest.get('digest') != digest:
        raise ValueError(f'Tag digest {manifest.get("digest")} does not match published digest {digest}.')
    platforms = {
        (entry.get('platform', {}).get('os'), entry.get('platform', {}).get('architecture'))
        for entry in manifest.get('manifests', [])
        if entry.get('platform', {}).get('os') != 'unknown'
    }
    if platforms != expected_platforms:
        raise ValueError(f'Published platforms {sorted(platforms)} do not match {sorted(expected_platforms)}.')
    platform_digests = {
        entry['digest'] for entry in manifest['manifests']
        if (entry.get('platform', {}).get('os'), entry.get('platform', {}).get('architecture')) in expected_platforms
    }
    attestations = {
        entry.get('annotations', {}).get('vnd.docker.reference.digest')
        for entry in manifest['manifests']
        if entry.get('annotations', {}).get('vnd.docker.reference.type') == 'attestation-manifest'
    }
    if not platform_digests <= attestations:
        raise ValueError('Each published platform must have an attestation manifest.')


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--digest', required=True)
    parser.add_argument('--platform', action='append', required=True)
    args = parser.parse_args()
    expected = set()
    for platform in args.platform:
        try:
            operating_system, architecture = platform.split('/', 1)
        except ValueError:
            parser.error(f'Invalid platform: {platform}')
        expected.add((operating_system, architecture))
    try:
        verify_manifest(json.loads(args.manifest.read_text()), args.digest, expected)
    except (KeyError, OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
