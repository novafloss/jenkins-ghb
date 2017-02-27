import asyncio
from unittest.mock import Mock

import pytest


@pytest.mark.asyncio
@asyncio.coroutine
def test_first_stage():
    from jenkins_epo.extensions.jenkins import StagesExtension

    ext = StagesExtension('stages', Mock())
    ext.current = Mock()
    ext.current.head.ref = 'pr'
    ext.current.SETTINGS.STAGES = ['build', 'test']
    ext.current.statuses = {}
    ext.current.job_specs = specs = {
        'build': Mock(config=dict(stage='build')),
        'test': Mock(config=dict()),
    }
    specs['build'].name = 'build'
    specs['test'].name = 'test'

    yield from ext.run()

    assert ext.current.current_stage.name == 'build'


@pytest.mark.asyncio
@asyncio.coroutine
def test_second_stage():
    from jenkins_epo.extensions.jenkins import StagesExtension

    ext = StagesExtension('stages', Mock())
    ext.current = Mock()
    ext.current.head.ref = 'pr'
    ext.current.SETTINGS.STAGES = ['build', 'test']
    ext.current.statuses = {}
    ext.current.job_specs = specs = {
        'test': Mock(config=dict()),
        'missing': Mock(config=dict()),
    }
    specs['test'].name = 'test'
    specs['missing'].name = 'missing'

    yield from ext.run()

    assert ext.current.current_stage.name == 'test'


@pytest.mark.asyncio
@asyncio.coroutine
def test_no_test_stage():
    from jenkins_epo.extensions.jenkins import StagesExtension

    ext = StagesExtension('stages', Mock())
    ext.current = Mock()
    ext.current.head.ref = 'pr'
    ext.current.SETTINGS.STAGES = ['build', 'deploy']
    ext.current.statuses = {}
    ext.current.job_specs = specs = {
        'build': Mock(config=dict()),
    }
    specs['build'].name = 'build'

    yield from ext.run()

    assert 'build' == ext.current.current_stage.name
    assert 'build' in ext.current.job_specs


@pytest.mark.asyncio
@asyncio.coroutine
def test_periodic_ignored():
    from jenkins_epo.extensions.jenkins import StagesExtension

    ext = StagesExtension('stages', Mock())
    ext.current = Mock()
    ext.current.head.ref = 'pr'
    ext.current.SETTINGS.STAGES = ['deploy', 'test']
    ext.current.statuses = {}
    ext.current.job_specs = specs = {
        'periodic': Mock(config=dict(periodic=True)),
        'test': Mock(config=dict()),
    }
    specs['periodic'].name = 'periodic'
    specs['test'].name = 'test'

    yield from ext.run()

    assert ext.current.current_stage.name == 'test'
    assert 'periodic' not in ext.current.job_specs


@pytest.mark.asyncio
@asyncio.coroutine
def test_periodic_required():
    from jenkins_epo.extensions.jenkins import StagesExtension

    ext = StagesExtension('stages', Mock())
    ext.current = Mock()
    ext.current.head.ref = 'pr'
    ext.current.SETTINGS.STAGES = ['deploy', 'test']
    ext.current.statuses = {}
    ext.current.job_specs = specs = {
        'deploy': Mock(config=dict(stage='deploy', periodic=True)),
        'test': Mock(config=dict()),
    }
    specs['deploy'].name = 'deploy'
    specs['test'].name = 'test'

    yield from ext.run()

    assert ext.current.current_stage.name == 'deploy'


@pytest.mark.asyncio
@asyncio.coroutine
def test_branches_limit():
    from jenkins_epo.extensions.jenkins import StagesExtension

    ext = StagesExtension('stages', Mock())
    ext.current = Mock()
    ext.current.head.ref = 'pr'
    ext.current.SETTINGS.STAGES = ['test']
    ext.current.statuses = {}
    ext.current.job_specs = specs = {
        'job': Mock(config=dict(branches='master')),
    }
    specs['job'].name = 'job'

    yield from ext.run()

    assert ext.current.current_stage.name == 'test'
    assert 'job' not in ext.current.job_specs


@pytest.mark.asyncio
@asyncio.coroutine
def test_external_context():
    from jenkins_epo.extensions.jenkins import StagesExtension

    ext = StagesExtension('stages', Mock())
    ext.current = Mock()
    ext.current.head.ref = 'pr'
    ext.current.SETTINGS.STAGES = [
        dict(name='deploy', external=['deploy/prod']),
        dict(name='final', external=['final']),
    ]
    ext.current.job_specs = {}
    ext.current.statuses = {}

    yield from ext.run()

    assert 'deploy' == ext.current.current_stage.name

    ext.current.statuses = {
        'plop': {'context': 'deploy/prod', 'state': 'success'},
    }

    yield from ext.run()

    assert 'final' == ext.current.current_stage.name


@pytest.mark.asyncio
@asyncio.coroutine
def test_nostages():
    from jenkins_epo.extensions.jenkins import StagesExtension, SkipHead

    ext = StagesExtension('stages', Mock())
    ext.current = Mock()
    ext.current.head.ref = 'pr'
    ext.current.SETTINGS.STAGES = ['test', 'deploy']
    ext.current.job_specs = {}
    ext.current.statuses = {}

    with pytest.raises(SkipHead):
        yield from ext.run()


@pytest.mark.asyncio
@asyncio.coroutine
def test_complete():
    from jenkins_epo.extensions.jenkins import StagesExtension

    ext = StagesExtension('stages', Mock())
    ext.current = Mock()
    ext.current.head.ref = 'pr'
    ext.current.SETTINGS.STAGES = ['test', 'deploy']
    ext.current.job_specs = specs = {
        'test': Mock(config=dict()),
        'deploy': Mock(config=dict(stage='deploy')),
    }
    specs['test'].name = 'test'
    specs['deploy'].name = 'deploy'
    ext.current.statuses = {
        'test': {'context': 'test', 'state': 'success'},
        'deploy': {'context': 'deploy', 'state': 'success'},
    }

    yield from ext.run()

    assert ext.current.current_stage.name == 'deploy'
