from unittest.mock import Mock
from datetime import datetime

import pytest


def comment(login='montecristo', **kwargs):
    defaults = dict(
        updated_at='2016-06-29T11:41:47Z',
        body=None,
        user=dict(login=login),
    )
    return dict(defaults, **kwargs)


def test_compute_skip_unindented():
    from jenkins_epo.bot import Bot

    bot = Bot().workon(Mock())
    comments = [comment(body='```\njenkins:\nskip: [toto]\n```')]
    instructions = list(bot.parse_instructions(comments))
    assert 1 == len(instructions)
    instruction = instructions[0]
    assert ['toto'] == instruction.args


def test_compute_help():
    from jenkins_epo.bot import Bot

    bot = Bot().workon(Mock())
    bot.process_instructions([
        comment(login='asker', body='jenkins: help')
    ])
    assert 'asker' in bot.current.help_mentions

    bot.process_instructions([
        comment(login='asker1', body='jenkins: help'),
        comment(login='bot', body='jenkins: help-reset'),
    ])
    assert not bot.current.help_mentions

    bot.process_instructions([
        comment(login='asker1', body='jenkins: help'),
        comment(login='asker2', body='jenkins: man'),
    ])
    assert 'asker1' in bot.current.help_mentions
    assert 'asker2' in bot.current.help_mentions

    bot.extensions_map['help'].run()

    man = bot.current.head.comment.call_args[1]['body']
    assert '@asker1' in man
    assert '@asker2' in man


def test_errors():
    from jenkins_epo.bot import Bot, Error

    bot = Bot().workon(Mock())
    bot.current.errors = [Error('message', Mock())]

    bot.extensions_map['error'].run()

    assert bot.current.head.comment.mock_calls


def test_errors_reset():
    from jenkins_epo.bot import Bot, Error
    from jenkins_epo.utils import parse_datetime

    bot = Bot().workon(Mock())
    bot.current.errors = [
        Error('message', parse_datetime('2016-08-03T15:58:47Z')),
    ]
    bot.process_instructions([comment(
        body='''jenkins: reset-errors''', updated_at='2016-08-03T17:58:47Z',
    )])

    bot.extensions_map['error'].run()

    assert not bot.current.head.comment.mock_calls


def test_report():
    from jenkins_epo.extensions.core import ReportExtension, Branch

    ext = ReportExtension('merger', Mock())
    ext.current = Mock()
    ext.current.head = Mock(spec=Branch)
    ext.current.head.sha = 'c0defada'
    ext.current.head.ref = 'refs/heads/branch'
    ext.current.head.repository = Mock()
    ext.current.head.repository.report_issue.return_value = {
        'number': '1',
    }
    ext.current.report_done = None
    ext.current.statuses = {
        'job1': {
            'state': 'failure',
            'target_url': 'build_url',
        },
    }
    ext.run()

    assert ext.current.head.comment.mock_calls
    assert ext.current.head.repository.report_issue.mock_calls


def test_autocancel():
    from jenkins_epo.extensions.core import AutoCancelExtension

    ext = AutoCancelExtension('merger', Mock())
    ext.current = Mock()
    ext.current.cancel_queue = cancel_queue = []
    ext.current.poll_queue = []
    last_commit = Mock()
    old_commit = Mock()
    ext.current.repository.process_commits.return_value = [
        last_commit, old_commit,
    ]

    last_commit.process_statuses.return_value = last_statuses = {
        'backed': {
            'description': 'Backed',
            'state': 'pending',
            'target_url': 'https://jenkins.lan/job/backed/',
        },
        'running': {
            'description': '#2 running',
            'state': 'pending',
            'target_url': 'https://jenkins.lan/job/running/build/2/',
        },
    }
    old_commit.process_statuses.return_value = old_statuses = {
        'backed': {'state': 'pending', 'description': 'Backed'},
        'success': {
            'state': 'success',
            'target_url': 'https://jenkins.lan/job/success/build/1/',
        },
        'running': {
            'description': '#1 running',
            'state': 'pending',
            'target_url': 'https://jenkins.lan/job/running/build/1/',
        },
    }

    ext.run()

    assert (old_commit, old_statuses['backed']) not in cancel_queue
    assert (old_commit, old_statuses['success']) not in cancel_queue
    assert (old_commit, old_statuses['running']) in cancel_queue
    assert (last_commit, last_statuses['backed']) not in cancel_queue
    assert (last_commit, last_statuses['running']) not in cancel_queue


def test_outdated():
    from jenkins_epo.extensions.core import OutdatedExtension, SkipHead

    ext = OutdatedExtension('merger', Mock())
    ext.current = Mock()
    ext.current.SETTINGS.COMMIT_MAX_WEEKS = 1
    ext.current.last_commit.date = datetime(2015, 1, 1, 1, 1, 1)

    with pytest.raises(SkipHead):
        ext.begin()


def test_skip_instruction():
    from jenkins_epo.bot import Instruction
    from jenkins_epo.extensions.core import SkipExtension, match

    ext = SkipExtension('ext', Mock())
    ext.current = ext.bot.current

    ext.process_instruction(Instruction(author='a', name='skip'))

    assert not match('job', ext.current.jobs_match)

    ext.process_instruction(Instruction(author='a', name='jobs', args='*'))

    assert match('job', ext.current.jobs_match)


def test_skip_run():
    from jenkins_epo.extensions.core import CommitStatus, SkipExtension

    ext = SkipExtension('ext', Mock())
    ext.current = ext.bot.current
    ext.current.cancel_queue = []
    ext.current.jobs_match = ['matching']
    ext.current.job_specs = dict(job=Mock())
    ext.current.jobs = {}
    ext.current.jobs['job'] = job = Mock()
    job.list_contexts.return_value = [
        'done', 'matching', 'null', 'queued', 'running',
    ]
    ext.current.statuses = statuses = {}
    statuses['queued'] = CommitStatus(state='pending', description='Queued')
    statuses['running'] = CommitStatus(
        state='pending', description='Build #1 running...',
        target_url='jenkins:///job/1',
    )
    statuses['done'] = CommitStatus(state='success')

    ext.run()

    assert 1 == len(ext.current.cancel_queue)
    pushed_contextes = [
        c[1][0]['context']
        for c in ext.current.last_commit.maybe_update_status.mock_calls
    ]
    assert 'done' not in pushed_contextes
    assert 'matching' not in pushed_contextes
    assert 'null' in pushed_contextes
    assert 'queued' in pushed_contextes
    assert 'running' in pushed_contextes