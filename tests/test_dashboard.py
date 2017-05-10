import asyncio

from asynctest import Mock
import pytest


@pytest.mark.asyncio
@asyncio.coroutine
def test_repositories(mocker):
    mocker.patch('jenkins_epo.web.REPOSITORIES', ['owner/repo'])
    from jenkins_epo.web import repositories

    response = yield from repositories(Mock())

    assert 'json' in response.content_type
    assert 'owner' in response.text


@pytest.mark.asyncio
@asyncio.coroutine
def test_heads(mocker):
    from jenkins_epo.repository import Repository
    Repository = mocker.patch(
        'jenkins_epo.web.Repository', Mock(spec=Repository),
    )
    Repository.from_name.return_value.fetch_protected_branches.return_value = [
        dict(name='master')
    ]

    from jenkins_epo.web import heads

    request = Mock(match_info=dict(owner='owner', name='repo'))
    response = yield from heads(request)

    assert 'json' in response.content_type
