import asyncio
from datetime import datetime

from asynctest import CoroutineMock, Mock
import pytest


@pytest.mark.asyncio
@asyncio.coroutine
def test_from_name(mocker):
    cached_arequest = mocker.patch(
        'jenkins_epo.repository.cached_arequest',
        CoroutineMock()
    )
    from jenkins_epo.repository import Repository

    cached_arequest.return_value = {
        'owner': {'login': 'newowner'},
        'name': 'newname',
    }

    repo = yield from Repository.from_name('oldowner', 'oldname')
    assert 'newowner' == repo.owner
    assert 'newname' == repo.name
    assert repo in {repo}
    assert repo == repo


def test_registry(SETTINGS):
    SETTINGS.REPOSITORIES = 'owner/name'
    from jenkins_epo.repository import RepositoriesRegistry

    registry = RepositoriesRegistry()

    assert 'owner/name' in registry


@pytest.mark.asyncio
@asyncio.coroutine
def test_fetch_hooks(mocker):
    cached_arequest = mocker.patch('jenkins_epo.repository.cached_arequest')
    from jenkins_epo.repository import Repository

    yield from Repository('owner', 'name').fetch_hooks()

    assert cached_arequest.mock_calls


@pytest.mark.asyncio
@asyncio.coroutine
def test_fetch_protected_branches(mocker):
    cached_arequest = mocker.patch('jenkins_epo.repository.cached_arequest')
    from jenkins_epo.repository import Repository

    yield from Repository('owner', 'name').fetch_protected_branches()

    assert cached_arequest.mock_calls


@pytest.mark.asyncio
@asyncio.coroutine
def test_fetch_commit(mocker):
    cached_arequest = mocker.patch('jenkins_epo.repository.cached_arequest')
    from jenkins_epo.repository import Repository

    cached_arequest.return_value = []

    yield from Repository('owner', 'name').fetch_commit('cafedodo')


def test_process_hooks():
    from jenkins_epo.repository import Repository

    repo = Repository('owner', 'name')
    hooks = list(repo.process_hooks([
        dict(name='jenkins'),
        dict(name='web', config=dict(url='http://other')),
        dict(name='web', config=dict(url='http://me')),
    ], webhook_url='http://me'))

    assert 1 == len(hooks)


def test_process_protected_branches():
    from jenkins_epo.repository import Repository

    repo = Repository('owner', 'name')
    repo.heads_filter = ['*', '-*/skip']
    branches = list(repo.process_protected_branches([
        {
            'name': 'master',
            'commit': {'sha': 'd0d0cafec0041edeadbeef'},
        },
        {
            'name': 'skip',
            'commit': {'sha': 'pouetpouet'},
        },
    ]))

    assert 1 == len(branches)
    head = branches[0]
    assert 'refs/heads/master' == head.fullref
    assert 'master' == head.ref
    assert head.url.startswith('https://github.com')


@pytest.mark.asyncio
@asyncio.coroutine
def test_fetch_pull_requests(mocker):
    cached_arequest = mocker.patch('jenkins_epo.repository.cached_arequest')
    from jenkins_epo.repository import Repository

    yield from Repository('owner', 'name').fetch_pull_requests()

    assert cached_arequest.mock_calls


def test_process_pulls():
    from jenkins_epo.repository import Repository

    repo = Repository('owner', 'name')
    repo.heads_filter = ['*2']

    heads = list(repo.process_pull_requests([
        dict(
            html_url='https://github.com/owner/repo/pull/2',
            number=2,
            head=dict(
                repo=dict(html_url='https://.../owner/repo'),
                ref='feature', sha='d0d0',
            ),
        ),
        dict(
            html_url='https://github.com/owner/repo/pull/3',
            number=3,
            head=dict(
                repo=dict(html_url='https://.../owner/repo'),
                ref='hotfix', sha='cafe',
            ),
        ),
    ]))

    assert 1 == len(heads)
    head = heads[0]
    assert 'refs/heads/feature' == head.fullref
    assert 'feature' == head.ref
    assert head.url.startswith('https://github.com')


@pytest.mark.asyncio
@asyncio.coroutine
def test_load_settings_no_yml(mocker):
    GITHUB = mocker.patch('jenkins_epo.repository.GITHUB')
    unpaginate = mocker.patch(
        'jenkins_epo.repository.unpaginate',
        CoroutineMock(return_value=[]),
    )
    from jenkins_epo.repository import ApiNotFoundError, Repository

    GITHUB.fetch_file_contents = CoroutineMock(side_effect=ApiNotFoundError(
        'url', Mock(), Mock())
    )

    repo = Repository('owner', 'repo1')
    yield from repo.load_settings()

    assert GITHUB.fetch_file_contents.mock_calls
    assert unpaginate.mock_calls


@pytest.mark.asyncio
@asyncio.coroutine
def test_load_settings_collaborators_denied(mocker):
    GITHUB = mocker.patch('jenkins_epo.repository.GITHUB')
    unpaginate = mocker.patch(
        'jenkins_epo.repository.unpaginate', CoroutineMock(),
    )
    from jenkins_epo.repository import (
        Repository, ApiNotFoundError, UnauthorizedRepository,
    )

    GITHUB.fetch_file_contents = CoroutineMock(
        return_value=repr(dict(settings=dict(branches=['master'])))
    )
    unpaginate.side_effect = ApiNotFoundError('u', Mock(), Mock())

    repo = Repository('owner', 'repo1')
    with pytest.raises(UnauthorizedRepository):
        yield from repo.load_settings()

    assert GITHUB.fetch_file_contents.mock_calls
    assert unpaginate.mock_calls


def test_load_settings_collaborators_override(mocker):
    cached_arequest = mocker.patch(
        'jenkins_epo.repository.cached_arequest',
        CoroutineMock()
    )
    GITHUB = mocker.patch('jenkins_epo.repository.GITHUB')

    from jenkins_epo.repository import Repository

    GITHUB.fetch_file_contents.side_effect = [
        repr(dict(settings=dict(branches=['master'], collaborators=['octo']))),
    ]

    repo = Repository('owner', 'repo1')
    repo.load_settings()

    assert not cached_arequest.mock_calls


def test_load_settings_already_loaded():
    from jenkins_epo.repository import Repository

    repo = Repository('owner', 'repo1')
    repo.SETTINGS.update({'COLLABORATORS': ['bdfl']})
    repo.load_settings()


def test_process_jenkins_yml_settings():
    from jenkins_epo.repository import Repository

    repo = Repository('owner', 'repo1')
    repo.process_settings(
        jenkins_yml=repr(dict(
            settings=dict(collaborators=['bdfl', 'hacker']))
        ),
    )
    assert ['bdfl', 'hacker'] == repo.SETTINGS.COLLABORATORS


def test_process_jenkins_yml_settings_reviewers_compat():
    from jenkins_epo.repository import Repository

    repo = Repository('owner', 'repo1')
    repo.process_settings(
        jenkins_yml=repr(dict(settings=dict(reviewers=['bdfl']))),
    )
    assert ['bdfl'] == repo.SETTINGS.COLLABORATORS


def test_collaborators():
    from jenkins_epo.repository import Repository

    repo = Repository('owner', 'repository')
    repo.process_settings(collaborators=[
        {'login': 'siteadmin', 'site_admin': True},
        {
            'login': 'contributor',
            'permissions': {'admin': False, 'pull': False, 'push': False},
            'site_admin': False,
        },
        {
            'login': 'pusher',
            'permissions': {'admin': False, 'pull': True, 'push': True},
            'site_admin': False,
        },
        {
            'login': 'owner',
            'permissions': {'admin': True, 'pull': True, 'push': True},
            'site_admin': False,
        },
    ])

    collaborators = repo.SETTINGS.COLLABORATORS

    assert 'siteadmin' in collaborators
    assert 'contributor' not in collaborators
    assert 'pusher' in collaborators
    assert 'owner' in collaborators


def test_process_commits():
    from jenkins_epo.repository import Repository

    repo = Repository('owner', 'name')
    items = list(repo.process_commits([dict(sha='cafed0d0')]))
    assert 1 == len(items)


@pytest.mark.asyncio
@asyncio.coroutine
def test_set_hook(mocker):
    GITHUB = mocker.patch('jenkins_epo.repository.GITHUB')

    from jenkins_epo.repository import Repository

    repo = Repository('owner', 'name')

    yield from repo.set_hook(dict())
    assert GITHUB.repos().hooks.apost.mock_calls

    yield from repo.set_hook(dict(), hookid='1231')
    assert GITHUB.repos().hooks().apatch.mock_calls


@pytest.mark.asyncio
@asyncio.coroutine
def test_fetch_comments(mocker):
    cached_arequest = mocker.patch(
        'jenkins_epo.repository.cached_arequest',
        CoroutineMock(return_value=[dict()])
    )

    from jenkins_epo.repository import Commit

    commit = Commit(Mock(), 'd0d0cafe')
    payload = yield from commit.fetch_comments()
    assert len(payload)
    assert cached_arequest.mock_calls


@pytest.mark.asyncio
@asyncio.coroutine
def test_report_issue(mocker):
    GITHUB = mocker.patch('jenkins_epo.repository.GITHUB')
    GITHUB.repos().issues.apost = CoroutineMock()

    from jenkins_epo.repository import Repository

    repo = Repository('owner', 'name')

    GITHUB.dry = 1
    payload = yield from repo.report_issue('title', 'body')
    assert not GITHUB.repos().issues.apost.mock_calls
    assert 0 == payload['number']

    GITHUB.dry = 0
    yield from repo.report_issue('title', 'body')
    assert GITHUB.repos().issues.apost.mock_calls


@pytest.mark.asyncio
@asyncio.coroutine
def test_fetch_status(mocker):
    cached_arequest = mocker.patch('jenkins_epo.repository.cached_arequest')
    cached_arequest.return_value = payload = dict(status=True)

    from jenkins_epo.repository import Commit

    commit = Commit(Mock(), 'd0d0cafe')
    payload = yield from commit.fetch_statuses()
    assert payload['status'] is True


@pytest.mark.asyncio
@asyncio.coroutine
def test_fetch_status_ignore(SETTINGS, mocker):
    SETTINGS.IGNORE_STATUSES = 1
    cached_arequest = mocker.patch('jenkins_epo.repository.cached_arequest')

    from jenkins_epo.repository import Commit

    commit = Commit(Mock(), 'd0d0cafe')
    payload = yield from commit.fetch_statuses()

    assert not payload['statuses']
    assert not cached_arequest.mock_calls


@pytest.mark.asyncio
@asyncio.coroutine
def test_process_status(mocker):
    push_status = mocker.patch(
        'jenkins_epo.repository.Commit.push_status',
        CoroutineMock()
    )
    from jenkins_epo.repository import Commit, CommitStatus

    commit = Commit(Mock(), 'd0d0')
    commit.contexts_filter = []
    commit.process_statuses({'statuses': [{
        'context': 'job1',
        'state': 'pending',
        'target_url': 'http://jenkins/job/url',
        'updated_at': '2016-06-27T11:58:31Z',
        'description': 'Queued!',
    }]})

    assert 'job1' in commit.statuses

    push_status.return_value = None

    yield from commit.maybe_update_status(CommitStatus(context='context'))


def test_sort_status():
    from jenkins_epo.repository import CommitStatus

    error = CommitStatus(context='job1', state='error')
    failure = CommitStatus(context='job1', state='failure')
    pending = CommitStatus(context='job1', state='pending')
    success = CommitStatus(context='job1', state='success')

    assert 'error' in repr(error)
    assert error < failure
    assert failure < pending
    assert pending < success


@pytest.mark.asyncio
@asyncio.coroutine
def test_update_status(mocker):
    push_status = mocker.patch(
        'jenkins_epo.repository.Commit.push_status',
        CoroutineMock()
    )
    from jenkins_epo.repository import Commit, CommitStatus

    commit = Commit(Mock(), 'd0d0')
    commit.statuses = {}
    push_status.return_value = {
        'context': 'job',
        'updated_at': '2016-08-30T08:25:56Z',
    }

    yield from commit.maybe_update_status(
        CommitStatus(context='job', state='success')
    )

    assert 'job' in commit.statuses


@pytest.mark.asyncio
@asyncio.coroutine
def test_push_status_dry(mocker):
    GITHUB = mocker.patch('jenkins_epo.repository.GITHUB')
    from datetime import datetime
    from jenkins_epo.repository import Commit, CommitStatus

    GITHUB.dry = 1

    commit = Commit(Mock(), 'd0d0')
    commit.statuses = {}
    status = yield from commit.push_status(CommitStatus(
        context='job', state='success', description='desc',
        updated_at=datetime(2016, 9, 13, 13, 41, 00),
    ))
    assert isinstance(status['updated_at'], str)


@pytest.mark.asyncio
@asyncio.coroutine
def test_push_status_1000(mocker):
    GITHUB = mocker.patch('jenkins_epo.repository.GITHUB')
    from jenkins_epo.repository import Commit, ApiError

    GITHUB.dry = False
    GITHUB.repos.return_value.statuses.return_value.apost.side_effect = (
        ApiError('url', Mock(), dict(json=dict()))
    )
    commit = Commit(Mock(), 'd0d0')
    commit.statuses = {}
    status = yield from commit.push_status({
        'context': 'job', 'description': '', 'state': 'success',
    })
    assert status
    assert GITHUB.repos().statuses().apost.mock_calls


@pytest.mark.asyncio
@asyncio.coroutine
def test_push_status(mocker):
    GITHUB = mocker.patch('jenkins_epo.repository.GITHUB')
    from jenkins_epo.repository import Commit

    GITHUB.dry = False
    GITHUB.repos().statuses().apost = CoroutineMock()
    commit = Commit(Mock(), 'd0d0')
    commit.statuses = {}
    status = yield from commit.push_status({
        'context': 'job', 'description': '', 'state': 'success',
    })
    assert status
    assert GITHUB.repos().statuses().apost.mock_calls


def test_filter_contextes():
    from jenkins_epo.repository import Commit, CommitStatus

    rebuild_failed = datetime(2016, 8, 11, 16)

    commit = Commit(Mock(), 'd0d0')
    commit.statuses = {
        'backed': CommitStatus({'state': 'pending', 'description': 'Backed'}),
        'errored': {
            'state': 'error',
            'updated_at': datetime(2016, 8, 11, 10),
        },
        'failed': {
            'state': 'failure',
            'updated_at': datetime(2016, 8, 11, 10),
        },
        'green': {'state': 'success', 'description': 'Success!'},
        'newfailed': {
            'state': 'error',
            'updated_at': datetime(2016, 8, 11, 20),
        },
        'queued': {'state': 'pending', 'description': 'Queued'},
        'running': {'state': 'pending', 'description': 'build #789'},
        'skipped': {
            'state': 'success', 'description': 'Skipped',
            'updated_at': datetime(2016, 8, 11, 10),
        },
    }

    not_built = list(commit.filter_not_built_contexts(
        [
            'backed', 'errored', 'failed', 'green', 'newfailed', 'notbuilt',
            'queued', 'running', 'skipped',
        ],
        rebuild_failed,
    ))

    assert 'backed' in not_built
    assert 'errored' in not_built
    assert 'failed' in not_built
    assert 'green' not in not_built
    assert 'newfailed' not in not_built
    assert 'not_built' not in not_built
    assert 'queued' in not_built
    assert 'running' not in not_built
    assert 'skipped' in not_built


@pytest.mark.asyncio
@asyncio.coroutine
def test_fetch_combined(mocker):
    cached_arequest = mocker.patch(
        'jenkins_epo.repository.cached_arequest', CoroutineMock()
    )
    from jenkins_epo.repository import Commit

    commit = Commit(Mock(), sha='x')

    ret = yield from commit.fetch_combined_status()

    assert ret == cached_arequest.return_value
    assert cached_arequest.mock_calls


def test_commit_date():
    from jenkins_epo.repository import Commit

    commit = Commit(Mock(), 'd0d0')
    assert repr(commit)

    commit.payload = {'author': {'date': '2016-10-11T14:45:00Z'}}

    assert 2016 == commit.date.year

    commit.payload = dict(commit=commit.payload)

    assert 2016 == commit.date.year


def test_webhook():
    from jenkins_epo.repository import WebHook

    a = WebHook(dict(name='web', active=True, config=dict(), events=[]))
    b = WebHook(dict(a, test_url='http://..'))

    assert a == b
