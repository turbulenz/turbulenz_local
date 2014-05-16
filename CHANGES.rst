==================================
Turbulenz Local Development Server
==================================

.. contents::
    :local:

.. _version-1.x-dev:

1.x-dev
-------

2014-05-16
- Fixed local server store API to stop game's users to purchasing "own" resources multiple times.
- Fixed local server crashing for store API calls with malformed parameters.

.. _version-1.1.4:

1.1.4
-----

:release-date: 2013-11-12

- Updated the way the deployment code sets timeouts for compatibility with the lastest versions of urllib3.
- Fixed some mimetypes for IE11 support.

.. _version-1.1.3:

1.1.3
-----

:release-date: 2013-10-30

- Changed local carousel to order projects by last modified from left to right.
- Updated package to use pylint 1.0 for code checks.
- Added a scheme to allow launching apps with iOS developer client.
- Fixed crash when running deploygame tool outside of a terminal.
- Added mimetype to server up ktx files.

.. _version-1.1.2:

1.1.2
-----

:release-date: 2013-07-30

- Support for launching .tzjs files in the native client on Android
- Fix issues with unicode characters in usernames
- Fix import of Turbulenz SDK version
- Fix for custom metrics events passed in batches with time offsets of 0
- Refuse negative scores passed to leaderboards
- Allow the deploygame tool to set the title on a project version
- Fix expired delayed notifications not being deleted from the file system

.. _version-1.1.1:

1.1.1
-----

:release-date: 2013-06-10

- Fix issues with non lowercase and non alphanumeric characters in usernames

.. _version-1.1:

1.1
---

:release-date: 2013-06-03

- Updated hub login to support remembering a users login details.
- Improved project upload dialogs.
- Moved common settings into a shared ini file between development and release environments.
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
