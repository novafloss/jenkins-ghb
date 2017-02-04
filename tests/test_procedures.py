import asyncio
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from aiohttp.test_utils import make_mocked_coro
from asynctest import CoroutineMock
import pytest


@pytest.mark.asyncio
@asyncio.coroutine
def test_process_head(mocker, SETTINGS):
    Bot = mocker.patch('jenkins_epo.procedures.Bot')

    from jenkins_epo.procedures import process_head

    bot = Bot.return_value
    bot.run = CoroutineMock()
    head = Mock(sha='cafed0d0')
    head.repository.load_settings = CoroutineMock()

    yield from process_head(head)

    assert bot.run.mock_calls


@pytest.mark.asyncio
@asyncio.coroutine
def test_process_head_repo_denied(mocker, SETTINGS):
    Bot = mocker.patch('jenkins_epo.procedures.Bot')

    from jenkins_epo.procedures import process_head, UnauthorizedRepository

    bot = Bot.return_value
    head = Mock(sha='cafed0d0')
    head.repository.load_settings = CoroutineMock(
        side_effect=UnauthorizedRepository()
    )

    with pytest.raises(UnauthorizedRepository):
        yield from process_head(head)

    assert head.repository.load_settings.mock_calls
    assert not bot.run.mock_calls


@pytest.mark.asyncio
@asyncio.coroutine
def test_process_head_repo_failed(mocker, SETTINGS):
    Bot = mocker.patch('jenkins_epo.procedures.Bot')

    from jenkins_epo.procedures import process_head

    bot = Bot.return_value
    head = Mock(sha='cafed0d0')
    head.repository.load_settings.side_effect = ValueError()

    with pytest.raises(ValueError):
        yield from process_head(head)

    assert head.repository.load_settings.mock_calls
    assert not bot.run.mock_calls


@pytest.mark.asyncio
@asyncio.coroutine
def test_process_head_cancelled(mocker, SETTINGS):
    Bot = mocker.patch('jenkins_epo.procedures.Bot')

    from jenkins_epo.procedures import process_head, CancelledError

    bot = Bot.return_value
    bot.run = CoroutineMock(side_effect=CancelledError())
    head = Mock(sha='cafed0d0')
    head.repository.load_settings = CoroutineMock()

    yield from process_head(head)

    assert bot.run.mock_calls


@pytest.mark.asyncio
@asyncio.coroutine
def test_process_head_log_exception(mocker, SETTINGS):
    Bot = mocker.patch('jenkins_epo.procedures.Bot')

    from jenkins_epo.procedures import process_head

    bot = Bot.return_value
    bot.run = CoroutineMock(side_effect=ValueError('POUET'))
    head = Mock(sha='cafed0d0')
    head.repository.load_settings = CoroutineMock()

    yield from process_head(head)

    assert bot.run.mock_calls


@pytest.mark.asyncio
@asyncio.coroutine
def test_process_head_raise_exception(mocker, SETTINGS):
    Bot = mocker.patch('jenkins_epo.procedures.Bot')
    SETTINGS.DEBUG = 1

    from jenkins_epo.procedures import process_head

    bot = Bot.return_value
    bot.run = CoroutineMock(side_effect=ValueError('POUET'))
    head = Mock(sha='cafed0d0')
    head.repository.load_settings = CoroutineMock()

    with pytest.raises(ValueError):
        yield from process_head(head)

    assert bot.run.mock_calls


@pytest.mark.asyncio
@asyncio.coroutine
def test_whoami(mocker):
    mocker.patch(
        'jenkins_epo.procedures.cached_arequest',
        make_mocked_coro(return_value=dict(login='aramis')),
    )

    from jenkins_epo import procedures

    login = yield from procedures.whoami()

    assert 'aramis' == login


@patch('jenkins_epo.procedures.Repository.from_name')
def test_list_repositories(from_name, SETTINGS):
    from jenkins_epo import procedures

    SETTINGS.REPOSITORIES = "owner/repo1,owner/repo1"
    repositories = procedures.list_repositories()
    assert 1 == len(list(repositories))


@patch('jenkins_epo.procedures.Repository.from_name')
def test_list_repositories_from_envvar_404(from_name, SETTINGS):
    from jenkins_epo import procedures

    SETTINGS.REPOSITORIES = "owner/repo1 owner/repo1"
    from_name.side_effect = Exception('404')

    repositories = procedures.list_repositories()

    assert 0 == len(list(repositories))


@pytest.mark.asyncio
@asyncio.coroutine
def test_throttle_sleep(mocker, SETTINGS):
    GITHUB = mocker.patch('jenkins_epo.procedures.GITHUB')
    GITHUB.rate_limit.aget = CoroutineMock(return_value=dict())
    compute_throttling = mocker.patch(
        'jenkins_epo.procedures.compute_throttling'
    )
    sleep = mocker.patch(
        'jenkins_epo.procedures.asyncio.sleep', CoroutineMock(name='sleep'),
    )

    from jenkins_epo.procedures import throttle_github

    compute_throttling.return_value = 100

    yield from throttle_github()

    assert sleep.mock_calls


def test_throttling_compute_early(SETTINGS):
    SETTINGS.RATE_LIMIT_THRESHOLD = 0
    from jenkins_epo.procedures import compute_throttling

    remaining = 4900
    seconds = compute_throttling(
        now=Mock(),
        rate_limit=dict(rate=dict(
            limit=5000, remaining=remaining,
        )),
    )
    assert 0 == seconds


def test_throttling_compute_fine(SETTINGS):
    SETTINGS.RATE_LIMIT_THRESHOLD = 0
    from jenkins_epo.procedures import compute_throttling

    # Consumed 1/5 calls at 2/3 of the time.
    now = datetime(2017, 1, 18, 14, 40, tzinfo=timezone.utc)
    reset = datetime(2017, 1, 18, 15, tzinfo=timezone.utc)
    remaining = 4000
    seconds = compute_throttling(
        now=now,
        rate_limit=dict(rate=dict(
            limit=5000, remaining=remaining,
            reset=reset.timestamp(),
        )),
    )
    assert 0 == seconds  # Fine !


def test_throttling_compute_chill(SETTINGS):
    SETTINGS.RATE_LIMIT_THRESHOLD = 0
    from jenkins_epo.procedures import compute_throttling

    # Consumed 4/5 calls at 1/3 of the time.
    seconds = compute_throttling(
        now=datetime(2017, 1, 18, 14, 20, tzinfo=timezone.utc),
        rate_limit=dict(rate=dict(
            limit=5000, remaining=1000,
            reset=datetime(2017, 1, 18, 15, tzinfo=timezone.utc).timestamp(),
        )),
    )

    assert seconds > 0  # Chill !


@pytest.mark.asyncio
@asyncio.coroutine
def test_process_url(mocker):
    mod = 'jenkins_epo.procedures'
    whoami = mocker.patch(mod + '.whoami', CoroutineMock())
    from_url = mocker.patch(mod + '.Head.from_url', CoroutineMock())
    process_head = mocker.patch(mod + '.process_head', CoroutineMock())

    from jenkins_epo.procedures import process_url

    yield from process_url('https//github/owner/name/pull/1')

    assert whoami.mock_calls
    assert from_url.mock_calls
    assert process_head.mock_calls


@pytest.mark.asyncio
@asyncio.coroutine
def test_queue_heads(mocker):
    list_repositories = mocker.patch(
        'jenkins_epo.procedures.list_repositories'
    )
    list_repositories.return_value = []

    from jenkins_epo.procedures import queue_heads
    from jenkins_epo.compat import PriorityQueue

    yield from queue_heads(PriorityQueue())
    assert list_repositories.mock_calls
