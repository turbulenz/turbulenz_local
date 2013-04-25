// Copyright (c) 2011-2012 Turbulenz Limited

/*global Backbone*/
/*global Templates*/
/*global window*/
/*jshint nomen: false*/
/*global _*/
/*global $*/
/*global alert*/
/*jshint nomen: true*/
/*exported LocalEditView*/

var LocalEditView = Backbone.View.extend({
    el: '#details',
    globalUrls: {},

    initialize: function initializeFn() {
        this.app = this.options.app;
        this.template = Templates.local_edit_game_template;
        this.directory_options_template = Templates.local_directory_options_template;
        /*jshint nomen: false*/
        _.bindAll(this, 'render');
        /*jshint nomen: true*/

        this.app.bind('game:edit', this.render);

        this.SLUG_PATTERN = new RegExp('^[a-z0-9]+[a-z0-9-]*$');
        this.ENGINE_VERSION_PATTERN = new RegExp('^(\\d+\\.)(\\d+)$');
        this.ASPECT_RATIO_PATTERN = new RegExp('^(?=.*[1-9])\\d+(\\.\\d+)?:(?=.*[1-9])\\d+(\\.\\d+)?$');

        return this;
    },

    setUrls: function setUrlsFn(slug) {
        var router = this.app.router;
        var globalUrls = this.globalUrls;
        globalUrls.url = router.get('edit-overview', {slug: slug});
        globalUrls.saveGameUrl = router.get('edit-save', {slug: slug});
        globalUrls.deleteGameUrl = router.get('edit-delete', {slug: slug});
        globalUrls.loadGameUrl = router.get('edit-load', {slug: slug});
        globalUrls.dirOptionsUrl = router.get('edit-directory-options', {slug: slug});
        globalUrls.createSlugUrl = router.get('edit-create-slug', {slug: slug});
    },

    render: function renderFn(slug) {
        this.app.setCurrentView(this);
        this.setUrls(slug);
        var globalUrls = this.globalUrls;

        var that = this;
        $.get(globalUrls.url, function (res) {
            $(that.el).jqotesub(that.template, {
                data: res.data,
                saveUrl: globalUrls.saveGameUrl,
                deleteUrl: globalUrls.deleteGameUrl
            });
            that.setPage(slug);
        });
        return this;
    },

    preLeave: function preLeaveFn() {
        if (!this.edited)
        {
            return true;
        }
        var hash = window.location.hash.split('/');
        if (hash.length > 1 && hash[1] === 'edit')
        {
            return false;
        }
        if (window.confirm('This page contains unsaved changes. Are you sure you want to discard them?'))
        {
            this.edited = false;
            return true;
        }
        return false;
    },

    getDeployFilesString: function getDeployFilesStringFn() {
        var value = '';

        $('#deploy_files_id option').each(function () {
            value += $.trim($(this).val());
        });
        return value;
    },

    // Store each text-field's value in the DOM under
    // 'oldValue'.
    resetOldValues: function resetOldValuesFn() {
        $('.validate').each(function () {
            $(this)[0].oldValue = $.trim($(this).val());
        });
        $('#deploy_files_id')[0].oldValue = this.getDeployFilesString();
    },

    // remove leading and trailing slashes and white space from
    // 'str'.
    sanitize: function sanitizeFn(str) {
        var safetyCounter = 0;
        str = $.trim(str);

        while (str.slice(-1) === '/' || str.slice(-1) === '\\')
        {
            str = $.trim(str.slice(0, -1));
            if (safetyCounter > 1000)
            {
                break;
            }
        }
        return str;
    },


    delayed: function delayedFn(callback, delay) {
        if (typeof delay === 'undefined')
        {
            delay = 1000;
        }
        // store the timer in the event handler closure
        var timer = 0;

        // return a function to bind to the event, which takes an event object
        // parameter
        return function (event) {
            // when the event is fired, reset the timer to call the callback
            // function after the specified delay
            clearTimeout(timer);
            timer = setTimeout(function () {
                callback(event);
            }, delay);
        };
    },


    slugHasCorrectFormat: function slugHasCorrectFormatFn() {
        return this.SLUG_PATTERN.test($('#slug_id').val());
    },

    updateSlugField: function updateSlugFieldFn(title) {
        var url = this.globalUrls.createSlugUrl;
        var that = this;
        var params = {
            'title': title
        };
        $.get(url, params, function (data) {
            $('#slug_id').val(data.data);
            $('#slug_message').html('* Note: slug has been automatically updated.');
            $('#slug_error').html(data.message);
            that.finishFieldChange();
        });
    },

    engineVersionHasCorrectFormat: function engineVersionHasCorrectFormatFn() {
        return this.ENGINE_VERSION_PATTERN.test($('#engine_version_id').val());
    },

    aspectRatioHasCorrectFormat: function aspectRatioHasCorrectFormatFn() {
        return this.ASPECT_RATIO_PATTERN.test($('#aspect_ratio_id').val());
    },

    showBusyIcon: function showBusyIconFn(field) {
        $(field).closest('.field').find('.status-icon').addClass('busy');
    },

    // Remove the status-icon from a text-field, signalling
    // That its value has changed.
    hideStatusIcon: function hideStatusIconFn(field) {
        $(field).closest('.field').removeClass('complete').removeClass('incorrect');
    },

    hideBusyIcon: function hideBusyIconFn(field) {
        $(field).closest('.field').find('.status-icon').removeClass('busy');
    },

    markFieldCorrect: function markFieldCorrectFn(field) {
        $(field).closest('.field').removeClass('incorrect').addClass('correct');
    },


    markFieldError: function markFieldErrorFn(field) {
        $(field).closest('.field').removeClass('complete').addClass('incorrect');
    },

    hideDirectoryOptions: function hideDirectoryOptionsFn(lock) {
        var directoryOptions = $('#directory-options');
        directoryOptions.empty();
        directoryOptions.removeClass('enabled');
        if (lock)
        {
            $('#path_id').removeClass('unlocked').attr('disabled', 'disabled');
            $('#lock_id').removeClass('unlocked').attr('value', 'locked');
        }
    },


    showFieldsets: function showFieldsetsFn(enable) {
        if (enable)
        {
            $('#edit-form fieldset').not('#directory-fieldset').addClass('enabled');
        }
        else
        {
            $('#edit-form fieldset').not('#directory-fieldset').removeClass('enabled');
        }
    },


    checkPath: function checkPathFn() {
        var that = this;
        $('#path_error').remove();
        var dir = $('#path_id').val();

        if (this.sanitize(dir) === '' || dir ===  $('#path_id')[0].oldValue)
        {
            that.hideDirectoryOptions(false);
            that.hideBusyIcon($('#path_id'));
        }
        else
        {
            var url = this.globalUrls.dirOptionsUrl;
            var params = {
                'dir': dir
            };

            $.get(url, params, function (data) {
                var directoryOptions = $('#directory-options');
                $('#directory-options').jqotesub(that.directory_options_template, data);

                $('#directory-fieldset').addClass('complete');

                $("#confirm-path").click(function () {
                    that.saveGame();
                    return false;
                });
                $("#use-data").click(function () {
                    that.loadGame();
                    return false;
                });
                $("#overwrite-data").click(function () {
                    that.saveGame();
                    return false;
                });
                $("#create-path").click(function () {
                    that.saveGame();
                    return false;
                });
                directoryOptions.addClass('enabled');
            });
        }
    },

    // Is called when a key-up event is detected in any
    // of the text fields.
    startFieldChange: function startFieldChangeFn(field) {
        var that = this;
        this.hideStatusIcon(field);

        if ($(field).attr('id') === 'path_id')
        {
            that.checkPath();
        }
        else if ($(field).attr('id') === 'title_id')
        {
            if ($.trim($(field).val()) !== $.trim($(field)[0].oldValue))
            {
                //if the slug has not been edited before
                if (!$('#slug_id').hasClass('edited'))
                {
                    that.updateSlugField($(field).val());
                    that.hideBusyIcon($(field));
                }
            }
            else
            {
                $('#slug_id').val($('#slug_id')[0].oldValue);
                that.hideBusyIcon($('#slug_id'));
            }
        }
        else if ($(field).attr('id') === 'slug_id')
        {
            $('#slug_id').addClass('edited');
            $('#slug_message').empty();
        }
        this.finishFieldChange();
        this.hideBusyIcon(field);
    },

    // Check whether any fields have changed and if so,
    // enable the 'save'
    // button if saving is possible.
    // Should only be called after all changes are done.
    finishFieldChange: function finishFieldChangeFn() {
        var save = false;
        var that = this;

        if ((this.sanitize($('#slug_id').val()) !== '') && (this.slugHasCorrectFormat()))
        {
            $('.validate').each(function () {
                var $this = $(this);
                var value;

                if ($this.attr('id') === 'deploy_files_id')
                {
                    value = that.getDeployFilesString();
                }
                else
                {
                    value = $this.val();
                }

                if (value !== $this[0].oldValue)
                {
                    save = true;
                    that.hideStatusIcon($this);
                    that.markFieldCorrect($this);
                }
            });
        }
        else
        {
            that.markFieldError('#slug_id');
            $('#slug_id').removeClass('edited');
        }

        if (!this.engineVersionHasCorrectFormat())
        {
            that.markFieldError($('#engine_version_id'));
            save = false;
        }

        if (!this.aspectRatioHasCorrectFormat())
        {
            that.markFieldError($('#aspect_ratio_id'));
            save = false;
        }

        this.setEdited(save);
    },


    updatePage: function updatePageFn(data) {
        if (data.ok)
        {
            var oldSlug = $('#slug_id')[0].oldValue;
            var newSlug = data.data.slug;

            $('#' + oldSlug).attr('id', newSlug);
            $('#' + newSlug).removeClass('Temporary');
            $('#' + newSlug + ' > div.game-box > h2').html(data.data.title);

            //trigger event to re-render game panel
            this.app.trigger('game:refresh', '#' + newSlug);

            this.resetOldValues();
        }
        else
        {
            window.alert('Page could not be updated: \n');
        }
    },


    saveGame: function saveGameFn() {
        var that = this;
        $('#deploy_files_id option').attr('selected', 'selected');

        var params = {
            'path': this.sanitize($('#path_id').val()),
            'title': this.sanitize($('#title_id').val()),
            'slug': this.sanitize($('#slug_id').val()),
            'plugin_main': $('#plugin_main_text').val(),
            'canvas_main': $('#canvas_main_text').val(),
            'mapping_table': $('#mapping_table_text').val(),
            'deploy_files': $('#deploy_files_id').val(),
            'engine_version': $('#engine_version_id').val(),
            'is_multiplayer': $('#is_multiplayer_id').val(),
            'aspect_ratio': $('#aspect_ratio_id').val()
        };

        if (params.deploy_files)
        {
            params.deploy_files = params.deploy_files.join('\n');
        }

        var slug = params.slug;

        if (slug !== '')
        {
            $.ajax({
                url: that.globalUrls.saveGameUrl,
                data: params,
                type: 'POST',
                success: function successFn(data)
                {
                    if (data.ok)
                    {
                        if ($('#directory-fieldset').hasClass('complete'))
                        {
                            that.hideDirectoryOptions(true);
                            that.showFieldsets(true);
                            that.setEdited(false);
                        }
                        var newSlug = data.data.slug;
                        that.app.carousel.setActionButtons(newSlug);
                        document.location.hash = '/edit/' + newSlug;
                        that.updatePage(data);
                    }
                    else
                    {
                        window.alert(data.msg);
                    }
                },
                error: function errorFn(XMLHttpRequest /*, textStatus, errorThrown */)
                {
                    if (XMLHttpRequest.status !== 200)
                    {
                        var theResponse = XMLHttpRequest.responseText;
                        var obj = JSON.parse(theResponse);
                        alert(obj.msg);
                    }
                }
            });
        }
        else
        {
            window.alert('Slug cannot be empty!');
        }
    },


    loadGame: function loadGameFn() {
        var that = this;
        var params = {
            'path': that.sanitize($('#path_id').val())
        };

        $.get(this.globalUrls.loadGameUrl, params, function (data) {
            if ($('#directory-fieldset').hasClass('complete'))
            {
                that.hideDirectoryOptions(true);
                that.showFieldsets(true);
                that.setEdited(false);
            }
            var slug = data.data.slug;
            that.app.carousel.setActionButtons(slug);
            document.location.hash = '/edit/' + slug;
            that.updatePage(data);
        });
    },


    deleteGame: function deleteGameFn(askForConfirmation, slug, quiet) {
        var that = this;
        var url;

        if (slug)
        {
            url = this.app.router.get('edit-delete', {slug: slug});
        }
        else
        {
            url = this.globalUrls.deleteGameUrl;
        }

        if (askForConfirmation === undefined)
        {
            askForConfirmation = true;
        }

        if (!askForConfirmation ||
            window.confirm('This deletes the game from the games-list. \n\n' +
                           'Local game files still need to be removed manually.\n\n' +
                           'Do you want to proceed?', 'xyz'))
        {
            $.ajax({
                url: url,
                async: false,
                type: 'GET',
                success: function successFn(/* data */) {
                    if (!quiet)
                    {
                        that.app.trigger('carousel:make');
                        that.app.trigger('carousel:refresh');
                        that.app.trigger('carousel:collapse');
                    }
                }
            });
        }
        return false;
    },

    setSaveButton: function setSaveButtonFn(enabled) {
        if (enabled)
        {
            $('.save').addClass('enabled');
        }
        else
        {
            $('.save').removeClass('enabled');
        }
    },

    // Enable/disable the save-button.
    setEdited: function setEditedFn(active) {
        if (active === null)
        {
            active = false;
        }

        this.edited = active;
        this.setSaveButton(active);
    },


    setPage: function setPageFn(/* slug */) {
        var that = this;
        try
        {
            $('#path_id').focus();
        }
        catch (e)
        {}

        // Store each field's value in its DOM-object
        this.resetOldValues();

        // Display throbber when a text field is being typed in.
        $('.validate').keyup(function () {
            that.showBusyIcon(this);
        });

        // After a short delay, execute input-specific functions.
        // These need to remove the throbber when finished.
        $('.validate').keyup(this.delayed(function (event) {
            that.startFieldChange($(event.target));
        }, 1000));

        // Attach listeners to buttons.
        $('.save').click(function () {
            if ($(this).hasClass('enabled'))
            {
                that.saveGame();
            }
            return false;
        });

        $('.delete').click(function () {
            that.deleteGame();
            return false;
        });

        $('#lock_id').click(function () {
            if ($(this).val() === 'locked')
            {
                $(this).val('unlocked');
                $(this).addClass('unlocked');
                $('#path_id').addClass('unlocked');
                $('#path_id').removeAttr('disabled');
            }
        });

        this.setEdited(false);

        $('#plugin_main_id').change(function () {
            var path = $(this).val().split("\\");
            var newVal = path[path.length - 1];
            $('#plugin_main_text').val(newVal);

            $('#plugin_main_opt').replaceWith('<option id="plugin_main_opt" value="' + newVal + '">' + newVal + '<\/option>');
            that.finishFieldChange();
        });
        $('#plugin_main_text').change(function () {
            $('#plugin_main_opt').replaceWith('<option id="plugin_main_opt" value="' + $(this).val() + '">' + $(this).val() + '<\/option>');
            that.finishFieldChange();
        });

        $('#canvas_main_id').change(function () {
            var path = $(this).val().split("\\");
            var newVal = path[path.length - 1];
            $('#canvas_main_text').val(newVal);

            $('#canvas_main_opt').replaceWith('<option id="canvas_main_opt" value="' + newVal + '">' + newVal + '<\/option>');
            that.finishFieldChange();
        });
        $('#canvas_main_text').change(function () {
            $('#canvas_main_opt').replaceWith('<option id="canvas_main_opt" value="' + $(this).val() + '">' + $(this).val() + '<\/option>');
            that.finishFieldChange();
        });

        $('#mapping_table_id').change(function () {
            var path = $(this).val().split('\\');
            var newVal = path[path.length - 1];
            $('#mapping_table_text').val(newVal);

            $('#mapping_table_opt').replaceWith('<option id="mapping_table_opt" value="' + newVal + '">' + newVal + '<\/option>');
            that.finishFieldChange();
        });
        $('#mapping_table_text').change(function () {
            $('#mapping_table_opt').replaceWith('<option id="mapping_table_opt" value="' + $(this).val() + '">' + $(this).val() + '<\/option>');
            that.finishFieldChange();
        });

        var inputBox = $('#deploy_file_pattern_id');
        var code = null;

        inputBox.keyup(function (e) {
            //'enter' key was pressed
            code = (e.keyCode ? e.keyCode : e.which);
            if (code === 13 || code === 10)
            {
                var isDuplicate = false;
                $('#deploy_files_id option').each(function (/* index */) {
                    if ($(this).val() === inputBox.val())
                    {
                        isDuplicate = true;
                        //the file/pattern entered already exists
                    }
                });

                if (inputBox.val() !== '' && isDuplicate === false)
                {
                    //if a valid pattern was entered
                    $('#deploy_files_id').append('<option value="' + inputBox.val() + '">' + inputBox.val() + '<\/option>');
                    e.preventDefault();
                    $('#deploy_file_pattern_id').val('');
                }
            }
        });

        $('#deploy_files_id').keyup(function (e) {
            //'delete' key was pressed
            code = (e.keyCode ? e.keyCode : e.which);
            var selectedOption = $('#deploy_files_id option:selected');

            var notPluginMainOption = selectedOption.val() !== $('#plugin_main_text').val();
            var notCanvasMainOption = selectedOption.val() !== $('#canvas_main_text').val();
            var notMappingTableOption = selectedOption.val() !== $('#mapping_table_text').val();

            if ((code === 46) && notPluginMainOption && notCanvasMainOption && notMappingTableOption)
            {
                $('#deploy_files_id option:selected').remove();
                e.preventDefault();
            }
        });

        $('#is_multiplayer_id').change(function () {
            that.finishFieldChange();
        });

        if (!this.engineVersionHasCorrectFormat())
        {
            that.markFieldError($('#engine_version_id'));
        }

        if (!this.aspectRatioHasCorrectFormat())
        {
            that.markFieldError($('#aspect_ratio_id'));
        }
    }
});
