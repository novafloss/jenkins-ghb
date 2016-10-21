from unittest import mock

from jenkins_epo.utils import Bunch


@mock.patch('jenkins_epo.dummy.GITHUB')
@mock.patch('jenkins_epo.dummy.logger')
def test_create_job_logs(logger, GITHUB):
    from jenkins_epo.dummy import CreateJobsExtension
    from jenkins_epo.bot import Bot

    ext = CreateJobsExtension('create-jobs', bot=Bot())
    ext.current = mock.Mock()
    ext.list_job_specs = mock.Mock(
        return_value={'test': Bunch(config={'script': 'run'})}
    )
    ext.run()

    ext.list_job_specs.assert_called_with(GITHUB.fetch_file_contents())
    logger.debug.assert_called_with('Loading jenkins.yml.')
    logger.info.assert_called_with('Would run %s', 'run')
