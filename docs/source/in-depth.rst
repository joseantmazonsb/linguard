In depth
========

Arguments
---------

The following table describes every argument accepted by Linguard:

+------------------+------------+------------------------------------------+------------------------------------------------------+
| Argument         | Type       | Explanation                              | Notes                                                |
+==================+============+==========================================+======================================================+
| *workdir*        | Positional | Path to the Linguard's working directory | Linguard will store here everything it needs to work |
+------------------+------------+------------------------------------------+------------------------------------------------------+
| *-h* \| *--help* | Optional   | Display Linguard's CLI help and exit     |                                                      |
+------------------+------------+------------------------------------------+------------------------------------------------------+
| *--debug*        | Optional   | Start the Flask backend in debug mode    | Default value is ``False``                           |
+------------------+------------+------------------------------------------+------------------------------------------------------+

Configuration
-------------

Two sample configuration files are provided, ``uwsgi.sample.yaml`` and ``linguard.sample.yaml``, although the most interesting one is the second, since the first only contains options for a third party software,
`UWSGI <https://uwsgi-docs.readthedocs.io>`__.

Nonetheless, it is worth noting that the path to the Linguard's working directory (which will be used by Linguard to store stuff) needs to be provided through uwsgi's configuration, using the field ``pyargv``. Moreover, to edit the port and/or the interface in which the web server is running you will need to edit the field ``http-socket`` of uwsgi's configuration file.


For now on, we will only discuss Linguard's configuration values. Although the file ``linguard.sample.yaml``
contains every possible option, the following tables explain each one of them and detail
all possible values.

Logging configuration
~~~~~~~~~~~~~~~~~~~~~

These options must be specified inside a ``logger`` node.

+-------------+----------------------------------------------------------------------+--------------------------------------------------------+----------------------------+
| Option      | Explanation                                                          | Values                                                 | Default                    |
+=============+======================================================================+========================================================+============================+
| *level*     | Set the minimum level of messages to be logged                       | ``debug``, ``info``, ``warning``, ``error``, ``fatal`` | ``info``                   |
+-------------+----------------------------------------------------------------------+--------------------------------------------------------+----------------------------+
| *overwrite* | Whether to overwrite the log file when the application starts or not | ``true``, ``false``                                    | ``false``                  |
+-------------+----------------------------------------------------------------------+--------------------------------------------------------+----------------------------+

Web configuration
~~~~~~~~~~~~~~~~~

These options must be specified inside a ``web`` node.

+------------------+-----------------------------------------------------------------------------+---------------------------------------+------------------------------------+
| Option           | Explanation                                                                 | Values                                | Default                            |
+==================+=============================================================================+=======================================+====================================+
| *login_attempts* | Maximum number of login attempts within ``login_ban_time``                  | (almost) Any integer                  | ``0`` (unlimited attempts)         |
+------------------+-----------------------------------------------------------------------------+---------------------------------------+------------------------------------+
| *login_ban_time* | Amount of seconds an IP will be banned after too many failed login attempts | (almost) Any integer                  | ``120``                            |
+------------------+-----------------------------------------------------------------------------+---------------------------------------+------------------------------------+
| *secret_key*     | Key used to secure the authentication process                               | A 32 characters long string           | A random 32 characters long string |
+------------------+-----------------------------------------------------------------------------+---------------------------------------+------------------------------------+

Traffic data collection configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

These options must be specified inside a ``traffic`` node.

+-----------+-----------------------------------------------+------------------------------------------------------------------------------------------------+-----------------------------------------------------------+
| Option    | Explanation                                   | Values                                                                                         | Default                                                   |
+===========+===============================================+================================================================================================+===========================================================+
| *driver*  | Driver used to save and load traffic data     | Any registered driver. You can even craft your own driver using the base class                 | The ``JSON`` driver, which stores data serialized as JSON |
|           |                                               | ``TrafficStorageDriver``. Further information will be available through the code documentation |                                                           |
+-----------+-----------------------------------------------+------------------------------------------------------------------------------------------------+-----------------------------------------------------------+
| *enabled* | Whether the data collection is enabled or not | ``true``, ``false``                                                                            | ``true``                                                  |
+-----------+-----------------------------------------------+------------------------------------------------------------------------------------------------+-----------------------------------------------------------+

.. note::

    Linguard will only store the **amount of bytes received and transmitted** by peers, and only if ``enabled`` is set to ``true``.

Wireguard configuration
~~~~~~~~~~~~~~~~~~~~~~~

These options must be specified inside a ``wireguard`` node.

Global options
""""""""""""""

+----------------+----------------------------------------------------+----------------------------------------------------------+-------------------------------------------------------------------------+
| Option         | Explanation                                        | Values                                                   | Default                                                                 |
+================+====================================================+==========================================================+=========================================================================+
| *endpoint*     | Endpoint for all peers                             | Should be something like                                 | Default value will be your computer's public IP (if it can be obtained) |
|                |                                                    | ``vpn.example.com``, though it may also be an IP address |                                                                         |
+----------------+----------------------------------------------------+----------------------------------------------------------+-------------------------------------------------------------------------+
| *wg_bin*       | Path to the WireGuard binary file (                | ``path/to/file``                                         | If not specified, it will be retrieved using the                        |
|                | ``wg``)                                            |                                                          | ``whereis`` command                                                     |
+----------------+----------------------------------------------------+----------------------------------------------------------+-------------------------------------------------------------------------+
| *wg_quick_bin* | Path to the WireGuard quick binary file (          | ``path/to/file``                                         | If not specified, it will be retrieved using the                        |
|                | ``wg-quick``)                                      |                                                          | ``whereis`` command                                                     |
+----------------+----------------------------------------------------+----------------------------------------------------------+-------------------------------------------------------------------------+
| *interfaces*   | Dictionary containing all interfaces of the server | A number of                                              |                                                                         |
|                |                                                    | ``interface`` nodes whose keys are their own UUIDs       |                                                                         |
+----------------+----------------------------------------------------+----------------------------------------------------------+-------------------------------------------------------------------------+
| *iptables_bin* | Path to the iptables binary file (                 | ``path/to/file``                                         | If not specified, it will be retrieved using the                        |
|                | ``iptables``)                                      |                                                          | ``whereis`` command                                                     |
+----------------+----------------------------------------------------+----------------------------------------------------------+-------------------------------------------------------------------------+

Interface configuration
"""""""""""""""""""""""

These options must be specified inside an ``interface`` node.

+----------------+--------------------------------------------------------------------------------------+-----------------------------------------------------------+---------------------------------------------------------------------------------------------------------------------------------------------------+
| Option         | Explanation                                                                          | Values                                                    | Default                                                                                                                                           |
+================+======================================================================================+===========================================================+===================================================================================================================================================+
| *auto*         | Whether the interface will be automatically brought up when the server starts or not | ``true``, ``false``                                       | Default value is ``true``                                                                                                                         |
+----------------+--------------------------------------------------------------------------------------+-----------------------------------------------------------+---------------------------------------------------------------------------------------------------------------------------------------------------+
| *description*  | A description of the interface                                                       | A character string                                        |                                                                                                                                                   |
+----------------+--------------------------------------------------------------------------------------+-----------------------------------------------------------+---------------------------------------------------------------------------------------------------------------------------------------------------+
| *gw_iface*     | Interface used to connect the WireGuard interface to your network                    | A valid network device                                    | Your computer's default gateway                                                                                                                   |
+----------------+--------------------------------------------------------------------------------------+-----------------------------------------------------------+---------------------------------------------------------------------------------------------------------------------------------------------------+
| *ipv4_address* | IPv4 address assigned to the interface                                               | A valid IPv4 address                                      |                                                                                                                                                   |
+----------------+--------------------------------------------------------------------------------------+-----------------------------------------------------------+---------------------------------------------------------------------------------------------------------------------------------------------------+
| *listen_port*  | UDP port used by WireGuard to communicate with peers                                 | ``1-65535``                                               |                                                                                                                                                   |
+----------------+--------------------------------------------------------------------------------------+-----------------------------------------------------------+---------------------------------------------------------------------------------------------------------------------------------------------------+
| *name*         | The interface's name                                                                 | A character string                                        | It may only contain alphanumeric characters, underscores and hyphens. It must also begin with a letter and cannot be more than 15 characters long |
+----------------+--------------------------------------------------------------------------------------+-----------------------------------------------------------+---------------------------------------------------------------------------------------------------------------------------------------------------+
| *on_up*        | Linux commands to be executed when the interface is going to be brought up           | Any linux command in path                                 | By default, it will add FORWARD and POSTROUTING rules related to the interface                                                                    |
+----------------+--------------------------------------------------------------------------------------+-----------------------------------------------------------+---------------------------------------------------------------------------------------------------------------------------------------------------+
| *on_down*      | Linux commands to be executed when the interface is going to be brought down         | Any linux command in path                                 | By default, it will remove FORWARD and POSTROUTING rules related to the interface                                                                 |
+----------------+--------------------------------------------------------------------------------------+-----------------------------------------------------------+---------------------------------------------------------------------------------------------------------------------------------------------------+
| *peers*        | Dictionary containing all peers of the interface                                     | A number of ``peer`` nodes whose keys are their own UUIDs |                                                                                                                                                   |
+----------------+--------------------------------------------------------------------------------------+-----------------------------------------------------------+---------------------------------------------------------------------------------------------------------------------------------------------------+
| *private_key*  | Private key used to authenticate the interface                                       | A valid private key generated via ``wg``                  |                                                                                                                                                   |
+----------------+--------------------------------------------------------------------------------------+-----------------------------------------------------------+---------------------------------------------------------------------------------------------------------------------------------------------------+
| *public_key*   | Public key used to authenticate the interface                                        | A valid private key generated via ``wg``                  |                                                                                                                                                   |
+----------------+--------------------------------------------------------------------------------------+-----------------------------------------------------------+---------------------------------------------------------------------------------------------------------------------------------------------------+
| *uuid*         | Unique identifier                                                                    | A valid Version 4 UUID                                    |                                                                                                                                                   |
+----------------+--------------------------------------------------------------------------------------+-----------------------------------------------------------+---------------------------------------------------------------------------------------------------------------------------------------------------+

Peer configuration
""""""""""""""""""

These options must be specified inside an ``peer`` node.

+----------------+------------------------------------------------------------------------------+------------------------------------------+-------------------------------------------------------------------------------------------------------------+
| Option         | Explanation                                                                  | Values                                   | Default                                                                                                     |
+================+==============================================================================+==========================================+=============================================================================================================+
| *dns1*         | Main DNS used by the peer                                                    | A valid IPv4 address                     |                                                                                                             |
+----------------+------------------------------------------------------------------------------+------------------------------------------+-------------------------------------------------------------------------------------------------------------+
| *dns2*         | Secondary DNS used by the peer                                               | A valid IPv4 address                     |                                                                                                             |
+----------------+------------------------------------------------------------------------------+------------------------------------------+-------------------------------------------------------------------------------------------------------------+
| *ipv4_address* | IPv4 address assigned to the peer                                            | A valid IPv4 address                     |                                                                                                             |
+----------------+------------------------------------------------------------------------------+------------------------------------------+-------------------------------------------------------------------------------------------------------------+
| *name*         | The peer's name                                                              | A character string                       |                                                                                                             |
+----------------+------------------------------------------------------------------------------+------------------------------------------+-------------------------------------------------------------------------------------------------------------+
| *nat*          | Linux commands to be executed when the interface is going to be brought up   | Any linux command in path                | Default value is ``false``. If ``true``, this option will enable the ``PersistentKeepalive`` WireGuard flag |
+----------------+------------------------------------------------------------------------------+------------------------------------------+-------------------------------------------------------------------------------------------------------------+
| *private_key*  | Private key used to authenticate the peer                                    | A valid private key generated via ``wg`` |                                                                                                             |
+----------------+------------------------------------------------------------------------------+------------------------------------------+-------------------------------------------------------------------------------------------------------------+
| *public_key*   | Public key used to authenticate the peer                                     | A valid private key generated via ``wg`` |                                                                                                             |
+----------------+------------------------------------------------------------------------------+------------------------------------------+-------------------------------------------------------------------------------------------------------------+
| *uuid*         | Unique identifier                                                            | A valid Version 4 UUID                   |                                                                                                             |
+----------------+------------------------------------------------------------------------------+------------------------------------------+-------------------------------------------------------------------------------------------------------------+

Security
--------

Although Linguard stores users' credentials encrypted, it does not implement end-to-end encryption and instead, it relays on TLS to secure the communication between the user and the server.
This means you should never run Linguard on its own, but use the ``https`` option of uWSGI or set up a reverse proxy if you wish to use plain HTTP with uWSGI. Don't worry, here's how:

uWSGI with HTTPS socket
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: yaml

    uwsgi:
      https: 0.0.0.0:8443,foobar.crt,foobar.key # More info at https://uwsgi-docs.readthedocs.io/en/latest/HTTPS.html
      master: true
      enable-threads: true
      chdir: /var/www/linguard
      venv: venv
      wsgi-file: linguard/__main__.py
      pyargv: data
      need-plugin: python3
      callable: app
      die-on-term: true
      chmod-socket: 660
      vacuum: true

Apache reverse proxy
~~~~~~~~~~~~~~~~~~~~

.. code-block:: apache

    <VirtualHost *:443>
        ServerName vpn.example.com

        ErrorLog ${APACHE*LOG*DIR}/error.log
        CustomLog ${APACHE*LOG*DIR}/access.log combined

        SSLEngine on
        SSLCertificateFile /path/to/crt
        SSLCertificateKeyFile /path/to/key
        SSLProtocol -all +TLSv1.2 +TLSv1.3

        ProxyPreserveHost On
        ProxyPass / http://10.0.0.1:8080/
        ProxyPassReverse / http://10.0.0.1:8080/
    </VirtualHost>

Nginx reverse proxy
~~~~~~~~~~~~~~~~~~~

.. code-block:: nginx

    server {
        listen 443;
        server_name         vpn.example.com;

        ssl_certificate     /path/to/crt;
        ssl*certificate*key /path/to/key;
        ssl_protocols       TLSv1.2 TLSv1.3;

        location / {
            proxy*set*header Host $host;
            proxy*set*header X-Real-IP $remote_addr;
            proxy_pass http://10.0.0.1:8080;
        }
    }
