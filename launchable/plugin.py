
import os
import sys
from io import StringIO
from time import time
from types import ModuleType

from nose.plugins import Plugin
from nose.plugins.capture import Capture
from nose.plugins.xunit import Tee
from nose.util import test_address

from launchable.case_event import CaseEvent
from launchable.client import LaunchableClientFactory
from launchable.log import logger
from launchable.manager import parse_test, reorder
from launchable.protecter import protect
from launchable.uploader import UploaderFactory

BUILD_NUMBER_KEY = "LAUNCHABLE_BUILD_NUMBER"

class Launchable(Plugin):
    name = "launchable"
    # Grab override sys.stdout after the capture plugin
    score = Capture.score - 1
    encoding = 'UTF-8'

    def __init__(self):
        super().__init__()
        self._capture_stack = []
        self._currentStdout = None
        self._currentStderr = None

    def options(self, parser, env):
        super(Launchable, self).options(parser, env=env)
        parser.add_option("--launchable", action='store_true', dest="enabled", help="Enable Launchable API interaction")
        parser.add_option("--launchable-build-number", action='store', type='string', dest="build_number", help="CI/CD build number")

    def configure(self, options, conf):
        super(Launchable, self).configure(options, conf)
        self.enabled = options.enabled
        self.build_number = options.build_number or os.getenv(BUILD_NUMBER_KEY)

        if self.enabled and self.build_number is None:
            self.enabled = False
            logger.warning("--launchable flag is specified but --launchable-build-number flag is missing. "
                           "Please specify --launchable-build-number flag in order to enable nose-launchable plugin")

    @protect
    def begin(self):
        self._client = LaunchableClientFactory.prepare()
        self._client.start(self.build_number)

        self._uploader = UploaderFactory.prepare(self._client)

        self._uploader.start()

    @protect
    def prepareTest(self, test):
        t = parse_test(test)

        self._print("Getting optimized test execution order from Launchable...\n")
        order = self._client.infer(t)
        self._print("Received optimized test execution order from Launchable\n")

        reorder(test, order)

        self._print("Test execution optimized by Launchable ")
        # A rocket emoji
        self._print("\U0001f680\n")
        return test

    @protect
    def startContext(self, context):
        self._startCapture()

    @protect
    def stopContext(self, context):
        self._endCapture()

    @protect
    def beforeTest(self, test):
        """Initializes a timer before starting a test."""
        self._timer = time()
        self._startCapture()

    @protect
    def afterTest(self, test):
        self._endCapture()
        self._currentStdout = None
        self._currentStderr = None

    @protect
    def addError(self, test, err, capt=None):
        self._addResult(test, CaseEvent.TEAT_FAILED, self._uploader.enqueue_failure)

    @protect
    def addFailure(self, test, err, capt=None, tb_info=None):
        self._addResult(test, CaseEvent.TEAT_FAILED, self._uploader.enqueue_failure)

    @protect
    def addSuccess(self, test, capt=None):
        self._addResult(test, CaseEvent.TEST_PASSED, self._uploader.enqueue_success)

    @protect
    def finalize(self, test):
        while self._capture_stack:
            self._endCapture()

        self._uploader.join()

    def _startCapture(self):
        self._capture_stack.append((sys.stdout, sys.stderr))
        self._currentStdout = StringIO()
        self._currentStderr = StringIO()
        sys.stdout = Tee(self.encoding, self._currentStdout, sys.stdout)
        sys.stderr = Tee(self.encoding, self._currentStderr, sys.stderr)

    def _endCapture(self):
        if self._capture_stack:
            sys.stdout, sys.stderr = self._capture_stack.pop()

    def _getCapturedStdout(self):
        if self._currentStdout:
            value = self._currentStdout.getvalue()
            if value:
                return value
        return ''

    def _getCapturedStderr(self):
        if self._currentStderr:
            value = self._currentStderr.getvalue()
            if value:
                return value
        return ''

    def _addResult(self, test, status, queueing):
        def get_test_name(t):
            file_path, module, name = test_address(t.test)
            # it return such as tests/dir1/test1.py#test1#test_evens
            return "#".join([os.path.relpath(file_path), module, name])

        logger.debug("Adding a test result: test: {}, context: {}".format(test, test.context))
        result = CaseEvent(get_test_name(test), self._timeTaken(), status, self._getCapturedStdout(),
                           self._getCapturedStderr())
        queueing(result)

    # Bypass Capture plugin
    def _print(self, message):
        sys.__stdout__.write(message)

    def _timeTaken(self):
        if hasattr(self, '_timer'):
            return time() - self._timer

        # test died before it ran (probably error in setup())
        # or success/failure added before test started probably
        # due to custom TestResult munging
        return 0.0
