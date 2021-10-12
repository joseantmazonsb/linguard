Contributing
====

.. note::

    Linguard is and will always be open source.

You may contribute by opening new issues, commenting on existent ones and creating pull requests with new features and bugfixes.
Any help is welcome, just make sure you read the following sections, which will guide you to set up the development environment.

Git flow
----

You should never work directly on the ``main`` branch. This branch is only used to gather new features and bugfixes previously merged to the ``dev`` branch and publish them in a single package. In other words, its purpose is to release new versions of Linguard.

Hence, the ``dev`` branch **should always be your starting point and the target of your pull requests.**

.. code-block:: bash

    git clone https://github.com/joseantmazonsb/linguard.git
    cd linguard
    git checkout dev

Dependency management
----

`Poetry <https://python-poetry.org/>`__ is used to handle packaging and dependencies. You will need to install it before getting started to code:

.. code-block:: bash

    curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python3 -

Once you have checked out the repository, you'd install the python requirements this way:

.. code-block:: bash

    poetry config virtualenvs.in-project true
    poetry install

Configuration files
----

Linguard has a setup assistant and does not require you to have an existing configuration file in its working directory. Nonetheless, you may use your own as long as it is valid and named ``linguard.yaml``.

As for the UWSGI configuration, Linguard provides a sample file (``uwsgi.sample.yaml``) for you to play around with it. Just make sure you run UWSGI using a valid file!

Testing
----

`PyTest <https://docs.pytest.org/en/6.2.x>`__ and `Coverage <https://coverage.readthedocs.io/en/coverage-5.5>`__ are used to test Linguard and generate coverage reports, which are uploaded to `Codecov <https://about.codecov.io>`__.

TDD is enforced. Make sure your code passes the existing tests and provide new ones to prove your new features/bugfixes actually work when making pull requests.

All tests should be anywhere under ``linguard/tests``, and you can run them all using Poetry:

.. code-block:: bash

    poetry run pytest

You may as well generate a coverage report using poetry:

.. code-block:: bash

    poetry run coverage report

Building
----

To build Linguard you may use the ``build.sh`` script, which automatically generates a ``dist`` folder containing a compressed file with all you need to publish a release.

CI/CD
----

Github Workflows are used to implement a CI/CD pipeline. When code is pushed to any branch, it will be automatically tested to ensure everything is working properly.

.. warning::

    The ``main`` branch is used to automatically deploy new releases, and **should never be the target of external pull requests**.
