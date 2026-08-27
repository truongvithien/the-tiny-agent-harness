# wordcount

A deliberately tiny sample project for the software-development laboratory. It
contains one function and one test module, and it ships with a failing test.

Its documented check command is:

```bash
python -m unittest discover -p 'test_*.py'
```

The laboratory copies this directory into an operating-system temporary
directory before an agent run, so the agent edits the copy and never this
source.
