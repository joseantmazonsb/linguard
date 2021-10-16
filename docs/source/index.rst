Linguard
========

.. image:: https://img.shields.io/github/license/joseantmazonsb/linguard
    :target: https://github.com/joseantmazonsb/linguard/blob/main/LICENSE.md
    :alt: License: GPL-3.0

.. image:: https://img.shields.io/badge/python-3.7%20%7C%203.8%20%7C%203.9-blue?logo=python&logoColor=yellow
    :alt: Supported python versions: 3.7, 3.8, 3.9

.. image:: https://github.com/joseantmazonsb/linguard/actions/workflows/stable-test.yaml/badge.svg
    :target: https://github.com/joseantmazonsb/linguard/actions/workflows/stable-test.yaml
    :alt: Stable workflow status

.. image:: https://github.com/joseantmazonsb/linguard/actions/workflows/latest-test.yaml/badge.svg
    :target: https://github.com/joseantmazonsb/linguard/actions/workflows/latest-test.yaml
    :alt: Latest workflow status

.. image:: https://readthedocs.org/projects/linguard/badge/?version=stable
    :target: https://linguard.readthedocs.io/en/stable/?badge=latest
    :alt: Stable Documentation Status

.. image:: https://codecov.io/gh/joseantmazonsb/linguard/branch/main/graph/badge.svg
    :target: https://codecov.io/gh/joseantmazonsb/linguard
    :alt: Code coverage status

.. image:: https://img.shields.io/github/v/release/joseantmazonsb/linguard?color=green&include_prereleases&logo=github)
    :target: https://github.com/joseantmazonsb/linguard/releases
    :alt: Latest release (including pre-releases)

.. image:: https://img.shields.io/github/downloads/joseantmazonsb/linguard/total?logo=github)
    :target: https://github.com/joseantmazonsb/linguard/releases
    :alt: Downloads counter (from all releases)

Linguard aims to provide a clean, simple yet powerful web GUI to manage your WireGuard server, and it's powered by Flask.

Key features
------------

* Management of Wireguard interfaces and peers via web. Interfaces can be created, removed, edited, exported and brought up and down directly from the web GUI. Peers can be created, removed, edited and downloaded at anytime as well.
* Display stored and real time traffic data using charts (storage of traffic data may be manually disabled).
* Display general network information.
* Encrypted user credentials (AES).
* Easy management through the ``linguard`` systemd service.

Contents
--------

.. toctree::
    :maxdepth: 2

    installation
    screenshots
    in-depth
    contributing
    changelog

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`