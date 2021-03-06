import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from asynctest import CoroutineMock
import pytest


@pytest.mark.asyncio
@asyncio.coroutine
def test_yml_notfound(mocker, SETTINGS):
    GITHUB = mocker.patch('jenkins_epo.extensions.core.GITHUB')

    from jenkins_epo.extensions.core import (
        ApiNotFoundError, SkipHead, YamlExtension
    )

    SETTINGS.update(YamlExtension.SETTINGS)

    ext = YamlExtension('ext', Mock())
    ext.current = ext.bot.current
    ext.current.yaml = {}
    ext.current.errors = []
    ext.current.job_specs = []

    GITHUB.fetch_file_contents = CoroutineMock(side_effect=ApiNotFoundError(
        'url', Mock(), Mock())
    )

    head = ext.current.head
    head.repository.url = 'https://github.com/owner/repo.git'
    head.repository.jobs = []

    with pytest.raises(SkipHead):
        yield from ext.run()

    assert GITHUB.fetch_file_contents.mock_calls
    assert not ext.current.errors
    assert not ext.current.job_specs


@pytest.mark.asyncio
@asyncio.coroutine
def test_yml_invalid(mocker, SETTINGS):
    GITHUB = mocker.patch('jenkins_epo.extensions.core.GITHUB')
    from jenkins_epo.extensions.core import YamlExtension

    ext = YamlExtension('ext', Mock())
    ext.current = ext.bot.current
    ext.current.yaml = {}
    ext.current.errors = []

    GITHUB.fetch_file_contents = CoroutineMock(return_value="{INVALID")

    head = ext.current.head
    head.repository.url = 'https://github.com/owner/repo.git'
    head.repository.jobs = []

    yield from ext.run()

    assert GITHUB.fetch_file_contents.mock_calls
    assert ext.current.errors


@pytest.mark.asyncio
@asyncio.coroutine
def test_yml_found(mocker, SETTINGS):
    GITHUB = mocker.patch('jenkins_epo.extensions.core.GITHUB')
    Job = mocker.patch('jenkins_epo.extensions.core.Job')
    from jenkins_epo.extensions.core import YamlExtension

    Job.jobs_filter = ['*', '-skip']
    SETTINGS.update(YamlExtension.SETTINGS)

    ext = YamlExtension('ext', Mock())
    ext.current = ext.bot.current
    ext.current.yaml = {'job': dict()}

    GITHUB.fetch_file_contents = CoroutineMock(
        return_value="job: command\nskip: command",
    )

    head = ext.current.head
    head.repository.url = 'https://github.com/owner/repo.git'
    head.repository.jobs = {}

    yield from ext.run()

    assert GITHUB.fetch_file_contents.mock_calls
    assert 'job' in ext.current.job_specs
    assert 'skip' not in ext.current.job_specs


def test_yml_comment_dict():
    from jenkins_epo.bot import Instruction
    from jenkins_epo.extensions.core import YamlExtension

    ext = YamlExtension('ext', Mock())
    ext.current = ext.bot.current
    ext.current.yaml = {}

    ext.process_instruction(Instruction(
        author='a', name='yaml', args=dict(job=dict(parameters=dict(PARAM1=1)))
    ))

    ext.process_instruction(Instruction(
        author='a', name='params', args=dict(job=dict(PARAM2=1))
    ))

    assert 'PARAM1' in ext.current.yaml['job']['parameters']
    assert 'PARAM2' in ext.current.yaml['job']['parameters']


def test_yml_comment_wrong():
    from jenkins_epo.bot import Instruction
    from jenkins_epo.extensions.core import YamlExtension

    ext = YamlExtension('ext', Mock())
    ext.current = ext.bot.current
    ext.current.yaml = {}
    ext.current.errors = []

    ext.process_instruction(Instruction(author='a', name='yaml', args=None))

    assert ext.current.errors


@pytest.mark.asyncio
@asyncio.coroutine
def test_yml_override_unknown_job(mocker, SETTINGS):
    GITHUB = mocker.patch('jenkins_epo.extensions.core.GITHUB')
    from jenkins_epo.extensions.core import YamlExtension

    GITHUB.fetch_file_contents = CoroutineMock(return_value='{}')

    ext = YamlExtension('ext', Mock())
    ext.current = ext.bot.current
    ext.current.errors = []
    ext.current.head.repository.jobs = []
    ext.current.yaml = {'unknown_jobs': {}}

    yield from ext.run()

    assert ext.current.errors


def test_yml_list_specs(SETTINGS):
    from jenkins_epo.extensions.core import YamlExtension

    SETTINGS.update(YamlExtension.SETTINGS)

    ext = YamlExtension('ext', Mock())
    ext.current = ext.bot.current
    ext.current.head.repository.url = 'https://github.com/o/n'

    jobs = ext.list_job_specs("job: command")

    assert 'job' in jobs


@patch('jenkins_epo.extensions.jenkins.JENKINS')
def test_job_new(JENKINS):
    from jenkins_epo.extensions.jenkins import CreateJobsExtension

    ext = CreateJobsExtension('createjob', Mock())
    ext.current = ext.bot.current
    ext.current.refresh_jobs = None
    ext.current.job_specs = {'new_job': Mock(config=dict())}
    ext.current.job_specs['new_job'].name = 'new_job'
    ext.current.jobs = {}

    res = [x for x in ext.process_job_specs()]
    assert res

    action, spec = res[0]

    assert action == JENKINS.create_job


@patch('jenkins_epo.extensions.jenkins.JENKINS')
def test_job_uptodate(JENKINS):
    from jenkins_epo.extensions.jenkins import CreateJobsExtension

    ext = CreateJobsExtension('createjob', Mock())
    ext.current = ext.bot.current
    ext.current.refresh_jobs = None
    ext.current.job_specs = {'job': Mock()}
    ext.current.job_specs['job'].name = 'job'
    ext.current.jobs = {'job': Mock()}
    ext.current.jobs['job'].spec.contains.return_value = True

    res = [x for x in ext.process_job_specs()]

    assert not res


def test_job_update():
    from jenkins_epo.extensions.jenkins import CreateJobsExtension

    ext = CreateJobsExtension('createjob', Mock())
    ext.current = ext.bot.current
    ext.current.refresh_jobs = None
    ext.current.job_specs = {'new_job': Mock(config=dict())}
    ext.current.job_specs['new_job'].name = 'new_job'
    job = Mock()
    job.spec.contains.return_value = False
    ext.current.jobs = {'new_job': job}

    res = [x for x in ext.process_job_specs()]
    assert res

    action, spec = res[0]

    assert action == job.update


@pytest.mark.asyncio
@asyncio.coroutine
def test_jenkins_create_success(mocker):
    process_job_specs = mocker.patch(
        'jenkins_epo.extensions.jenkins.CreateJobsExtension.process_job_specs'
    )
    JENKINS = mocker.patch('jenkins_epo.extensions.jenkins.JENKINS')
    from jenkins_yml.job import Job as JobSpec
    from jenkins_epo.extensions.jenkins import CreateJobsExtension, UnknownJob

    ext = CreateJobsExtension('createjob', Mock())
    ext.current = ext.bot.current
    ext.current.head.sha = 'cafed0d0'
    ext.current.head.repository.jobs = {}
    ext.current.job_specs = dict(new=JobSpec('new', dict(periodic=True)))
    ext.current.jobs = {}
    ext.current.last_commit.push_status = CoroutineMock()
    JENKINS.aget_job = CoroutineMock(side_effect=UnknownJob('POUET'))
    JENKINS.create_job = CoroutineMock()
    job = JENKINS.create_job.return_value
    job.name = 'new'
    process_job_specs.return_value = [(JENKINS.create_job, Mock())]

    yield from ext.run()

    assert not ext.current.errors.append.mock_calls
    assert JENKINS.aget_job.mock_calls
    assert JENKINS.create_job.mock_calls
    assert ext.current.jobs['new'] == JENKINS.create_job.return_value


@pytest.mark.asyncio
@asyncio.coroutine
def test_jenkins_fails_existing(mocker):
    process_job_specs = mocker.patch(
        'jenkins_epo.extensions.jenkins.CreateJobsExtension.process_job_specs'
    )

    from jenkins_yml.job import Job as JobSpec
    from jenkins_epo.extensions.jenkins import CreateJobsExtension

    ext = CreateJobsExtension('createjob', Mock())
    ext.current = ext.bot.current
    ext.current.errors = []
    ext.current.head.sha = 'cafed0d0'
    ext.current.head.repository.jobs = {'job': Mock()}
    ext.current.job_specs = dict(job=JobSpec.factory('job', 'toto'))
    job = Mock()
    ext.current.jobs = {'job': job}
    job.update = CoroutineMock(side_effect=Exception('POUET'))

    process_job_specs.return_value = [(job.update, Mock())]

    yield from ext.run()

    assert ext.current.errors
    assert job.update.mock_calls


@patch('jenkins_epo.extensions.jenkins.JENKINS')
def test_refresh_job_outdated(JENKINS):
    from jenkins_epo.extensions.jenkins import CreateJobsExtension
    from jenkins_epo.bot import Instruction

    ext = CreateJobsExtension('createjob', Mock())
    ext.current = ext.bot.current
    ext.current.errors = []
    ext.current.refresh_jobs = None
    ext.current.job_specs = {'job': Mock(config={})}
    ext.current.job_specs['job'].name = 'job'
    job = Mock(updated_at=datetime.now() - timedelta(hours=1))
    job.name = 'job'
    job.spec.contains.return_value = True
    job.update = CoroutineMock()
    ext.current.jobs = {'job': job}

    ext.process_instruction(Instruction(
        author='author', name='refresh-jobs', date=datetime.now()
    ))

    assert ext.current.refresh_jobs

    items = list(ext.process_job_specs())
    assert 1 == len(items)
    action, spec = items[0]
    assert job.update == action

    ext.current.jobs['job'].updated_at = datetime.now() + timedelta(hours=1)
    items = list(ext.process_job_specs())
    assert 0 == len(items)
