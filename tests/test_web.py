import asyncio
from unittest.mock import Mock

import pytest


@pytest.mark.asyncio
@asyncio.coroutine
def test_simple(mocker, WORKERS):
    mocker.patch('jenkins_epo.web.WORKERS', WORKERS)
    from jenkins_epo.web import simple_webhook

    req = Mock(GET=dict(head='url://'))
    res = yield from simple_webhook(req)

    assert 200 == res.status
    assert WORKERS.enqueue.mock_calls


def test_signature():
    from jenkins_epo.web import compute_signature
    payload = b"""PAYLOAD"""
    wanted_signature = 'sha1=917eb41141e2e4ce264faa004335e46a344f3f54'
    assert wanted_signature == compute_signature(payload, b'notasecret')
