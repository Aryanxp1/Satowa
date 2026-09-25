"""Local JSON credentials remain optional and never override environment config."""
import json

import pytest

from app.config import Settings, apply_local_credentials, load_local_credentials


def test_local_credentials_fill_only_empty_settings(tmp_path):
    path = tmp_path / 'credential.json'
    path.write_text(json.dumps({
        'cloudinary': {'cloud_name': 'local-cloud', 'api_key': 'local-key',
                       'api_secret': 'local-secret'},
        'gemini': {'api_key': 'local-gemini'},
    }))
    settings = Settings(_env_file=None, CLOUDINARY_CLOUD_NAME='environment-cloud')
    apply_local_credentials(settings, load_local_credentials(path))
    assert settings.CLOUDINARY_CLOUD_NAME == 'environment-cloud'
    assert settings.CLOUDINARY_API_KEY == 'local-key'
    assert settings.CLOUDINARY_API_SECRET.get_secret_value() == 'local-secret'
    assert settings.GEMINI_API_KEY == 'local-gemini'


def test_empty_template_is_unconfigured(tmp_path):
    path = tmp_path / 'credential.json'
    path.write_text('{"cloudinary":{"cloud_name":"","api_key":"","api_secret":""},"gemini":{"api_key":""}}')
    settings = Settings(_env_file=None)
    apply_local_credentials(settings, load_local_credentials(path))
    assert settings.CLOUDINARY_CLOUD_NAME == ''
    assert settings.CLOUDINARY_API_SECRET.get_secret_value() == ''


@pytest.mark.parametrize('content', ['{bad json', '[]', '{"cloudinary": 7}',
                                     '{"cloudinary": {"api_secret": 7}}'])
def test_invalid_credentials_have_safe_error(tmp_path, content):
    path = tmp_path / 'credential.json'
    path.write_text(content)
    with pytest.raises(ValueError, match='credential.json'):
        load_local_credentials(path)
