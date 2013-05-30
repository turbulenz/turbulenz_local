==================================
Turbulenz Local Development Server
==================================

.. contents::
    :local:

.. _version-1.x-dev:

1.x-dev
-------

2013-05-30

- Added a login panel (no password required) for cookie based logins. This allows testing multiple users on local.
- Added Data Shares API endpoints.
- Added Notifications API endpoints.

.. _version-1.0.2:

1.0.2
-----

:release-date: 2013-05-21

- Fixed deployment of games to the Turbulenz Hub when 7-zip binaries are not installed

.. _version-1.0.1:

1.0.1
-----

:release-date: 2013-05-20

- Add support to the customevents api for sending batches of events to minimize http requests
- Update the routing for the save file handler which was not allowing saves when slugs contained non ascii
  characters
- Fix the --clean command to match the documentation
- Support new format of cached upload hashes from the Turbulenz Hub. This avoids the issue where files with matching
  content are uploaded with different filenames
- Support saving of binary data in the local server save api


.. _version-1.0:

1.0
---

:release-date: 2013-05-02

.. _v1.0-changes:

- First open source release
