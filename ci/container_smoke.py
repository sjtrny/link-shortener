"""Exercise built images using isolated Docker resources, including remote daemons."""

import argparse
import json
from pathlib import Path
import secrets
import subprocess
import tempfile
import time
import uuid


PROBE = Path(__file__).with_name('container_probe.py').read_text()
PYTHON = '/app/.venv/bin/python'
READY = (
    "import http.client; c=http.client.HTTPConnection('127.0.0.1',8000,timeout=2); "
    "c.request('GET','/',headers={'Host':'short.example'}); assert c.getresponse().status==301"
)


class SmokeTest:
    def __init__(self, image, baseline, directory):
        self.image = image
        self.baseline = baseline
        self.directory = Path(directory)
        self.prefix = 'link-shortener-ci-' + uuid.uuid4().hex[:12]
        self.containers = set()
        self.volumes = []
        self.secret = secrets.token_urlsafe(64)
        self.password = secrets.token_urlsafe(32)
        self.env_file = self.directory / 'app.env'
        self.env_file.write_text('\n'.join([
            f'DJANGO_SECRET_KEY={self.secret}',
            'DJANGO_ALLOWED_HOSTS=short.example,go.example',
            'DJANGO_CSRF_TRUSTED_ORIGINS=https://short.example',
            'SHORTLINK_BASE_URL=https://go.example',
            'FORWARDED_ALLOW_IPS=127.0.0.1',
            'DJANGO_SUPERUSER_USERNAME=ci-admin',
            'DJANGO_SUPERUSER_EMAIL=ci@example.com',
            f'DJANGO_SUPERUSER_PASSWORD={self.password}',
        ]) + '\n')
        self.env_file.chmod(0o600)

    def docker(self, *arguments, check=True, **kwargs):
        result = subprocess.run(['docker', *arguments], capture_output=True, text=True, timeout=90, **kwargs)
        if check and result.returncode:
            output = (result.stdout + result.stderr).replace(self.secret, '[redacted]').replace(self.password, '[redacted]')
            raise RuntimeError(f'Docker command failed ({arguments[0]}):\n{output}')
        return result

    def volume(self, suffix):
        name = f'{self.prefix}-{suffix}'
        self.docker('volume', 'create', name)
        self.volumes.append(name)
        return name

    def start(self, suffix, volume, *, baseline=False):
        name = f'{self.prefix}-{suffix}'
        self.containers.add(name)
        flags = [] if baseline else [
            '--read-only', '--tmpfs', '/tmp:rw,noexec,nosuid,size=64m',
            '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
        ]
        self.docker('run', '-d', '--name', name, '--network', 'none', '--env-file', str(self.env_file),
                    '-v', f'{volume}:/app/data', *flags, self.baseline if baseline else self.image)
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            state = json.loads(self.docker('inspect', name).stdout)[0]['State']
            if not state['Running']:
                raise RuntimeError(f'{suffix} stopped during startup')
            if baseline:
                if self.docker('exec', name, PYTHON, '-c', READY, check=False).returncode == 0:
                    break
            elif state.get('Health', {}).get('Status') == 'healthy':
                break
            time.sleep(1)
        else:
            raise RuntimeError(f'{suffix} did not become ready')
        if not baseline:
            config = json.loads(self.docker('inspect', name).stdout)[0]
            assert config['Config']['User'] == '10001:10001'
            assert config['HostConfig']['ReadonlyRootfs']
            assert config['HostConfig']['CapDrop'] == ['ALL']
            assert not config['NetworkSettings']['Ports']
            self.docker('exec', name, PYTHON, '-m', 'config.healthcheck')
        return name

    def probe(self, container, *checks):
        result = self.docker('exec', '-i', container, PYTHON, '-', *checks, input=PROBE)
        print(result.stdout, end='', flush=True)

    def stop(self, container):
        self.docker('stop', '--time', '35', container)
        state = json.loads(self.docker('inspect', container).stdout)[0]['State']
        assert state['ExitCode'] == 0, 'Container did not stop cleanly'
        self.docker('rm', container)
        self.containers.remove(container)

    def snapshot(self, volume, archive, *, restore=False):
        name = f'{self.prefix}-archive'
        self.containers.add(name)
        command = ['docker', 'run', '--rm', '--name', name, '--network', 'none', '--read-only',
                   '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
                   '-v', f'{volume}:/app/data', '--entrypoint', 'tar', self.image, '-C', '/app/data']
        if restore:
            # Docker needs -i before the image to read the archive stream.
            command.insert(2, '-i')
            with archive.open('rb') as source:
                subprocess.run([*command, '-xzf', '-', '--no-same-owner'], stdin=source, check=True, timeout=60)
        else:
            with archive.open('wb') as destination:
                archive.chmod(0o600)
                subprocess.run([*command, '-czf', '-', '.'], stdout=destination, check=True, timeout=60)
        self.containers.remove(name)

    def run(self):
        metadata = json.loads(self.docker('image', 'inspect', self.image).stdout)[0]['Config']
        assert metadata['Labels']['org.opencontainers.image.source'] == 'https://github.com/sjtrny/link-shortener'
        assert not any(value.startswith('DJANGO_SECRET_KEY=') for value in metadata['Env'])
        volume = self.volume('fresh')
        container = self.start('fresh', volume)
        self.probe(container, 'seed', 'runtime', 'persisted', 'http')
        self.stop(container)
        container = self.start('replacement', volume)
        self.probe(container, 'persisted', 'http')
        self.stop(container)
        print('Passed fresh install and container replacement', flush=True)

        archive = self.directory / 'backup.tar.gz'
        self.snapshot(volume, archive)
        restored = self.volume('restored')
        self.snapshot(restored, archive, restore=True)
        # A custom command must not migrate, bootstrap an admin, or need deployment secrets.
        result = self.docker('run', '--rm', '--network', 'none', '--read-only', '-v', f'{restored}:/app/data',
                             self.image, 'python', '-c',
                             "import sqlite3; c=sqlite3.connect('file:/app/data/db.sqlite3?mode=ro',uri=True); "
                             "assert c.execute('PRAGMA integrity_check').fetchall()==[('ok',)]; print('integrity ok')")
        assert result.stdout.strip() == 'integrity ok'
        container = self.start('restored', restored)
        self.probe(container, 'runtime', 'persisted', 'http')
        self.stop(container)
        print('Passed offline backup and restore into a new volume', flush=True)

        upgraded = self.volume('upgrade')
        container = self.start('baseline', upgraded, baseline=True)
        self.probe(container, 'seed', 'persisted')
        self.stop(container)
        container = self.start('upgrade', upgraded)
        self.probe(container, 'runtime', 'persisted', 'http')
        self.stop(container)
        print('Passed upgrade from the baseline image', flush=True)

    def cleanup(self):
        for container in sorted(self.containers):
            logs = self.docker('logs', '--tail', '80', container, check=False)
            output = (logs.stdout + logs.stderr).replace(self.secret, '[redacted]').replace(self.password, '[redacted]')
            print(f'Container diagnostics ({container}):\n{output}', flush=True)
            self.docker('rm', '--force', container, check=False)
        for volume in self.volumes:
            self.docker('volume', 'rm', volume)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True, help='Locally built candidate image')
    parser.add_argument('--upgrade-from', required=True, help='Locally built baseline image')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='link-shortener-ci-') as directory:
        suite = SmokeTest(args.image, args.upgrade_from, directory)
        try:
            suite.run()
        finally:
            suite.cleanup()


if __name__ == '__main__':
    main()
