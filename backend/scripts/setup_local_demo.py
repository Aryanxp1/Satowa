"""Create local-only reviewer credentials, then seed the synthetic walkthrough."""
from pathlib import Path
import json
import secrets


def ensure_local_env():
    env_path = Path(__file__).resolve().parents[1] / '.env'
    existing = env_path.read_text() if env_path.exists() else ''
    configured = any(line.strip().startswith('REVIEWER_TOKENS=') and
                     line.partition('=')[2].strip() for line in existing.splitlines())
    if not configured:
        token = secrets.token_urlsafe(32)
        prefix = '' if not existing or existing.endswith('\n') else '\n'
        with env_path.open('a') as stream:
            stream.write(prefix + 'REVIEWER_TOKENS=' + json.dumps({'Farhan': token}) + '\n')
        env_path.chmod(0o600)
        print('A local reviewer token was created in backend/.env (gitignored).')
    else:
        print('Using existing REVIEWER_TOKENS from backend/.env.')


if __name__ == '__main__':
    ensure_local_env()
    from seed_local_demo import seed
    seed()
