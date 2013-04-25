// Copyright (c) 2010-2012 Turbulenz Limited

/*global $*/

$(function () {
    $('select.selectbox').each(function () {

        // create new HTML to replace selectbox
        var items = [];
        var options = $(this).children('option');
        var numOptions = options.length;
        for (var i = 0; i < numOptions; i += 1)
        {
            items[items.length] = '<li><span>' + $(options[i]).text() + '</span></li>';
        }
        $(this).hide().after(
            '<div class="selectbox" tabindex="0"><div><ul>' +
                items.join('') +
            '</ul><b><b>&nbsp;</b></b></div></div>'
        );
        $(this).siblings('.selectbox').focus(function () {
            $(this).find('div:first').toggleClass('drop', true);
        }).blur(function () {
            $(this).find('div:first').toggleClass('drop', false);
        });
    });
});
