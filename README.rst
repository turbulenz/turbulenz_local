==================================
Turbulenz Local Development Server
==================================

The Turbulenz local Python package provides a locally hosted web server for development of projects using the
`Turbulenz Engine <http://github.com/turbulenz/turbulenz_engine>`_.

The web server allows developers to work offline or rapidly iterate on their game development whilst still
providing all the API's and features of the Turbulenz services on `turbulenz.com <https://turbulenz.com>`_ and
the web hosted development `Turbulenz Hub <https://hub.turbulenz.com>`_

In addition to providing the Turbulenz Services APIs the server provides features such as game http request
metrics, asset browsers, asset dissassemblers and the ability to launch an asset viewer from the asset browser.

History
=======

The latest release is 1.0 which can be found here `<https://pypi.python.org/pypi/turbulenz_local/1.0>`_

A full history of changes can be found in the
`Changelog <http://github.com/turbulenz/turbulenz_local/blob/master/CHANGES.rst>`_


Installation/Setup
==================

The recommended paths for using Turbulenz Local is to either install the Turbulenz SDK from the Turbulenz Hub,
or clone the `Open Source Turbulenz Engine repository <http://github.com/turbulenz/turbulenz_engine>`_ and follow
it's setup guide.
Both of these methods will install Turbulenz Local and it's dependencies from `PyPi <http://pypi.python.org>`_ using
VirtualEnv, however you can also install Turbulenz Local globally on your system or via similar virtual
environment packages using Python package managers like SetupTools and pip.

Once installed the ``local_server`` command will be available in your environment, ``local_server --help`` will give
details on the available commands.

Turbulenz Local runs from a home folder where it stores all configuration data and data for the Turbulenz Services
such as leaderboard data, badge data, metrics etc. Specifying ``--home <path>`` will set the path for all other
commands, the default is a folder called devserver relative to the folder the script is run from.

To initialize a local server home folder (default configuration files etc) use ``local_server --init``

To launch Turbulenz Local use ``--launch`` with the optional ``--development`` if you wish to run the server in
development mode (auto restart on code changes, debug callstacks when crashing etc)

The remaining commands are primarily related to repackaging_


Documentation
=============

Full documentation for the usage of Turbulenz Local can be found in the Turbulenz Engine docs at
`<http://docs.turbulenz.com/local/index.html>`_

This documentation is built from the `Turbulenz Engine repository <http://github.com/turbulenz/turbulenz_engine>`_


Dependencies
============

The only dependencies for using Turbulenz Local are Python 2.7.x and a number of Python packages. These
additional packages will be automatically installed as dependencies when the Turbulenz Local package is installed
with a Python package manager.

.. _repackaging:

Repackaging Turbulenz Local
===========================

The distributed versions of Turbulenz Local on PyPi include optimized compacted JavaScript and HTML for the front-end
of the server. The ``local_server`` command includes ``--compile`` and ``--clean`` targets to perform these
optimizations. But has dependencies on the YUICompressor and UglifyJS which are not provided by default in the
repository. The locations of the YUICompressor JAR file and the UglifyJS script can be provided as parameters to the
``local_server`` command.
In addition the YUICompressor will require Java to be installed and UglifyJS requires NodeJS to be installed.

After running ``--compile`` the setup.py script will bundle all the generated optimized files with the package. The
package can also be built without the optimized files however they are recommended.


Licensing
=========

Turbulenz Local is licensed under the `MIT license <http://github.com/turbulenz/turbulenz_local/raw/master/LICENSE>`_

Contributing
============

Our contributors are listed `here <http://github.com/turbulenz/turbulenz_local/blob/master/CONTRIBUTORS.rst>`_

Contributions are always encouraged whether they are small documentation tweaks, bug fixes or suggestions for larger
changes. You can check the `issues <http://github.com/turbulenz/turbulenz_local/issues>`_ or `discussion forums
<https://groups.google.com/group/turbulenz-engine-users>`_ first to see if anybody else is undertaking similar changes.

If you'd like to contribute any changes simply fork the project on Github and send us a pull request or send a Git
patch to the discussion forums detailing the proposed changes. If accepted we'll add you to the list of contributors.

We include a .pylintrc file in the repository which allows you to check your code conforms to our standards. Our
documentation is built from the Turbulenz Engine open source repository so please consider how your changes may affect
the documentation.

Note: by contributing code to the Turbulenz Local Development Server project in any form, including sending a pull
request via Github, a code fragment or patch via private email or public discussion groups, you agree to release your
code under the terms of the MIT license that you can find in the
`LICENSE <http://github.com/turbulenz/turbulenz_local/raw/master/LICENSE>`_ file included in the source distribution.


Links
=====

| Turbulenz game site - `turbulenz.com <https://turbulenz.com>`_
| Turbulenz developer service and SDK download - `hub.turbulenz.com <https://hub.turbulenz.com>`_
| Documentation for this module and the SDK - `docs.turbulenz.com <http://docs.turbulenz.com>`_
| About Turbulenz - `biz.turbulenz.com <http://biz.turbulenz.com>`_
