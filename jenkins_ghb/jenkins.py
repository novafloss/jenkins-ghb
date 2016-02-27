from jenkinsapi.jenkins import Jenkins

from .settings import SETTINGS


class LazyJenkins(object):
    def __init__(self):
        self._instance = None

    def __getattr__(self, name):
        self.load()
        return getattr(self._instance, name)

    def load(self):
        if not self._instance:
            self._instance = Jenkins(SETTINGS.JENKINS_URL)


JENKINS = LazyJenkins()
