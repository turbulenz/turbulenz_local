// Copyright (c) 2011-2012 Turbulenz Limited

/*global Backbone*/
/*global Templates*/
/*global window*/
/*global $*/
/*jshint nomen: false*/
/*global _*/
/*jshint nomen: true*/
/*exported LocalDeployView*/

var LocalDeployView = Backbone.View.extend({
    el: 'body',

    initialize: function ()
    {
        this.app = this.options.app;
        this.login_template = Templates.local_deploy_login_template;
        this.select_template = Templates.local_deploy_select_template;
        this.upload_template = Templates.local_deploy_upload_template;
        /*jshint nomen: false*/
        _.bindAll(this, 'render', 'initialiseDeployForms');
        /*jshint nomen: true*/

        this.app.bind('deploy:set', this.setDialogs);
        this.app.bind('deploy:initialise', this.initialiseDeployForms);
        return this;
    },

    render: function (/* slug */)
    {
        $(this.el).jqoteapp(this.login_template);
        $(this.el).jqoteapp(this.select_template);
        $(this.el).jqoteapp(this.upload_template);
        return this;
    },

    setDialogs: function () {
        $('#deploy_login_dialog_id').dialog({
            autoOpen: false,
            height: 250,
            width: 400,
            modal: true,
            close: function () {
                $('#deploy_login_id').val('').removeClass('ui-state-error');
                $('#deploy_password_id').val('').removeClass('ui-state-error');
            }
        });

        $('#deploy_select_dialog_id').dialog({
            autoOpen: false,
            height: 340,
            width: 500,
            modal: true,
            close: function () {
                $('#deploy_select_project_id')[0].options.length = 0;
                $('#deploy_new_version_number_id').val('').removeClass('ui-state-error');
                $('#deploy_select_version_id').removeAttr('disabled')[0].options.length = 0;
                $('#deploy_new_version_name_id').val('');
            }
        });

        $('#deploy_upload_dialog_id').dialog({
            autoOpen: false,
            height: 150,
            width: 800,
            modal: true
        });

        $('#deploy_upload_bar_id').progressbar({value: 0});
    },

    initialiseDeployForms: function (slug)
    {
        var router = this.app.router;
        var deploy_login_url = router.get('deploy-login');
        var deploy_start_url = router.get('deploy-start');
        var deploy_progress_url = router.get('deploy-progress');
        var deploy_postupload_progress_url = router.get('deploy-postupload-progress');
        var deploy_cancel_url = router.get('deploy-cancel');


        var deployLoginForm = $('#deploy_login_form_id'),
            deployLoginDialog = $('#deploy_login_dialog_id'),
            deploySelectForm = $('#deploy_select_form_id'),
            deploySelectDialog = $('#deploy_select_dialog_id'),
            deployUploadForm = $('#deploy_upload_form_id'),
            deployUploadDialog = $('#deploy_upload_dialog_id'),
            deployUploadBar = $('#deploy_upload_bar_id'),
            deployUploadFilesCounter = $('#deploy_upload_files_counter_id'),
            deployUploadBytesCounter = $('#deploy_upload_bytes_counter_id'),
            slugPattern = new RegExp('^[a-z0-9]+[a-z0-9-\\.]*$'),
            progressInterval = 100,
            loginCookie = null,
            that = this;

        function commaFormatted(n)
        {
            var a = [];
            n = n.toString();
            while (3 < n.length)
            {
                a.unshift(n.substr(n.length - 3));
                n = n.substr(0, n.length - 3);
            }
            if (0 < n.length)
            {
                a.unshift(n);
            }
            return a.join(',');
        }

        function startDeploy(deployInfo)
        {
            var timeOutID, checkProgress, checkPostuploadProgress, startString, progressString;

            startString = 'local=' + deployInfo.local +
                           '&' + deployInfo.cookie +
                           '&project=' + deployInfo.project +
                           '&version=' + deployInfo.version;
            if (deployInfo.versiontitle)
            {
                startString += '&versiontitle=' + deployInfo.versiontitle;
            }

            function beforeClose(/* event, ui */)
            {
                if (timeOutID)
                {
                    clearTimeout(timeOutID);
                    timeOutID = undefined;

                    var progress = deployUploadBar.progressbar('option', 'value');
                    if (progress < 100)
                    {
                        if (window.confirm('Do you want to cancel the deploy?'))
                        {
                            $.ajax({
                                async: false,
                                type: 'POST',
                                data: progressString,
                                url: deploy_cancel_url
                            });
                            return true;
                        }
                        else
                        {
                            timeOutID = setTimeout(checkProgress, progressInterval);
                            return false;
                        }
                    }
                    return true;
                }
                else
                {
                    return false;
                }
            }

            function beforePostuploadClose(/* event, ui */)
            {
                if (timeOutID)
                {
                    clearTimeout(timeOutID);
                    timeOutID = undefined;

                    var progress = deployUploadBar.progressbar('option', 'value');
                    if (progress < 100)
                    {
                        window.alert('Cannot interrupt Post-upload processing');
                        timeOutID = setTimeout(checkPostuploadProgress, progressInterval);
                        return false;
                    }
                    return true;
                }
                else
                {
                    return false;
                }
            }

            function onProgress(response)
            {
                var progress_info = response.data,
                    uploaded_files = progress_info.uploaded_files,
                    uploaded_bytes = progress_info.uploaded_bytes,
                    total_files = progress_info.total_files,
                    num_files = progress_info.num_files,
                    num_bytes = progress_info.num_bytes,
                    progress;

                if (total_files)
                {
                    if (uploaded_files)
                    {
                        if (uploaded_files < total_files)
                        {
                            progress = (100 * (uploaded_bytes / num_bytes));
                            deployUploadFilesCounter.text('Uploading modified files: ' +
                                                          uploaded_files + '/' + total_files);
                            deployUploadBytesCounter.text('Uploading bytes: ' +
                                                          commaFormatted(uploaded_bytes) +
                                                          '/' +
                                                          commaFormatted(num_bytes));
                        }
                        else
                        {
                            progress = 100;
                            deployUploadFilesCounter.text('Uploading finished.');
                            deployUploadBytesCounter.text('');
                        }
                    }
                    else
                    {
                        progress = (100 * (num_files / total_files));
                        deployUploadFilesCounter.text('Scanning and compressing files: ' +
                                                      num_files + '/' + total_files);
                        deployUploadBytesCounter.text('Total bytes: ' + commaFormatted(num_bytes));
                    }
                }
                else
                {
                    progress = 0;
                }
                deployUploadBar.progressbar('option', 'value', progress);
                if (progress >= 100)
                {
                    //window.alert('Upload successful.');

                    deployUploadFilesCounter.text('');
                    deployUploadBytesCounter.text('');

                    clearTimeout(timeOutID);
                    timeOutID = undefined;

                    $('#deploy_upload_cancel_id').hide();
                    deployUploadDialog.unbind().bind('dialogbeforeclose', beforePostuploadClose);

                    timeOutID = setTimeout(checkPostuploadProgress, 500);
                }
                else
                {
                    if (total_files > 1000)
                    {
                        timeOutID = setTimeout(checkProgress, (5 * progressInterval));
                    }
                    else
                    {
                        timeOutID = setTimeout(checkProgress, progressInterval);
                    }
                }
            }

            function onProgressError(XMLHttpRequest, textStatus)
            {
                if ('timeout' === textStatus)
                {
                    window.alert('The connection to local.turbulenz timed out.');
                }
                else //('error' === textStatus)
                {
                    var response = JSON.parse(XMLHttpRequest.responseText),
                        msg = response ? response.msg : "unknown",
                        status = XMLHttpRequest.status;

                    if (500 === status)
                    {
                        window.alert('Local.turbulenz failed.\n' + msg);
                    }
                    else
                    {
                        window.alert('Hub uploading failed.\n' + msg);
                    }
                }
                deployUploadDialog.unbind('dialogbeforeclose', beforeClose);
                deployUploadDialog.dialog('close');
            }

            function onPostuploadProgress(response)
            {
                var progress_info = response.data,
                    processed_content = progress_info.processed,
                    total_content = progress_info.total,
                    progress;

                if (total_content)
                {
                    if (processed_content < total_content)
                    {
                        progress = (100 * (processed_content / total_content));
                        deployUploadFilesCounter.text('Post-upload processing progress: ' +
                                                      processed_content + '/' + total_content);
                        deployUploadBytesCounter.text('');
                    }
                    else
                    {
                        progress = 100;
                        deployUploadFilesCounter.text('Processing finished.');
                        deployUploadBytesCounter.text('');
                    }
                }
                else
                {
                    progress = 0;
                }
                deployUploadBar.progressbar('option', 'value', progress);
                if (progress >= 100)
                {
                    try
                    {
                        window.alert('Deployment complete' + (progress_info.msg ? ':\n\n' + progress_info.msg : ''));
                    }
                    catch (error)
                    {
                        window.alert('Deployment complete');
                    }

                    deployUploadFilesCounter.text('');
                    deployUploadBytesCounter.text('');
                    deployUploadDialog.unbind('dialogbeforeclose', beforePostuploadClose);
                    deployUploadDialog.dialog('close');

                    $('#deploy_upload_cancel_id').show();
                }
                else
                {
                    if (total_content > 1000)
                    {
                        timeOutID = setTimeout(checkPostuploadProgress, (5 * progressInterval));
                    }
                    else
                    {
                        timeOutID = setTimeout(checkPostuploadProgress, progressInterval);
                    }
                }
            }

            function onPostuploadProgressError(XMLHttpRequest, textStatus)
            {
                if ('timeout' === textStatus)
                {
                    window.alert('The connection to local.turbulenz timed out.');
                }
                else //('error' === textStatus)
                {
                    var response = JSON.parse(XMLHttpRequest.responseText),
                        msg = response ? response.msg : "unknown",
                        status = XMLHttpRequest.status;

                    if (500 === status)
                    {
                        window.alert('Hub failed.\n' + msg);
                    }
                    else
                    {
                        window.alert('Hub post-processing failed.\n' + msg);
                    }
                }
                deployUploadDialog.unbind('dialogbeforeclose', beforePostuploadClose);
                deployUploadDialog.dialog('close');
            }

            function stopUpload()
            {
                deployUploadDialog.unbind('dialogbeforeclose', beforeClose);
                deployUploadDialog.dialog('close');
            }

            checkProgress = function checkProgressFn()
            {
                $.ajax({
                    async: false,
                    type: 'POST',
                    data: progressString,
                    url: deploy_progress_url,
                    success: onProgress,
                    error: onProgressError
                });
            };

            checkPostuploadProgress = function checkPostuploadProgressFn()
            {
                $.ajax({
                    async: false,
                    type: 'POST',
                    data: progressString,
                    url: deploy_postupload_progress_url,
                    success: onPostuploadProgress,
                    error: onPostuploadProgressError
                });
            };

            function onCancel()
            {
                if (beforeClose())
                {
                    deployUploadFilesCounter.text('');
                    deployUploadBytesCounter.text('');
                    deployUploadDialog.unbind('dialogbeforeclose', beforeClose);
                    deployUploadDialog.dialog('close');
                }
                return false;
            }

            function onStart(response)
            {
                deploySelectDialog.dialog('close');

                var data = response.data;
                if (data)
                {
                    progressString = data;

                    deployUploadFilesCounter.text('Scanning files...');
                    deployUploadBytesCounter.text('');
                    deployUploadBar.progressbar('option', 'value', 0);
                    deployUploadForm.unbind();
                    $('#deploy_upload_cancel_id').unbind().click(onCancel);
                    deployUploadDialog.unbind().dialog('open').bind('dialogbeforeclose', beforeClose);

                    timeOutID = setTimeout(checkProgress, 500);
                }
            }

            function onStartError(XMLHttpRequest, textStatus)
            {
                if ('timeout' === textStatus)
                {
                    window.alert('The connection to the Hub timed out.');
                }
                else //('error' === textStatus)
                {
                    var response = JSON.parse(XMLHttpRequest.responseText),
                        msg = response ? response.msg : "unknown",
                        status = XMLHttpRequest.status;

                    if (500 === status)
                    {
                        window.alert('Local.turbulenz is not setup correctly.\n' + msg);
                    }
                    else
                    {
                        window.alert('Hub log in details are incorrect.\n' + msg);
                    }
                }
            }


            deployUploadForm.unbind();
            deployUploadForm.submit(stopUpload);

            $.ajax({
                async: false,
                timeout: 10000,
                type: 'POST',
                url: deploy_start_url,
                data: startString,
                success: onStart,
                error: onStartError
            });
        }

        function onLogin(response)
        {
            var hub_info = response.data,
                projects = hub_info.projects,
                numProjects = (projects ? projects.length : 0),
                createNewVersionNumberInput = $('#deploy_new_version_number_id'),
                createSelectProjectInput = $('#deploy_select_project_id'),
                projectOptions = createSelectProjectInput[0].options,
                createSelectVersionInput = $('#deploy_select_version_id'),
                versionOptions = createSelectVersionInput[0].options;

            $('body').css('cursor', 'auto');

            if (numProjects < 1)
            {
                window.alert('This user has no projects on Hub that you can deploy to.');
                return;
            }

            loginCookie = hub_info.cookie;

            if (numProjects > 1)
            {
                if (projects[0].modified)
                {
                    projects.sort(function (a, b) {
                        return b.modified - a.modified;
                    });
                }
                else
                {
                    projects.sort(function (a, b) {
                        return b.created - a.created;
                    });
                }
            }

            function htmlDecode(value)
            {
                return $('<div/>').html(value).text();
            }

            for (var p = 0; p < numProjects; p += 1)
            {
                var project = projects[p];
                var option = new Option(htmlDecode(project.title), project.slug);
                projectOptions[projectOptions.length] = option;
                if (p === 0)
                {
                    createSelectVersionInput.val(project.slug);
                }
            }

            function projectChanged()
            {
                function sortVersions(a, b)
                {
                    var aa = a.version.split('.');
                    var bb = b.version.split('.');
                    for (var x = 0; aa[x] && bb[x]; x += 1)
                    {
                        var ax = aa[x];
                        var bx = bb[x];
                        if (ax !== bx)
                        {
                            var an = Number(ax), bn = Number(bx);
                            if (isNaN(an) || isNaN(bn))
                            {
                                return (aa[x] < bb[x]) ? 1 : -1;
                            }
                            else
                            {
                                return bn - an;
                            }
                        }
                    }
                    return bb.length - aa.length;
                }

                versionOptions.length = 0;

                var p = createSelectProjectInput.find('option:selected').index();
                var project = projects[p];
                var versions = project.versions;
                var numVersions, version, versionName, v;

                if (versions)
                {
                    numVersions = versions.length;
                    if (1 < numVersions)
                    {
                        versions.sort(sortVersions);
                    }
                    for (v = 0; v < numVersions; v += 1)
                    {
                        version = versions[v];
                        versionName = version.version;
                        createSelectVersionInput.append($('<option></option>')
                            .attr('value', versionName)
                            .text(versionName));
                    }
                }
                var locked_versions = project.locked_versions;
                if (locked_versions)
                {
                    numVersions = locked_versions.length;
                    if (1 < numVersions)
                    {
                        locked_versions.sort(sortVersions);
                    }
                    for (v = 0; v < numVersions; v += 1)
                    {
                        version = locked_versions[v];
                        versionName = version.version;
                        createSelectVersionInput.append($('<option></option>')
                            .attr('disabled', 'disabled')
                            .attr('value', versionName)
                            .text(versionName + ' (locked)'));
                    }
                }
                if (!versions || versions.length === 0)
                {
                    createSelectVersionInput.prepend($('<option></option>')
                            .attr('disabled', 'disabled')
                            .attr('value', '')
                            .text('No Writable Versions'));
                }
            }

            function versionNumberChanged()
            {
                var createNewVersionNumberVal = $.trim(createNewVersionNumberInput.val());
                if (createNewVersionNumberVal)
                {
                    createSelectVersionInput.attr('disabled', true);
                }
                else
                {
                    createSelectVersionInput.removeAttr('disabled');
                }
            }

            projectChanged();

            createSelectProjectInput.unbind();
            createSelectProjectInput.change(projectChanged);

            createNewVersionNumberInput.unbind();
            createNewVersionNumberInput.change(versionNumberChanged);

            deploySelectDialog.dialog('open');
        }

        function doLogin()
        {
            var correct = true,
                loginInput = $('#deploy_login_id'),
                passwordInput = $('#deploy_password_id'),
                loginInputVal = $.trim(loginInput.val()),
                passwordInputVal = $.trim(passwordInput.val()),
                remembermeVal = $('#rememberme').attr('checked');

            loginInput.removeClass('ui-state-error');
            passwordInput.removeClass('ui-state-error');

            if (!loginInputVal)
            {
                loginInput.addClass('ui-state-error');
                correct = false;
            }

            if (!passwordInputVal)
            {
                passwordInput.addClass('ui-state-error');
                correct = false;
            }

            if (correct)
            {
                var loginString = 'login=' + loginInputVal +
                                  '&password=' + passwordInputVal;

                $('body').css('cursor', 'wait');

                $.ajax({
                    timeout: 10000,
                    type: 'POST',
                    url: deploy_login_url,
                    data: loginString,
                    success: function onLoginSuccessFn() {
                        if (remembermeVal)
                        {
                            that.tempLogin = loginInputVal;
                            that.tempPassword = passwordInputVal;
                            that.rememberme = true;
                        }
                        else
                        {
                            that.tempLogin = null;
                            that.tempPassword = null;
                            that.rememberme = false;
                        }
                        onLogin.apply(this, arguments);
                    },
                    error: function onLoginErrorFn(XMLHttpRequest, textStatus)
                    {
                        $('body').css('cursor', 'auto');

                        var status = XMLHttpRequest.status;
                        if ('timeout' === textStatus)
                        {
                            window.alert('The connection to the Hub timed out.');
                        }
                        else if (status === 500)
                        {
                            window.alert('Connection to the Hub failed. Please try again later');
                        }
                        else //('error' === textStatus)
                        {
                            var response = JSON.parse(XMLHttpRequest.responseText),
                                msg = response ? response.msg : "unknown";
                            window.alert('Hub log in failed.\n' + msg);
                        }
                    }
                });

                deployLoginDialog.dialog('close');
            }

            return false;
        }

        function doSelect()
        {
            var correct = true,
                deployInfo = {},
                createSelectProjectInput = $('#deploy_select_project_id'),
                createSelectVersionInput = $('#deploy_select_version_id'),
                createNewVersionNumberInput = $('#deploy_new_version_number_id'),
                createNewVersionNameInput = $('#deploy_new_version_name_id'),
                createSelectProjectVal = createSelectProjectInput.val(),
                createSelectVersionVal = createSelectVersionInput.val(),
                createNewVersionNumberVal = $.trim(createNewVersionNumberInput.val()),
                createNewVersionNameVal = $.trim(createNewVersionNameInput.val());

            createNewVersionNumberInput.removeClass('ui-state-error');
            createNewVersionNameInput.removeClass('ui-state-error');

            if (createNewVersionNumberVal)
            {
                if (!slugPattern.test(createNewVersionNumberVal))
                {
                    createNewVersionNumberInput.addClass('ui-state-error');
                    correct = false;
                }
                else
                {
                    deployInfo.version = createNewVersionNumberVal;
                    deployInfo.versiontitle = createNewVersionNameVal;
                }
            }
            else if (!createSelectVersionVal)
            {
                createNewVersionNumberInput.addClass('ui-state-error');
                correct = false;
            }
            else
            {
                deployInfo.version = createSelectVersionVal;
            }

            if (correct)
            {
                deployInfo.project = createSelectProjectVal;
                deployInfo.cookie = loginCookie;
                deployInfo.local = slug;

                deployUploadDialog.dialog('option', 'title', 'Deploying ' + slug + ' to ' + deployInfo.version);

                startDeploy(deployInfo);
            }

            return false;
        }

        deployLoginForm.unbind();
        deploySelectForm.unbind();

        deployLoginForm.submit(doLogin);
        deploySelectForm.submit(doSelect);

        if (this.rememberme && this.tempLogin && this.tempPassword)
        {
            deployLoginForm.find('input[name="login"]').val(this.tempLogin);
            deployLoginForm.find('input[name="password"]').val(this.tempPassword);
            deployLoginForm.find('input[name="rememberme"]').attr('checked', true);
        }
    }
});

