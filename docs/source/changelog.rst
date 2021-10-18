Changelog
=========

All notable changes to this project will be documented here.

.. note::
    Linguard is adhered to `Semantic Versioning <https://semver.org/>`__.

1.0.1
-----

Fixes
~~~~~

* Fixed a bug related to versioning which caused the app to start in dev mode.

Docs
~~~~

* Removed "Versions" empty section from index.


1.0.0
-----

What's new
~~~~~~~~~~

* QR codes! You can scan a QR code to get the WireGuard configuration of any peer or interface.
* Docker is finally here! For now on, there will be official docker images available for every release.
* Display the IP address of the interface to be used when adding or editing a peer.
* Updating the name of an interface also updates all references inside the "On up" and "On down" text areas.
* Delete buttons have been relocated in the Interface and Peer views.

Fixes
~~~~~

* Fixed a bug when updating the username or password which made the "Logged in {time} ago" sign show no time at all.
* Removed the possibility to add peers if there are no WireGuard interfaces.
* Ensured that peers can only be assigned valid, unused and not reserved IP addressed.
* Ensured that peers' IP addresses are in the same network of their interface.
* Ensured that interfaces can only be assigned valid, unused and not reserved IP addressed.
* Ensured that interfaces' cannot be assigned an IP address belonging to a network which already has an interface.
* Fixed a bug when updating an interface's gateway, which only updated one appearance of the previous gateway in the
  "On up" and "On down" text areas.
* Fixed the behaviour of the ``overwrite`` flag regarding the logging settings which was causing to overwrite the log
  file each time the settings were saved instead of every time Linguard boots up.

Docs
~~~~

* Improved documentation about the development environment.
* Fixed a bunch of typos.
* Fixed the Traffic Data Driver table.

0.2.0
-----

* Easy first time setup, which automatically detects the location of the required binaries and sets the public IP as endpoint by default.
* Everything in one place: workdir-based architecture.
* Removed option to log to standard output.
* Includes a ready-to-go uWSGI configuration file.
* Removed the ``linguard.sample.yaml`` file in favour of the first time setup.
* Settings are now accessible through the side navbar.
