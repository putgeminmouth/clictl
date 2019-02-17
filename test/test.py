import unittest
import subprocess
import tempfile
import os

this_file_dir = os.path.dirname(os.path.realpath(__file__))


class TestStringMethods(unittest.TestCase):

    def run_with_config(self, **kwargs):
        config = kwargs.get('config', {})
        args = kwargs.get('args', [])
        env = kwargs.get('env', None)
        configfile = tempfile.mkstemp()[1]
        with open(configfile, 'w') as f:
            f.write(config)
        cmds = ['python', this_file_dir + '/../src/clictl.py', '--config', configfile] + args
        print(cmds)
        try:
            return 0, subprocess.check_output(" ".join(cmds), env = env, shell = True).strip()
        except subprocess.CalledProcessError as e:
            return e.returncode, e.output

    def test_echo(self):
        code, out = self.run_with_config(
            config = """
                pipeline:
                    - echo: hello
            """,
        )
        self.assertEqual('hello', out)

    def test_interpolation_env(self):
        code, out = self.run_with_config(
            config = """{
                "pipeline": [{
                    "echo": "{env.foo}"
                }]
            }
            """,
            args = ['--', 'true'],
            env = { 'foo': 'bar' }
        )
        self.assertEqual('bar', out)

    def test_interpolation_cmd(self):
        code, out = self.run_with_config(
            config = """
                pipeline:
                    - echo: "{1} {0}"
            """,
            args = ['--', 'true', 'bar'],
        )
        self.assertEqual('bar true', out)

    def test_require_pass(self):
        code, out = self.run_with_config(
            config = """{
                "pipeline": [{
                    "require": true
                }]
            }
            """,
            args = ['--', 'echo', 'ok']
        )
        self.assertEqual('ok', out)

    def test_require_fail(self):
        code, out = self.run_with_config(
            config = """{
                "pipeline": [{
                    "require": false
                }]
            }
            """,
            args = ['--', 'echo', 'ok']
        )
        self.assertEqual(2, code)

    def test_and(self):
        code, out = self.run_with_config(
            config = """{
                "pipeline": [{
                    "require": {
                      "and": [
                        true,
                        true
                      ]
                    }
                }]
            }
            """,
            args = ['--']
        )
        self.assertEqual(0, code)

        code, out = self.run_with_config(
            config = """{
                "pipeline": [{
                    "require": {
                      "and": [
                        true,
                        false
                      ]
                    }
                }]
            }
            """,
            args = ['--']
        )
        self.assertEqual(2, code)

        code, out = self.run_with_config(
            config = """{
                "pipeline": [{
                    "require": {
                      "and": [
                        false,
                        true
                      ]
                    }
                }]
            }
            """,
            args = ['--']
        )
        self.assertEqual(2, code)

        code, out = self.run_with_config(
            config = """{
                "pipeline": [{
                    "require": {
                      "and": [
                        false,
                        false
                      ]
                    }
                }]
            }
            """,
            args = ['--']
        )
        self.assertEqual(2, code)

        code, out = self.run_with_config(
            config = """{
                "pipeline": [{
                    "require": {
                      "and": [
                        false,
                        false
                      ]
                    }
                }]
            }
            """,
            args = ['--']
        )
        self.assertEqual(2, code)

    def test_or(self):
        code, out = self.run_with_config(
            config = """
                pipeline:
                    - require:
                        or:
                            - true
                            - true
            """,
            args = ['--']
        )
        self.assertEqual(0, code)

        code, out = self.run_with_config(
            config = """
                pipeline:
                    - require:
                        or:
                            - true
                            - false
            """,
            args = ['--']
        )
        self.assertEqual(0, code)

        code, out = self.run_with_config(
            config = """
                pipeline:
                    - require:
                        or:
                            - false
                            - true
            """,
            args = ['--']
        )
        self.assertEqual(0, code)

        code, out = self.run_with_config(
            config = """
                pipeline:
                    - require:
                        or:
                            - false
                            - false
            """,
            args = ['--']
        )
        self.assertEqual(2, code)

    def test_equal(self):
        code, out = self.run_with_config(
            config = """{
                "pipeline": [{
                    "require": {
                      "equal": [
                        "hello",
                        "hello"
                      ]
                    }
                }]
            }
            """,
            args = ['--']
        )
        self.assertEqual(0, code)

        code, out = self.run_with_config(
            config = """{
                "pipeline": [{
                    "require": {
                      "equal": [
                        "hello",
                        "goodbye"
                      ]
                    }
                }]
            }
            """,
            args = ['--']
        )
        self.assertEqual(2, code)

    def test_equal_pass(self):
        code, out = self.run_with_config(
            config = """{
                "pipeline": [{
                    "require": {
                      "equal": [
                        "bar",
                        "bar"
                      ]
                    }
                }]
            }
            """,
            args = ['--']
        )
        self.assertEqual(0, code)

        code, out = self.run_with_config(
            config = """{
                "pipeline": [{
                    "require": {
                      "eq": [
                        "bar",
                        "bar"
                      ]
                    }
                }]
            }
            """,
            args = ['--']
        )
        self.assertEqual(0, code)

        code, out = self.run_with_config(
            config = """{
                "pipeline": [{
                    "require": {
                      "==": [
                        "bar",
                        "bar"
                      ]
                    }
                }]
            }
            """,
            args = ['--']
        )
        self.assertEqual(0, code)

    def test_equal_false(self):
        code, out = self.run_with_config(
            config = """{
                "pipeline": [{
                    "require": {
                      "equal": [
                        "foo",
                        "bar"
                      ]
                    }
                }]
            }
            """,
            args = ['--'],
            env = { 'foo': 'bar' }
        )
        self.assertEqual(2, code)

        code, out = self.run_with_config(
            config = """{
                "pipeline": [{
                    "require": {
                      "eq": [
                        "foo",
                        "bar"
                      ]
                    }
                }]
            }
            """,
            args = ['--'],
            env = { 'foo': 'bar' }
        )
        self.assertEqual(2, code)

        code, out = self.run_with_config(
            config = """{
                "pipeline": [{
                    "require": {
                      "==": [
                        "foo",
                        "bar"
                      ]
                    }
                }]
            }
            """,
            args = ['--'],
            env = { 'foo': 'bar' }
        )
        self.assertEqual(2, code)


    def test_nequal_pass(self):
        code, out = self.run_with_config(
            config = """{
                "pipeline": [{
                    "require": {
                      "neq": [
                        "foo",
                        "bar"
                      ]
                    }
                }]
            }
            """,
            args = ['--'],
            env = { 'foo': 'bar' }
        )
        self.assertEqual(0, code)

        code, out = self.run_with_config(
            config = """{
                "pipeline": [{
                    "require": {
                      "!=": [
                        "foo",
                        "bar"
                      ]
                    }
                }]
            }
            """,
            args = ['--'],
            env = { 'foo': 'bar' }
        )
        self.assertEqual(0, code)

    def test_nequal_fail(self):
        code, out = self.run_with_config(
            config = """{
                "pipeline": [{
                    "require": {
                      "neq": [
                        "bar",
                        "bar"
                      ]
                    }
                }]
            }
            """,
            args = ['--']
        )
        self.assertEqual(2, code)

        code, out = self.run_with_config(
            config = """{
                "pipeline": [{
                    "require": {
                      "!=": [
                        "bar",
                        "bar"
                      ]
                    }
                }]
            }
            """,
            args = ['--']
        )
        self.assertEqual(2, code)

    def test_if_pass(self):
        code, out = self.run_with_config(
            config = """
                pipeline:
                    - if:
                        condition: true
                        then:
                            - echo: "{env.foo}"
            """,
            args = ['--', 'true'],
            env = { 'foo': 'bar' }
        )
        self.assertEqual('bar', out)

    def test_if_fail(self):
        code, out = self.run_with_config(
            config = """
                pipeline:
                    - if:
                        condition: false
                        then:
                            - echo: "{env.foo}"
            """,
            args = ['--', 'true'],
            env = { 'foo': 'bar' }
        )
        self.assertEqual('', out)
        self.assertEqual(0, code)

if __name__ == '__main__':
    unittest.main()
