/*
* jQuery css clip animation support -- Jim Palmer
* version 0.1.2b
* idea spawned from jquery.color.js by John Resig
* Released under the MIT license.
*/
(function(jQuery) {
jQuery.fx.step.clip = function(fx) {
if (fx.state == 0) {
/* handle three valid possibilities
* val val val val
* val, val, val, val
* val,val,val,val
*/
var cRE = /rect\(([0-9]{1,})(px|em)[,\s]+([0-9]{1,})(px|em)[,\s]+([0-9]{1,})(px|em)[,\s]+([0-9]{1,})(px|em)\)/;
// no longer replace commas - they may not exist and the regex compensates for them anyway
//grab the curent clip region of the element
$elem = $(fx.elem);
var clip = cRE.test(fx.elem.style.clip) ? fx.elem.style.clip : 'rect(0px ' + $elem.width() + 'px ' + $elem.height() + 'px 0px)';
fx.start = cRE.exec(clip.replace(/,/g, " "));
// handle the fx.end error
try {
fx.end = cRE.exec(fx.end.replace(/,/g, ''));
} catch (e) {
return false;
}
}
var sarr = new Array(), earr = new Array(), spos = fx.start.length, epos = fx.end.length,
emOffset = fx.start[ss + 1] == 'em' ? (parseInt($(fx.elem).css('fontSize')) * 1.333 * parseInt(fx.start[ss])) : 1;
for (var ss = 1; ss < spos; ss += 2) { sarr.push(parseInt(emOffset * fx.start[ss])); }
for (var es = 1; es < epos; es += 2) { earr.push(parseInt(emOffset * fx.end[es])); }
fx.elem.style.clip = 'rect(' +
parseInt((fx.pos * (earr[0] - sarr[0])) + sarr[0]) + 'px ' +
parseInt((fx.pos * (earr[1] - sarr[1])) + sarr[1]) + 'px ' +
parseInt((fx.pos * (earr[2] - sarr[2])) + sarr[2]) + 'px ' +
parseInt((fx.pos * (earr[3] - sarr[3])) + sarr[3]) + 'px)';
}
})(jQuery);