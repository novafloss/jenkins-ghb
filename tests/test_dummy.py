from unittest import mock


@mock.patch('jenkins_epo.dummy.GITHUB')
def test_create_job_logs(GITHUB):
    from jenkins_epo.dummy import CreateJobsExtension

    ext = CreateJobsExtension()
    ext.current = mock.Mock()
    ext.list_job_specs = mock.Mock()
    ext.run()
