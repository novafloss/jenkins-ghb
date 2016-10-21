import logging

from .extensions import (
    CreateJobsExtension as BaseCreateJobsExtension,
)
from .github import GITHUB, ApiNotFoundError

logger = logging.getLogger(__name__)


class CreateJobsExtension(BaseCreateJobsExtension):
    def run(self):
        head = self.current.head

        try:
            jenkins_yml = GITHUB.fetch_file_contents(
                head.repository, 'jenkins.yml', ref=head.ref,
            )
            logger.debug("Loading jenkins.yml.")
        except ApiNotFoundError:
            jenkins_yml = None

        self.current.job_specs = self.list_job_specs(jenkins_yml)

        for name, job in self.current.job_specs.items():
            logger.info("Would run %s", job.config['script'])
