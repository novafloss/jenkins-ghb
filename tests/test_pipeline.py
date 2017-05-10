def test_pipeline():
    from jenkins_yml.job import Job
    from jenkins_epo.pipeline import Pipeline
    from jenkins_epo.repository import CommitStatus

    pipeline = Pipeline.from_yaml(
        stages=['build', 'test', dict(
            name='deploy', external=['staging', 'prod']
        )]
    )

    assert 'test' in pipeline.stages

    docker = Job(name='docker', config=dict(stage='build'))
    units = Job(name='units', config=dict())

    pipeline.add_specs(units, docker)

    assert docker in pipeline.stages['build'].jobs
    assert units in pipeline.stages['test'].jobs

    pipeline.process_statuses(
        CommitStatus(context='docker', state='success', updated_at=1),
        CommitStatus(context='docker', state='pending', updated_at=0),
        CommitStatus(context='units/py35', state='success', updated_at=0),
        CommitStatus(context='units/py36', state='pending', updated_at=0),
        CommitStatus(context='staging', state='success', updated_at=1),
    )

    assert 1 == len(pipeline.stages['build'].statuses)
    assert 'success' == pipeline.stages['build'].state
    assert 2 == len(pipeline.stages['test'].statuses)
    assert 'pending' == pipeline.stages['test'].state
    assert 'unknown' == pipeline.stages['deploy'].state

    payload = pipeline.to_json()
    assert 3 == len(payload)
    test = payload[1]
    assert 'test' == test['name']
    assert 2 == len(test['statuses'])


def test_stage_state():
    from jenkins_epo.pipeline import Stage

    stage = Stage(name='test')
    assert 'test' in repr(stage)

    stage.statuses = {
        s: {'state': s}
        for s in ['error', 'failure', 'pending', 'success', 'unknown']
    }
    assert 'error' == stage.state

    stage.statuses.pop('error')
    assert 'failure' == stage.state

    stage.statuses.pop('failure')
    assert 'pending' == stage.state

    stage.statuses.pop('pending')
    assert 'unknown' == stage.state

    stage.statuses.pop('unknown')
    assert 'success' == stage.state


def test_stage_trim():
    from jenkins_epo.pipeline import Stage

    stage = Stage(name='test', trim_prefixes=['prefix'])

    assert 'units' == stage.trim_context('test-units')
    assert 'units' == stage.trim_context('prefix-test-units')
    assert 'units' == stage.trim_context('test-prefix-units')
    assert 'tests-units' == stage.trim_context('tests-units')
